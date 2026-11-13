"""The semantic layer used by hybrid verification.

Plain TF-IDF only matches the same words. This layer adds meaning in three ways, from cheapest to richest:

1. A built-in concept lexicon: "clients", "user base" and "customers" all mean the same thing, so they share a
   concept token. It is deterministic, runs offline and every match can be explained. Brands can add their own
   concepts in the Vault (asset "concepts").
2. Optional sentence embeddings (the sentence-transformers package). If it is not installed the product keeps
   working with the lexicon only.
3. (In judge.py) an optional AI judge that must cite the fact it relied on.

It also finds claims written in unusual or implied ways ("our help desk never sleeps", "millions of users"),
which the regex rules for explicit wording cannot see."""
import re

from .. import clock
from . import suggest as S
from .claims import parse_numbers
from .text_utils import sentences
from .verify import FactIndex, fact_numbers, is_expired

# ---------------------------------------------------------------------------------------------- concept lexicon
CONCEPTS = {
    "customers": ["customer base", "user base", "customers", "clients", "users", "businesses", "companies", "firms",
                  "merchants", "subscribers", "organisations", "organizations", "freelancers"],
    "support": ["support", "help desk", "helpdesk", "service desk", "customer care", "customer service", "help centre",
                "help center", "helpline", "assistance", "care team"],
    "always_on": ["never sleeps", "never closes", "never closed", "around the clock", "day and night", "night and day",
                  "any time of day", "any hour", "every hour", "all hours", "non-stop", "nonstop", "365 days",
                  "seven days a week", "7 days a week", "every day of the year", "always open", "always there",
                  "always here", "never offline", "24 hours", "twenty-four hours"],
    "uptime": ["uptime", "never goes down", "never go down", "never down", "zero downtime", "no downtime",
               "without downtime", "downtime", "outage", "always up", "stays up", "stay up", "service level",
               "reliability", "reliable"],
    "price": ["price", "pricing", "cost", "fee", "charge", "starts at", "starting at", "starts from", "starting from",
              "as little as", "as low as", "per month", "a month", "each month", "monthly"],
    "plan_starter": ["starter", "basic plan", "entry plan", "entry-level", "lowest tier", "cheapest plan", "first plan",
                     "base plan", "starting plan"],
    "plan_pro": ["pro plan", "professional plan", "premium plan", "top plan", "advanced plan", "professional"],
    "trial": ["trial", "try for free", "try it free", "try free", "free for", "test drive", "no credit card", "no card",
              "without a card", "evaluation period", "free period", "free to try", "try it out"],
    "discount": ["discount", "% off", "off the price", "save", "saving", "cheaper annual", "yearly deal", "annual deal",
                 "special rate", "reduced price", "price cut"],
    "annual": ["annual", "yearly", "per year", "a year", "each year", "12-month", "twelve month", "year-long",
               "full year", "12 months"],
    "certification": ["certified", "certification", "certificate", "accredited", "accreditation", "iso", "soc",
                      "audited", "compliant", "compliance", "security standard", "information security"],
    "data_location": ["data centre", "data center", "servers", "hosted in", "stored in", "where your data",
                      "data residency", "data is kept", "data lives", "data is stored"],
}


def _phrase_rx(phrases):
    parts = []
    for p in sorted(phrases, key=len, reverse=True):
        esc = re.escape(p.strip().lower()).replace(r"\ ", r"\s+")
        parts.append(esc + (r"(?:s|es)?" if p[-1:].isalpha() else ""))
    return re.compile(r"(?<![a-z0-9])(?:" + "|".join(parts) + r")(?![a-z0-9])", re.I)


_RX_CACHE = {}


def _compiled(extra=()):
    key = tuple(sorted((c["id"], tuple(c["phrases"])) for c in extra))
    if key not in _RX_CACHE:
        merged = {k: list(v) for k, v in CONCEPTS.items()}
        for c in extra:
            merged.setdefault(str(c["id"]), []).extend(c["phrases"])
        _RX_CACHE[key] = {cid: _phrase_rx(ph) for cid, ph in merged.items() if ph}
    return _RX_CACHE[key]


