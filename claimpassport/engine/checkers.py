"""Rule checkers: tone, terminology, messaging, accessibility and visual consistency.

Every checker returns raw findings: {"rule_code", "span": (start, end), "message", "suggestions", "confidence"}.
The pipeline later adds severity, source and human-lock information from the rule."""
import re

from . import suggest as S
from .text_utils import sentences


class Ctx:
    """Everything a checker may need."""

    def __init__(self, text, visible, fmt, meta, rules, glossary, palette, fonts, image_rules):
        self.text, self.visible, self.fmt, self.meta = text, visible, fmt, meta or {}
        self.rules, self.glossary = rules, glossary
        self.palette, self.fonts, self.image_rules = palette, fonts, image_rules

    def rule(self, code):
        r = self.rules.get(code)
        return r if r and r.get("active", 1) else None


def F(code, s, e, message, suggestions, conf=0.85, **extra):
    d = {"rule_code": code, "span": (s, e), "message": message, "suggestions": suggestions, "confidence": conf}
    d.update(extra)
    return d


def _find(text, term, case_sensitive=False):
    flags = 0 if case_sensitive else re.I
    return list(re.finditer(r"(?<![\w])" + re.escape(term) + r"(?![\w])", text, flags))


# ---------------------------------------------------------------- terminology and tone words
def check_glossary(ctx):
    rule, out = ctx.rule("TERM-1"), []
    if not rule:
        return out
    for g in ctx.glossary:
        pref = g["preferred"]
        good = [(m.start(), m.end()) for m in _find(ctx.visible, pref, True)]
        for banned in g["banned"]:
            for m in _find(ctx.visible, banned, bool(g["case_sensitive"])):
                if m.group() == pref or any(a <= m.start() and m.end() <= b for a, b in good):
                    continue
                note = f" {g['note']}" if g.get("note") else ""
                out.append(F("TERM-1", m.start(), m.end(),
                             f'"{m.group()}" is not the approved term. Please write "{pref}".{note}',
                             [S.rep(f'Use "{pref}"', pref, "Same meaning, written the approved way.")], 0.95))
    return out


def check_terms_rules(ctx):
    out = []
    for rule in ctx.rules.values():
        if rule["kind"] != "terms" or not rule.get("active", 1):
            continue
        cs = bool(rule["config"].get("case_sensitive"))
        for term, alts in (rule["config"].get("pairs") or {}).items():
            good = [(x.start(), x.end()) for a in alts for x in _find(ctx.visible, a, True)]
            for m in _find(ctx.visible, term, cs):
                found = m.group()
                if any(a <= m.start() and m.end() <= b for a, b in good):
                    continue
                sugg = [S.rep(f'Use "{S.case_like(found, a)}"', S.case_like(found, a),
                              "Same meaning in the brand's approved style.") for a in alts[:3]]
                tip = f' Try "{S.case_like(found, alts[0])}".' if alts else ""
                out.append(F(rule["code"], m.start(), m.end(), f'"{found}": {rule["title"]}.{tip}', sugg, 0.9))
    return out


# ---------------------------------------------------------------- tone
def check_exclaim(ctx):
    rule = ctx.rule("T-2")
    if not rule:
        return []
    mx = int(rule["config"].get("max", 1))
    out, seen = [], 0
    for m in re.finditer(r"!+", ctx.visible):
        seen += 1
        if len(m.group()) > 1 or seen > mx:
            out.append(F("T-2", m.start(), m.end(),
                         "Too many exclamation marks. Our voice is friendly but calm: use at most one per piece.",
                         [S.rep("Use a full stop", ".", "Keeps your message with a calmer tone.")], 0.9))
    return out


