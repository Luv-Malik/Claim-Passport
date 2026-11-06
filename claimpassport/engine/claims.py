"""Claim extraction: find the sentences that state something that needs proof."""
import re

from .text_utils import sentences

_MONTHS = (r"(?:January|February|March|April|May|June|July|August|September|October|November|December|"
           r"Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sept|Sep|Oct|Nov|Dec)")
# Things that look like numbers but are not claims (dates, standards, versions, URLs...).
_NOISE = [
    re.compile(rf"\b\d{{1,2}}(?:st|nd|rd|th)?\s+{_MONTHS}\.?(?:,?\s+\d{{4}})?\b", re.I),
    re.compile(rf"\b{_MONTHS}\.?\s+\d{{1,2}}(?:st|nd|rd|th)?(?:,?\s+\d{{4}})?\b", re.I),
    re.compile(r"\b\d{4}-\d{2}-\d{2}\b"),
    re.compile(r"\b\d{1,2}/\d{1,2}/\d{2,4}\b"),
    re.compile(r"\bISO\s?\d{3,5}(?::\d{4})?", re.I),
    re.compile(r"\bSOC\s?[123]\b", re.I),
    re.compile(r"\b\d{1,2}\s?[x×/]\s?\d{1,2}\b"),
    re.compile(r"\b\d{1,2}(?::\d{2})?\s?(?:am|pm)\b", re.I),
    re.compile(r"\bQ[1-4]\b"),
    re.compile(r"\bv\d+(?:\.\d+)*\b", re.I),
    re.compile(r"https?://\S+"),
    re.compile(r"\]\([^)]*\)"),
    re.compile(r"\b\d{10,}\b"),
    re.compile(r"(?<!Rs\. )(?<!Rs\.)(?<!₹)(?<!\$)\b(?:19|20)\d{2}\b(?!\s?(?:\+|%|customers|users|clients|teams|businesses))"),
]

TRIGGERS = [
    ("superlative", re.compile(
        r"(?<!\w)(?:the\s+)?(?:best|#\s?1|no\.?\s?1|number\s(?:one|1)|leading|top[- ]rated|top[- ]ranked|"
        r"world[- ]class|fastest|cheapest|lowest[- ]price|unmatched|unbeatable|"
        r"most\s+(?:trusted|secure|reliable|powerful|popular)|only)(?!\w)(?<!\bonly)|(?<!\w)the\s+only(?!\w)",
        re.I)),
    ("absolute", re.compile(
        r"(?<![\w.])(?:100\s?%|guarantee[ds]?|risk[- ]free|zero[- ]risk|no[- ]risk|never\s+(?:fails?|down|breaks?)|"
        r"always\s+(?:on|available|up)|24\s?[x×/]\s?7|round[- ]the[- ]clock|proven|foolproof|unlimited)(?!\w)", re.I)),
    ("certification", re.compile(
        r"(?<!\w)(?:ISO\s?\d{3,5}(?::\d{4})?|SOC\s?[123]|GDPR|HIPAA|PCI[- ]?DSS|certified|accredited|"
        r"award[- ]winning|compliant)(?!\w)", re.I)),
    ("offer", re.compile(
        r"(?<!\w)(?:limited[- ]time|today only|free\s+trial|free\s+forever|money[- ]back|"
        r"no\s+(?:hidden\s+)?fees|offer ends)(?!\w)", re.I)),
    ("comparison", re.compile(r"(?<!\w)(?i:better|cheaper|faster|smarter|easier)\s+(?i:than)\s+[A-Za-z]\w*")),
]

_NUM = re.compile(
    r"(?P<cur>(?:Rs\.?|INR|₹|\$|USD|€)\s?)?(?P<num>\d{1,3}(?:,\d{2,3})+(?:\.\d+)?|\d+(?:\.\d+)?)"
    r"(?P<suf>\s?(?:%|\+|[kKmM]\b|lakh|crore))?", re.I)
_UNIT_AFTER = re.compile(
    r"^\s?-?\s?(?:days?|hours?|months?|years?|minutes?|customers?|users?|clients?|countries|teams?|businesses|invoices?)\b", re.I)
_MULT = {"k": 1e3, "m": 1e6, "lakh": 1e5, "crore": 1e7}


def mask_noise(s):
    for rx in _NOISE:
        s = rx.sub(lambda m: " " * len(m.group()), s)
    return s


def parse_numbers(text, base=0, worthy_only=True, skip_spans=()):
    """Find numbers in `text`. Returns dicts with raw text, value, kind and absolute offsets."""
    out = []
    clean = mask_noise(text)
    for m in _NUM.finditer(clean):
        s, e = m.start(), m.end()
        if any(s < b and e > a for a, b in skip_spans):
            continue
        num = m.group("num").replace(",", "")
        try:
            value = float(num)
        except ValueError:
            continue
        suf = (m.group("suf") or "").strip().lower()
        cur = bool(m.group("cur"))
        plus = suf == "+"
        if suf in _MULT:
            value *= _MULT[suf]
        kind = "money" if cur else "percent" if suf == "%" else "count"
        if worthy_only:
            unit = bool(_UNIT_AFTER.match(clean[e:]))
            if not (cur or suf or value >= 20 or unit):
                continue
        out.append({"raw": text[s:e].strip(), "value": value, "kind": kind, "plus": plus,
                    "start": base + s + (len(text[s:e]) - len(text[s:e].lstrip())),
                    "end": base + e - (len(text[s:e]) - len(text[s:e].rstrip()))})
    return out


def find_triggers(sent, base=0):
    found = []
    for ttype, rx in TRIGGERS:
        for m in rx.finditer(sent):
            s, e = base + m.start(), base + m.end()
            if any(s < fe and e > fs for fs, fe in ((f["start"], f["end"]) for f in found)):
                continue
            found.append({"type": ttype, "text": m.group(), "start": s, "end": e})
    return sorted(found, key=lambda f: f["start"])


def extract_claims(text):
    """Return a list of claims: sentences with triggers (superlatives, certificates...) or numbers."""
    claims = []
    for s, e, sent in sentences(text):
        triggers = find_triggers(sent, s)
        spans = [(t["start"] - s, t["end"] - s) for t in triggers if t["type"] in ("absolute", "superlative")]
        numbers = parse_numbers(sent, s, True, spans)
        if triggers or numbers:
            claims.append({"start": s, "end": e, "text": sent, "triggers": triggers, "numbers": numbers})
    return claims
