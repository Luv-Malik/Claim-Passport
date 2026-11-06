"""Fix suggestions. They change ONLY the problem phrase, so the writer's sentence and purpose stay.
A suggestion is either kind='replace' (text change) or kind='note' (advice, no text change)."""
import re


def rep(label, replacement, rationale, span=None):
    s = {"kind": "replace", "label": label, "replacement": replacement, "rationale": rationale}
    if span:
        s["span"] = [span[0], span[1]]
    return s


def note(label, rationale):
    return {"kind": "note", "label": label, "replacement": None, "rationale": rationale}


def case_like(src, alt):
    if len(src) > 1 and src.isupper():
        return alt.upper()
    if src[:1].isupper():
        return alt[:1].upper() + alt[1:]
    return alt


_ABSOLUTE = {"100%": ["highly", "built to be"], "risk-free": ["low-risk"], "zero risk": ["low risk"],
             "no risk": ["low risk"], "proven": ["tested"], "foolproof": ["dependable"],
             "24/7": ["weekday"], "24x7": ["weekday"], "round-the-clock": ["weekday"],
             "unlimited": ["generous"]}
_COMPARE = {"cheaper": "affordable", "faster": "fast", "better": "a strong choice", "smarter": "smart",
            "easier": "easy to use"}


def hype_options(trigger_text, ttype):
    """Options for an unproven superlative / absolute claim."""
    t = trigger_text.strip()
    low = re.sub(r"\s+", " ", t.lower())
    has_article = low.startswith("the ")
    core = low[4:] if has_article else low
    opts = []
    if ttype == "superlative":
        if core.startswith("most "):
            for alt in (core[5:], "trusted"):
                opts.append(rep(f'Use "{alt}"', case_like(t, alt), "Keeps your point without claiming to be the top."))
        elif core in ("#1", "# 1", "no. 1", "no 1", "number one", "number 1"):
            for alt in ("popular", "trusted"):
                opts.append(rep(f'Use "{alt}"', case_like(t, alt), "Keeps the praise but does not claim a rank."))
        elif core == "only":
            pass
        else:
            for alt in ("reliable", "trusted", "simple"):
                text = ("a " if has_article else "") + alt
                if len(opts) < 2:
                    opts.append(rep(f'Use "{text}"', case_like(t, text),
                                    "Same meaning, but it is a fair description instead of a ranking."))
    else:
        for alt in _ABSOLUTE.get(core, [])[:2]:
            opts.append(rep(f'Use "{alt}"', case_like(t, alt), "Softer wording that the company can stand behind."))
        if not opts:
            opts.append(note("Replace with a measurable fact",
                             "Use a number or fact that exists in the Brand Vault instead of an absolute promise."))
    opts.append(rep("Remove this phrase", "", "Keeps the rest of your sentence and drops only the unproven wording."))
    return opts


def compare_options(trigger_text):
    first = trigger_text.split()[0]
    alt = _COMPARE.get(first.lower(), "strong")
    return [rep(f'Use "{alt}"', alt, "Describes your own benefit without naming another brand."),
            note("Ask Legal for proof", "Naming a competitor needs a dated, published comparison and a legal review.")]


def sentence_split_option(sentence, start):
    """Try to split a long sentence at a natural joining word."""
    mid = len(sentence) / 2
    best = None
    for m in re.finditer(r"(, and |; |, but |, which |, so | and )", sentence):
        dist = abs(m.start() - mid)
        if m.start() > 25 and len(sentence) - m.end() > 25 and (best is None or dist < best[0]):
            best = (dist, m)
    if not best:
        return None
    m = best[1]
    first, second = sentence[:m.start()].rstrip(",;"), sentence[m.end():]
    if not second:
        return None
    new = f"{first}. {second[:1].upper()}{second[1:]}"
    return rep("Split into two sentences", new, "Same words, shorter sentences. Easier to read for everyone.",
               (start, start + len(sentence)))
