"""Small text helpers. All offsets always refer to the ORIGINAL text, so highlights line up."""
import re

_ABBR = re.compile(r"\b(Rs|No|Mr|Mrs|Ms|Dr|vs|etc|approx|Inc|Ltd)\.", re.I)
_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9\"“(\[#*\-])|\n+")


def sentences(text):
    """Return [(start, end, sentence)] with offsets into `text`."""
    masked = _ABBR.sub(lambda m: m.group(0)[:-1] + "_", text)
    out, pos = [], 0
    for m in _SPLIT.finditer(masked):
        _add(out, text, pos, m.start())
        pos = m.end()
    _add(out, text, pos, len(text))
    return out


def _add(out, text, s, e):
    seg = text[s:e]
    stripped = seg.strip()
    if not stripped:
        return
    s2 = s + (len(seg) - len(seg.lstrip()))
    out.append((s2, s2 + len(stripped), stripped))


def mask_html(text):
    """Blank out tags/scripts/styles with spaces so visible text keeps the same offsets."""
    return re.sub(r"<script.*?</script>|<style.*?</style>|<!--.*?-->|<[^>]+>",
                  lambda m: " " * len(m.group()), text, flags=re.S | re.I)


def words(text):
    return re.findall(r"[A-Za-z0-9']+", text)


def syllables(word):
    groups = re.findall(r"[aeiouy]+", word.lower())
    return max(1, len(groups))


def reading_ease(text):
    """Flesch reading ease (higher = easier). Returns None for very short text."""
    ws = words(text)
    sents = [s for _, _, s in sentences(text)]
    if len(ws) < 8 or not sents:
        return None
    syl = sum(syllables(w) for w in ws)
    return round(206.835 - 1.015 * (len(ws) / len(sents)) - 84.6 * (syl / len(ws)), 1)


def clean_gap(text, start):
    """After deleting text at `start`, tidy double spaces and space-before-punctuation."""
    text = re.sub(r"[ \t]{2,}", " ", text)
    text = re.sub(r"\s+([.,;:!?])", r"\1", text)
    return text