def check_caps(ctx):
    rule = ctx.rule("T-3")
    if not rule:
        return []
    allow = {a.upper() for a in rule["config"].get("allow", [])}
    allow |= {g["preferred"].upper() for g in ctx.glossary}
    mn = int(rule["config"].get("min_len", 4))
    out = []
    for m in re.finditer(r"\b[A-Z]{%d,}\b" % mn, ctx.visible):
        w = m.group()
        if w in allow:
            continue
        pre = ctx.visible[max(0, m.start() - 2):m.start()]
        start_of_sentence = pre.strip() == "" or pre.strip()[-1:] in ".!?"
        opts = [S.rep(f'Use "{w.capitalize()}"', w.capitalize(), "Same word without shouting.")]
        if not start_of_sentence:
            opts = [S.rep(f'Use "{w.lower()}"', w.lower(), "Same word without shouting.")] + opts
        out.append(F("T-3", m.start(), m.end(), f'"{w}" is in ALL CAPS, which reads as shouting.', opts, 0.9))
    return out


# ---------------------------------------------------------------- accessibility
def check_readability(ctx):
    rule = ctx.rule("A-1")
    if not rule:
        return []
    mx = int(rule["config"].get("max_words", 28))
    out = []
    for s, e, sent in sentences(ctx.visible):
        if sent.startswith(("#", "http", "|")):
            continue
        n = len(re.findall(r"\b[\w'-]+\b", sent))
        if n > mx:
            sugg = []
            opt = S.sentence_split_option(sent, s)
            if opt:
                sugg.append(opt)
            sugg.append(S.note("Shorten it yourself", "Aim for one idea per sentence."))
            out.append(F("A-1", s, e, f"This sentence has {n} words. Sentences under {mx} words are easier to read.",
                         sugg, 0.8))
    return out


def check_alt_text(ctx):
    rule = ctx.rule("A-2")
    if not rule:
        return []
    out = []
    advice = [S.note("Add alt text", "Describe what the image shows and why it matters, in one short sentence.")]
    if ctx.fmt == "html":
        for m in re.finditer(r"<img\b[^>]*>", ctx.text, re.I | re.S):
            tag = m.group()
            alt = re.search(r"\balt\s*=\s*([\"'])(.*?)\1", tag, re.I | re.S)
            if (not alt or not alt.group(2).strip()) and not re.search(r'role\s*=\s*["\']presentation', tag, re.I):
                out.append(F("A-2", m.start(), m.end(), "This image has no alt text, so screen readers cannot describe it.", advice, 0.95))
    if ctx.fmt in ("markdown", "text"):
        for m in re.finditer(r"!\[\s*\]\([^)]*\)", ctx.text):
            out.append(F("A-2", m.start(), m.end(), "This image has no alt text, so screen readers cannot describe it.", advice, 0.95))
    if ctx.fmt == "pptx":
        for img in ctx.meta.get("images", []):
            if not img.get("alt"):
                out.append(F("A-2", 0, 0, f'Picture "{img.get("name", "image")}" on slide {img.get("slide", "?")} has no alt text.', advice, 0.9))
    if ctx.fmt == "image" and not (ctx.meta.get("alt_text") or "").strip():
        out.append(F("A-2", 0, 0, "This image was uploaded without alt text.", advice, 0.9))
    return out


def check_links(ctx):
    rule = ctx.rule("A-3")
    if not rule:
        return []
    generic = {g.lower() for g in rule["config"].get("generic", [])}
    out = []
    pats = [re.compile(r"\[([^\]]+)\]\([^)]*\)")]
    if ctx.fmt == "html":
        pats.append(re.compile(r"<a\b[^>]*>(.*?)</a>", re.I | re.S))
    for rx in pats:
        for m in rx.finditer(ctx.text):
            label = re.sub(r"<[^>]+>", "", m.group(1)).strip()
            if label.lower() in generic:
                out.append(F("A-3", m.start(1), m.end(1), f'The link text "{label}" does not say where the link goes.',
                             [S.note("Describe the destination", 'For example: "Read the pricing guide" instead of "click here".')], 0.9))
    return out