def concepts_in(text, extra=()):
    """The concept ids that appear in `text` (in any of their wordings)."""
    return {cid for cid, rx in _compiled(extra).items() if rx.search(text or "")}


def expand(text, extra=()):
    """Add one meaning-level token per concept found, so different wordings share a token."""
    found = sorted(concepts_in(text, extra))
    return text if not found else text + " " + " ".join("cpt" + c.replace("_", "") for c in found)


# ---------------------------------------------------------------------------------------------- embeddings (optional)
_EMBEDDERS = {}


class SentenceEmbedder:
    def __init__(self, model_name):
        from sentence_transformers import SentenceTransformer        # optional dependency
        self.name = model_name
        self.model = SentenceTransformer(model_name)

    def encode(self, texts):
        return [list(map(float, v)) for v in self.model.encode(list(texts), normalize_embeddings=True)]


def load_embedder(cfg):
    """The embedding model if the package and model are available, otherwise None (the product keeps working)."""
    name = (cfg or {}).get("EMBEDDING_MODEL") or "sentence-transformers/all-MiniLM-L6-v2"
    if name not in _EMBEDDERS:
        try:
            _EMBEDDERS[name] = SentenceEmbedder(name)
        except Exception:
            _EMBEDDERS[name] = None
    return _EMBEDDERS[name]


def embeddings_installed():
    """Cheap check (does not load the model): is the optional sentence-transformers package installed?"""
    import importlib.util
    return importlib.util.find_spec("sentence_transformers") is not None


def _cos(a, b):
    return sum(x * y for x, y in zip(a, b))


class HybridIndex(FactIndex):
    """TF-IDF over concept-expanded text, plus embedding similarity when an embedder is available.
    The score of a fact is the better of the two, so the thresholds tuned for TF-IDF still apply."""

    def __init__(self, facts, embedder=None, extra_concepts=()):
        self.extra, self.embedder = list(extra_concepts or []), embedder
        super().__init__(facts)
        self.mode = "tfidf+concepts" + ("+embeddings" if embedder else "")
        self.fact_vecs = None
        if embedder and facts:
            self.fact_vecs = embedder.encode([f"{f['statement']} {f.get('keywords') or ''}" for f in facts])

    def prep(self, text):
        return expand(text, self.extra)

    def _scores(self, text):
        lex = super()._scores(text)
        if not self.fact_vecs:
            return lex
        q = self.embedder.encode([text])[0]
        # MiniLM-style cosines: ~0.3 is unrelated, ~0.85 is a paraphrase. Uncalibrated: the Accuracy Lab measures it.
        sem = [max(0.0, min(1.0, (_cos(q, v) - 0.30) / 0.55)) for v in self.fact_vecs]
        return [max(a, b) for a, b in zip(lex, sem)]


def build_index(facts, hybrid=False, cfg=None, extra_concepts=()):
    if not hybrid:
        return FactIndex(facts)
    return HybridIndex(facts, load_embedder(cfg), extra_concepts)


# ---------------------------------------------------------------------------------------------- implied claims
def _rx(*alts):
    return re.compile(r"(?<![\w])(?:" + "|".join(alts) + r")(?![\w])", re.I)


