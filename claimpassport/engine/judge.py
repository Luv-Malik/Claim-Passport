"""The grounded AI judge (optional).

An AI model is asked whether the approved facts support one sentence. Its answer must be structured JSON and must
CITE the fact it relied on (the fact id) and the matching words copied from that fact. We check the citation
ourselves: an answer without a valid citation is never trusted. It becomes a low-confidence finding that a person
must review. The judge never removes a finding and never decides anything; it only adds evidence.

Privacy: only one sentence and the approved statements of NON-confidential facts are sent, with personal data masked."""
import re

from .. import clock
from . import suggest as S
from .verify import is_expired

VERDICTS = ("supports", "contradicts", "unrelated", "unsure")
MAX_CALLS = 8                      # per analysis, so cost stays bounded


def _norm(s):
    return re.sub(r"[^a-z0-9%+]+", " ", (s or "").lower()).strip()


def validate(answer, candidates):
    """Return a clean verdict dict, or None if it is not usable. `candidates` are {"id", "statement"} dicts.
    `cited` is True only when the fact id is one we offered AND the quoted words really appear in that fact."""
    if not isinstance(answer, dict) or answer.get("verdict") not in VERDICTS:
        return None
    out = {"verdict": answer["verdict"], "fact_id": None, "quote": "", "reason": str(answer.get("reason") or "")[:240],
           "cited": False}
    try:
        fid = int(answer.get("fact_id"))
    except (TypeError, ValueError):
        fid = None
    fact = next((c for c in candidates if c["id"] == fid), None)
    quote = str(answer.get("quote") or "").strip()
    if fact and len(_norm(quote)) >= 2 and _norm(quote) in _norm(fact["statement"]):
        out.update(fact_id=fid, quote=quote, cited=True)
    return out


def _sentence_span(visible_sentences, start):
    return next(((s, e) for s, e, _ in visible_sentences if s <= start < e), None)


def run(llm, facts, findings, claims, visible, sents, today=None):
    """Ask the judge about the most useful sentences. Returns (extra_raw_findings, notes, events).
    - `extra_raw_findings`: C-6 findings when the judge says a sentence contradicts a cited fact.
    - `notes`: {finding_index: advice suggestion} for findings the judge thinks may be supported.
    Nothing is removed or decided here."""
    today = today or clock.today()
    usable = [f for f in facts if not f["confidential"] and not is_expired(f, today)]
    if not usable:
        return [], {}, []
    extra, notes, calls, masked_total, asked = [], {}, 0, 0, set()
    taken = [(r["span_start"], r["span_end"]) for r in findings]
    # most useful first: numbers with no source, then unsupported bold claims
    order = sorted(range(len(findings)), key=lambda i: {"C-4": 0, "C-1": 1}.get(findings[i]["rule_code"], 9))
    for i in order:
        f = findings[i]
        if f["rule_code"] not in ("C-4", "C-1") or calls >= MAX_CALLS:
            continue
        sp = _sentence_span(sents, f["span_start"])
        if not sp or sp in asked:
            continue
        asked.add(sp)
        sentence = visible[sp[0]:sp[1]]
        cands = [{"id": x["id"], "statement": x["statement"]} for x in usable]
        calls += 1
        answer, masked = llm.judge(sentence, cands)
        masked_total += masked
        v = validate(answer, cands)
        if not v or v["verdict"] in ("unrelated", "unsure"):
            continue
        fact = next((x for x in usable if x["id"] == v["fact_id"]), None) if v["cited"] else None
        if v["verdict"] == "supports" and fact:
            notes[i] = S.note(f'The AI judge found a possible source: {fact["key"]}',
                              f'It points to "{v["quote"]}" in "{fact["statement"]}". '
                              "A person must confirm it, then add the claim to the Vault or reword it.")
        elif v["verdict"] == "contradicts":
            if fact:
                extra.append({"rule_code": "C-6", "span": (sp[0], sp[1]), "confidence": 0.78, "fact": fact, "ai": True,
                              "message": f'AI check: this sentence appears to go against the approved fact "{fact["statement"]}" '
                                         f'(matching words: "{v["quote"]}"). {v["reason"]}'.strip(),
                              "suggestions": [S.rep("Use the approved statement", fact["statement"],
                                                    "Replaces this sentence with the approved wording.", (sp[0], sp[1])),
                                              S.note("Ask the fact owner", "If the fact changed, update it in the Vault first.")]})
            elif not _overlaps_any(taken, sp):
                # No valid citation: we cannot trust it, so it is low confidence and goes to a person.
                extra.append({"rule_code": "C-6", "span": (sp[0], sp[1]), "confidence": 0.35, "fact": None, "ai": True,
                              "message": "AI check: this sentence may contradict an approved fact, but the AI did not cite one. "
                                         "Please review it yourself.",
                              "suggestions": [S.note("Review against the Vault", "Compare this sentence with the approved facts.")]})
    events = []
    if calls:
        events.append({"step": "ai-judge", "engine": "anthropic", "model": getattr(llm, "model", "llm"),
                       "data_sent": f"{calls} sentence(s) with the approved statements of non-confidential facts. "
                                    "The AI must cite a fact id and matching words; answers without a valid citation are low confidence.",
                       "masked": masked_total})
    return extra, notes, events


def _overlaps_any(spans, sp):
    return any(sp[0] < b and sp[1] > a for a, b in spans)