def _hex_rgb(h):
    h = h.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def _lum(rgb):
    def ch(c):
        c /= 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (ch(c) for c in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast_ratio(a, b):
    la, lb = _lum(_hex_rgb(a)), _lum(_hex_rgb(b))
    hi, lo = max(la, lb), min(la, lb)
    return round((hi + 0.05) / (lo + 0.05), 2)


_HEX = r"#[0-9a-fA-F]{6}\b|#[0-9a-fA-F]{3}\b"


def _decl_blocks(text):
    blocks = [(m.start(2), m.end(2)) for m in re.finditer(r"style\s*=\s*([\"'])(.*?)\1", text, re.S | re.I)]
    for sm in re.finditer(r"<style[^>]*>(.*?)</style>", text, re.S | re.I):
        base = sm.start(1)
        for bm in re.finditer(r"\{([^}]*)\}", sm.group(1)):
            blocks.append((base + bm.start(1), base + bm.end(1)))
    return blocks


def check_contrast(ctx):
    rule = ctx.rule("A-4")
    if not rule or ctx.fmt != "html":
        return []
    need = float(rule["config"].get("min_ratio", 4.5))
    out = []
    for a, b in _decl_blocks(ctx.text):
        block = ctx.text[a:b]
        fg = re.search(r"(?<![-\w])color\s*:\s*(%s)" % _HEX, block)
        bg = re.search(r"background(?:-color)?\s*:\s*(%s)" % _HEX, block)
        if not (fg and bg):
            continue
        ratio = contrast_ratio(fg.group(1), bg.group(1))
        if ratio < need:
            fs, fe = a + fg.start(1), a + fg.end(1)
            sugg = []
            for p in ctx.palette:
                if contrast_ratio(p["hex"], bg.group(1)) >= need:
                    sugg.append(S.rep(f'Use {p["name"]} ({p["hex"]})', p["hex"],
                                      f"Passes the 4.5:1 contrast rule on this background."))
                if len(sugg) == 2:
                    break
            out.append(F("A-4", fs, fe, f"Text colour {fg.group(1)} on {bg.group(1)} has a contrast of {ratio}:1. "
                         f"People with low vision need at least {need}:1.", sugg, 0.97))
    return out


# ---------------------------------------------------------------- visual consistency (html)
def _nearest(hexv, palette):
    rgb = _hex_rgb(hexv)
    best = None
    for p in palette:
        d = sum((x - y) ** 2 for x, y in zip(rgb, _hex_rgb(p["hex"]))) ** 0.5
        if best is None or d < best[0]:
            best = (d, p)
    return best


def check_palette(ctx):
    rule = ctx.rule("V-1")
    if not rule or ctx.fmt != "html" or not ctx.palette:
        return []
    tol = float(rule["config"].get("tolerance", 40))
    out = []
    for m in re.finditer(_HEX, ctx.text):
        rgb = _hex_rgb(m.group())
        if max(rgb) - min(rgb) < 14:      # greys are allowed
            continue
        d, p = _nearest(m.group(), ctx.palette)
        if d > tol:
            out.append(F("V-1", m.start(), m.end(), f"{m.group()} is not one of the brand colours.",
                         [S.rep(f'Use {p["name"]} ({p["hex"]})', p["hex"], "The closest approved brand colour.")], 0.85))
    return out


def check_fonts(ctx):
    rule = ctx.rule("V-2")
    if not rule or ctx.fmt != "html" or not ctx.fonts:
        return []
    ok = {f.lower() for f in ctx.fonts} | {"sans-serif", "serif", "monospace", "inherit", "system-ui"}
    out = []
    for m in re.finditer(r"font-family\s*:\s*(?:([\"'])(?P<q>[^\"']+)\1|(?P<u>[^,;}\"'<>\n]+))", ctx.text, re.I):
        grp = "q" if m.group("q") else "u"
        name = m.group(grp).strip()
        if name and name.lower() not in ok:
            s = m.start(grp) + (len(m.group(grp)) - len(m.group(grp).lstrip()))
            out.append(F("V-2", s, s + len(name), f'The font "{name}" is not an approved brand font.',
                         [S.rep(f'Use "{ctx.fonts[0]}"', ctx.fonts[0], "The main brand font.")], 0.9))
    return out


def check_image(ctx):
    rule = ctx.rule("V-3")
    if not rule or ctx.fmt != "image":
        return []
    cfg, m, out = rule["config"], ctx.meta, []
    w, h = m.get("width", 0), m.get("height", 0)
    rules = ctx.image_rules or {}
    if rules.get("min_width") and w and w < rules["min_width"]:
        out.append(F("V-3", 0, 0, f"The image is {w}px wide. Brand images should be at least {rules['min_width']}px wide.",
                     [S.note("Export a larger image", "Use the original design file or a higher-resolution export.")], 0.9))
    ratios = rules.get("ratios") or []
    if ratios and w and h:
        r = w / h
        tol = float(cfg.get("ratio_tolerance", 0.05))
        if not any(abs(r - a) / a <= tol for a in ratios):
            out.append(F("V-3", 0, 0, f"The image shape ({w}x{h}) is not one of the approved shapes.",
                         [S.note("Crop to an approved shape", "Approved width-to-height ratios: " + ", ".join(f"{a:.2f}" for a in ratios))], 0.8))
    for c in m.get("colors", []):
        rgb = _hex_rgb(c["hex"])
        if c["share"] >= float(cfg.get("coverage", 0.2)) and max(rgb) - min(rgb) >= 14 and ctx.palette:
            d, p = _nearest(c["hex"], ctx.palette)
            if d > float(cfg.get("distance", 70)):
                out.append(F("V-3", 0, 0, f"About {round(c['share'] * 100)}% of the image uses {c['hex']}, which is far from the brand colours.",
                             [S.note(f"Recolour towards {p['name']} ({p['hex']})", "Use the brand palette for large areas of colour.")], 0.75))
    return out


# ---------------------------------------------------------------- messaging rules from the guidelines
def check_requires(ctx):
    out = []
    for rule in ctx.rules.values():
        if rule["kind"] != "requires" or not rule.get("active", 1):
            continue
        cfg = rule["config"]
        trig = re.search(cfg["trigger"], ctx.visible, re.I)
        if trig and not re.search(cfg["required"], ctx.visible, re.I):
            sent = next(((s, e) for s, e, _ in sentences(ctx.visible) if s <= trig.start() < e), (trig.start(), trig.end()))
            add = cfg.get("append", "")
            end_text = ctx.visible[sent[0]:sent[1]]
            joiner = " " if end_text.endswith((".", "!", "?")) else ". "
            out.append(F(rule["code"], trig.start(), trig.end(), cfg.get("message", rule["title"]),
                         [S.rep(f'Add "{add}"', joiner + add, "Adds the required line without changing your message.", (sent[1], sent[1]))], 0.9))
    return out


def check_regex_rules(ctx):
    out = []
    for rule in ctx.rules.values():
        if rule["kind"] != "regex" or not rule.get("active", 1):
            continue
        cfg = rule["config"]
        try:
            rx = re.compile(cfg["pattern"], re.I if "i" in cfg.get("flags", "") else 0)
        except re.error:
            continue
        for m in rx.finditer(ctx.visible):
            out.append(F(rule["code"], m.start(), m.end(), cfg.get("message", rule["title"]),
                         [S.note("Reword with Legal", cfg.get("advice", "Describe what the product does, not the legal result."))], 0.85))
    return out


ALL = (check_glossary, check_terms_rules, check_exclaim, check_caps, check_readability, check_alt_text,
       check_links, check_contrast, check_palette, check_fonts, check_image, check_requires, check_regex_rules)


def run_all(ctx):
    out = []
    for fn in ALL:
        out.extend(fn(ctx))
    return out