IMPLIED = [
    ("absolute", _rx(
        r"never\s+(?:sleeps?|closes?|closed|goes?\s+down|stops?|misses?|offline|crash(?:es)?|lets?\s+you\s+down|"
        r"makes?\s+(?:a\s+)?mistakes?)",
        r"around\s+the\s+clock", r"day\s+and\s+night", r"night\s+and\s+day", r"any\s+(?:time|hour)\s+of\s+the\s+(?:day|night)",
        r"at\s+any\s+hour", r"every\s+hour\s+of\s+every\s+day", r"all\s+day,?\s+every\s+day", r"non-?stop",
        r"365\s+days", r"(?:seven|7)\s+days\s+a\s+week", r"every\s+day\s+of\s+the\s+year",
        r"always\s+(?:open|there|here|reachable|ready)", r"zero\s+downtime", r"no\s+downtime",
        r"without\s+(?:any\s+)?downtime", r"flawless(?:ly)?", r"error-?free", r"mistake-?free", r"failure-?proof",
        r"can(?:no|')t\s+fail", r"cannot\s+fail", r"bulletproof")),
    ("superlative", _rx(
        r"second\s+to\s+none", r"nobody\s+does\s+(?:it\s+)?better", r"no\s+one\s+does\s+(?:it\s+)?better",
        r"unrivall?ed", r"unparalleled", r"in\s+a\s+league\s+of\s+(?:its|our)\s+own", r"head\s+and\s+shoulders\s+above",
        r"like\s+no\s+other", r"beyond\s+compare", r"the\s+gold\s+standard", r"(?:market|industry|category)\s+leader",
        r"nothing\s+(?:else\s+)?compares", r"unequall?ed", r"peerless", r"the\s+one\s+and\s+only",
        r"everyone'?s\s+(?:favou?rite|first\s+choice)")),
    ("certification", _rx(
        r"bank-?\s?grade", r"military-?\s?grade", r"fully\s+(?:audited|secure)", r"independently\s+(?:audited|verified|certified)",
        r"passed\s+(?:every|all)\s+(?:security\s+)?audits?", r"meets?\s+(?:all|every)\s+(?:industry\s+)?(?:security\s+)?standards?",
        r"hack-?proof", r"unhackable", r"(?:completely|totally)\s+secure")),
    ("comparison", _rx(
        r"unlike\s+(?:other|most|many)\s+(?:tools|apps|platforms|products|vendors|competitors|solutions|software)",
        r"outperforms?", r"beats?\s+(?:the\s+)?(?:competition|competitors|rivals|others|everyone)",
        r"leaves?\s+(?:the\s+)?(?:competition|competitors|rivals)(?:\s+far)?\s+behind",
        r"(?:other|rival)\s+(?:tools|apps|platforms)\s+can(?:no|')t\s+(?:match|compete)",
        r"ahead\s+of\s+(?:the\s+)?(?:competition|competitors|everyone|the\s+rest)")),
]
QUANTITY = re.compile(
    r"(?<![\w])(?P<mag>tens\s+of\s+(?:thousands|millions)|hundreds\s+of\s+(?:thousands|millions)|millions|thousands|hundreds)"
    r"\s+of\s+(?:(?:happy|loyal|active|paying|satisfied|small)\s+)?(?P<ent>[a-z]+)(?![\w])", re.I)
_MAG_LOW = {"hundreds": 200, "thousands": 2_000, "millions": 2_000_000, "tens of thousands": 20_000,
            "tens of millions": 20_000_000, "hundreds of thousands": 200_000, "hundreds of millions": 200_000_000}
_WHY = {"absolute": "an absolute promise", "superlative": "a ranking or top-spot claim",
        "certification": "a security or certification claim", "comparison": "a comparison with other brands"}


def _overlaps(spans, a, b):
    return any(a < e and b > s for s, e in spans)


def _supports_phrase(fact, kind):
    text = f"{fact['statement']} {fact.get('value') or ''}"
    return any(rx.search(text) for k, rx in IMPLIED if k == kind) or bool(
        kind == "absolute" and re.search(r"24\s?[x×/]\s?7|round[- ]the[- ]clock|always\s+(?:on|available|up)", text, re.I))


def _count_min(fact):
    nums = [n for n in fact_numbers(fact) if n["kind"] == "count"]
    return max((n["value"] for n in nums), default=None)


def _fact_text(fact):
    return "(confidential fact)" if fact["confidential"] else fact["statement"]


