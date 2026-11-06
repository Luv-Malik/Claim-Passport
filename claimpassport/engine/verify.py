"""Check claims against approved facts.

Retrieval is a small TF-IDF search (pure Python, no model download). It is deliberately simple and
explainable: every match shows the fact and the score. See docs/ROADMAP.md for the embeddings upgrade."""
import math
import re
from collections import Counter

from .. import clock
from .claims import parse_numbers

MIN_SCORE = 0.18
MISMATCH_MIN_SCORE = 0.3
_STOP = set("a an the and or of to in on for with is are was were be been it its this that at by from as our we "
            "you your has have had will can all every get gets per".split())


def tokens(text):
    out = []
    for t in re.findall(r"[a-z0-9]+", text.lower()):
        if t in _STOP:
            continue
        if len(t) > 4:
            for suf in ("ing", "ed", "es", "s"):
                if t.endswith(suf) and len(t) - len(suf) >= 3:
                    t = t[: -len(suf)]
                    break
        out.append(t)
    return out


class FactIndex:
    def __init__(self, facts):
        self.facts = facts
        docs = [tokens(f"{f['statement']} {f.get('keywords') or ''} {f.get('category') or ''} {f.get('key') or ''}")
                for f in facts]
        df = Counter()
        for d in docs:
            df.update(set(d))
        n = max(len(docs), 1)
        self.idf = {t: math.log((n + 1) / (c + 0.5)) + 1 for t, c in df.items()}
        self.vecs = [self._vec(d) for d in docs]

    def _vec(self, toks):
        tf = Counter(toks)
        v = {t: (1 + math.log(c)) * self.idf.get(t, 1.0) for t, c in tf.items()}
        norm = math.sqrt(sum(x * x for x in v.values())) or 1.0
        return {t: x / norm for t, x in v.items()}

    def search(self, text, k=3):
        q = self._vec(tokens(text))
        scored = [(sum(q.get(t, 0) * w for t, w in vec.items()), f) for vec, f in zip(self.vecs, self.facts)]
        scored.sort(key=lambda x: -x[0])
        return [(s, f) for s, f in scored[:k] if s >= MIN_SCORE]


def fact_numbers(fact):
    return parse_numbers(f"{fact.get('value') or ''}. {fact['statement']}", 0, worthy_only=False)


def approved_number_raw(fact, kind=None):
    """The number exactly as the approved fact writes it, e.g. 'Rs. 499' or '10,000+'."""
    nums = fact_numbers(fact)
    pick = [n for n in nums if kind is None or n["kind"] == kind] or nums
    return pick[0]["raw"] if pick else (fact.get("value") or "")


def _norm(s):
    return re.sub(r"[^a-z0-9%#]", "", s.lower())


def is_expired(fact, today=None):
    exp = clock.parse_date(fact.get("expires_on"))
    return bool(exp and exp < (today or clock.today()))


def verify_claim(claim, index, facts, today=None):
    """Return how each number and trigger of a claim stands against the approved facts."""
    today = today or clock.today()
    cands = index.search(claim["text"], k=3)
    best = cands[0] if cands else (0.0, None)
    num_results, trig_results = [], []
    for num in claim["numbers"]:
        res = {"number": num, "status": "no_source", "fact": None, "score": best[0]}
        same_kind = [(s, f) for s, f in cands if any(n["kind"] == num["kind"] for n in fact_numbers(f))]
        if same_kind:
            match = None
            for s, f in same_kind:
                for fn in fact_numbers(f):
                    if fn["kind"] != num["kind"]:
                        continue
                    ok = abs(fn["value"] - num["value"]) <= 1e-6 * max(1.0, fn["value"])
                    # "Over 5,000" or "5,000+" is true when the fact says "10,000+"
                    prefix = claim["text"][max(0, num["start"] - claim["start"] - 22):num["start"] - claim["start"]].lower()
                    softened = num["plus"] or any(w in prefix for w in ("over", "more than", "at least", "up to"))
                    if not ok and fn["plus"] and softened and num["value"] <= fn["value"]:
                        ok = True
                    if ok:
                        match = (s, f)
                        break
                if match:
                    break
            if match:
                res.update(status="supported", fact=match[1], score=match[0])
            else:
                s, f = same_kind[0]
                if s >= MISMATCH_MIN_SCORE:      # only call it a mismatch when the fact is clearly about the same thing
                    res.update(status="mismatch", fact=f, score=s)
        num_results.append(res)
    for trig in claim["triggers"]:
        key = _norm(re.sub(r"^the\s+", "", trig["text"], flags=re.I))
        hit = None
        for f in facts:
            if key and key in _norm(f"{f['statement']} {f.get('value') or ''}"):
                hit = f
                break
        trig_results.append({"trigger": trig, "status": "supported" if hit else "unsupported", "fact": hit})
    return {"numbers": num_results, "triggers": trig_results, "best": best}