def implied_findings(visible, index, facts, today=None, taken=(), extra_concepts=()):
    """Claims written in other words. Returns raw findings in the same shape the pipeline uses.
    `taken` lists spans that already have a finding, so one phrase is never flagged twice."""
    today = today or clock.today()
    taken, out = list(taken), []
    for s, e, sent in sentences(visible):
        for kind, rx in IMPLIED:
            for m in rx.finditer(sent):
                a, b = s + m.start(), s + m.end()
                if _overlaps(taken, a, b):
                    continue
                taken.append((a, b))
                phrase = m.group().strip()
                cands = index.search(sent, k=3)
                if kind == "comparison":
                    out.append({"rule_code": "C-5", "span": (a, b), "confidence": 0.8, "fact": None,
                                "message": f'"{phrase}" is {_WHY[kind]}. This needs proof and Legal review.',
                                "suggestions": [S.note("Ask Legal for proof", "Naming or implying competitors needs a dated, published comparison and a legal review."),
                                                S.note("Describe your own benefit", "Say what your product does well without comparing it.")]})
                    continue
                related = next(((sc, f) for sc, f in cands if not is_expired(f, today)), None) if cands else None
                if related and _supports_phrase(related[1], kind):
                    continue                                # an approved fact really says this
                if related and kind == "absolute":
                    sc, f = related
                    sugg = [S.note("Use the approved wording", "Say exactly what the approved fact says."),
                            S.note("Ask the owner", f"If this has changed, {f['owner'] or 'the owner'} must update the fact in the Vault first.")]
                    if not f["confidential"]:
                        sugg.insert(0, S.rep("Use the approved statement", f["statement"], "Replaces this sentence with the approved wording.", (s, e)))
                    out.append({"rule_code": "C-6", "span": (a, b), "confidence": min(0.9, 0.65 + 0.6 * sc), "fact": f,
                                "message": f'"{phrase}" is {_WHY[kind]}, but the approved fact says "{_fact_text(f)}"',
                                "suggestions": sugg})
                else:
                    out.append({"rule_code": "C-1", "span": (a, b), "confidence": 0.75, "fact": None,
                                "force_lock": kind == "certification",
                                "message": f'"{phrase}" is {_WHY[kind]} with no approved source in the Brand Vault.',
                                "suggestions": [S.note("Ask for a verified fact", "Security or Legal can add it to the Vault with proof."),
                                                S.note("Say what you can prove", "Use a measurable fact from the Vault instead.")]})
        for m in QUANTITY.finditer(sent):
            a, b = s + m.start(), s + m.end()
            if _overlaps(taken, a, b):
                continue
            taken.append((a, b))
            mag = re.sub(r"\s+", " ", m.group("mag").lower())
            ent_concepts = concepts_in(m.group("ent"), extra_concepts)
            if not ent_concepts:
                continue                                      # "thousands of ideas": not a claim about our numbers
            cands = index.search(sent, k=3)
            same = [(sc, f) for sc, f in cands if (concepts_in(f"{f['statement']} {f.get('keywords') or ''}", extra_concepts) & ent_concepts)
                    and _count_min(f) is not None and not is_expired(f, today)]
            phrase = m.group().strip()
            if not same:
                out.append({"rule_code": "C-4", "span": (a, b), "confidence": 0.55, "fact": None,
                            "message": f'"{phrase}" states how many, but there is no approved number for it in the Brand Vault.',
                            "suggestions": [S.note("Add the fact to the Vault", "A manager can add it with a source document, owner and expiry date."),
                                            S.note("Reword without the amount", "Describe the benefit without the size claim.")]})
                continue
            sc, f = same[0]
            if _count_min(f) >= _MAG_LOW[mag]:
                continue                                      # "thousands" is true when the fact says 10,000+
            good = next((n["raw"] for n in fact_numbers(f) if n["kind"] == "count"), f.get("value") or "")
            sugg = [S.note("Ask the fact owner", f"If the number grew, {f['owner'] or 'the owner'} must update the fact first.")]
            if not f["confidential"]:
                noun = m.group("ent")
                sugg.insert(0, S.rep(f"Use the approved number ({good})", f"{good} {noun}", "Keeps your sentence and states what the approved fact says.", (a, b)))
            out.append({"rule_code": "C-6", "span": (a, b), "confidence": min(0.9, 0.65 + 0.6 * sc), "fact": f,
                        "message": f'"{phrase}" claims more than the approved fact, which says "{_fact_text(f)}"',
                        "suggestions": sugg})
    return out
