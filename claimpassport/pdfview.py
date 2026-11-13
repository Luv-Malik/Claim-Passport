"""PDF page view with the problems outlined, and OCR for scanned PDFs.

Rendering uses poppler (`pdftoppm`, `pdftotext -bbox`). Scanned pages are read with Tesseract (pytesseract).
Where a finding sits on a page is found by matching the finding's words against the words on the rendered page;
if the words cannot be matched (for example the text was changed by an applied fix), the finding is listed as
"not outlined" instead of drawing a box in the wrong place."""
import base64
import io
import re
import subprocess
import tempfile
from pathlib import Path

TEXT_DPI, SCAN_DPI = 100, 200
MAX_OCR_PAGES = 30
SEVERITY_COLOR = {"high": (214, 69, 69), "medium": (227, 160, 8), "low": (47, 109, 181)}
DONE_COLOR = (31, 164, 99)
_WORD = re.compile(r'<word xMin="([\d.]+)" yMin="([\d.]+)" xMax="([\d.]+)" yMax="([\d.]+)">(.*?)</word>', re.S)
_PAGE = re.compile(r'<page width="([\d.]+)" height="([\d.]+)">(.*?)</page>', re.S)


def norm(s):
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def _run(args, **kw):
    return subprocess.run(args, capture_output=True, timeout=120, **kw)


def tools_available():
    import shutil
    return {"poppler": bool(shutil.which("pdftoppm") and shutil.which("pdftotext")), "tesseract": bool(shutil.which("tesseract"))}


def page_count(data):
    from pypdf import PdfReader
    return len(PdfReader(io.BytesIO(data)).pages)


def _render_png(path, page, dpi):
    from PIL import Image
    r = _run(["pdftoppm", "-f", str(page), "-l", str(page), "-r", str(dpi), "-png", "-singlefile", path, path + "_pg"])
    out = Path(path + "_pg.png")
    if r.returncode != 0 or not out.exists():
        raise RuntimeError("Could not draw this PDF page (is poppler-utils installed?).")
    try:
        return Image.open(io.BytesIO(out.read_bytes())).convert("RGB")
    finally:
        out.unlink(missing_ok=True)


def _text_words(path, page):
    """Words with boxes in PDF points for one page, from the PDF's own text layer."""
    r = _run(["pdftotext", "-f", str(page), "-l", str(page), "-bbox", path, "-"])
    m = _PAGE.search(r.stdout.decode("utf-8", "ignore"))
    if not m:
        return 1.0, 1.0, []
    words = [(float(a), float(b), float(c), float(d), re.sub(r"&(amp|lt|gt|quot|apos);", lambda x: {"amp": "&", "lt": "<", "gt": ">", "quot": '"', "apos": "'"}[x.group(1)], t))
             for a, b, c, d, t in _WORD.findall(m.group(3))]
    return float(m.group(1)), float(m.group(2)), words


def _ocr_words(img):
    import pytesseract
    d = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)
    return [(d["left"][i], d["top"][i], d["left"][i] + d["width"][i], d["top"][i] + d["height"][i], d["text"][i])
            for i in range(len(d["text"])) if (d["text"][i] or "").strip() and float(d["conf"][i]) >= 0]


def ocr_page(data, page):
    """Text of one scanned page, or None when OCR is not possible."""
    try:
        import pytesseract
        with tempfile.TemporaryDirectory() as tmp:
            path = str(Path(tmp) / "in.pdf")
            Path(path).write_bytes(data)
            img = _render_png(path, page, SCAN_DPI)
            return pytesseract.image_to_string(img).strip()
    except Exception:
        return None


# ---------------------------------------------------------------- where does each finding sit?
def _count(hay, key, upto):
    n, i = 0, hay.find(key)
    while i != -1 and i < upto:
        n += 1
        i = hay.find(key, i + 1)
    return n


def locate(findings, current_text, original_text, page_spans):
    """Map findings to (page, ordinal-within-page, key) using the original upload's page layout."""
    if not page_spans:
        return {}
    page_norm = [norm(original_text[s["start"]:s["end"]]) for s in page_spans]
    whole = "".join(page_norm)
    starts, acc = [], 0
    for pn in page_norm:
        starts.append(acc)
        acc += len(pn)
    out = {}
    for f in findings:
        if f["span_end"] <= f["span_start"]:
            continue
        key = norm(f["excerpt"] if f.get("excerpt") else current_text[f["span_start"]:f["span_end"]])
        if len(key) < 2:
            continue
        k = _count(norm(current_text[:f["span_start"]]), key, 10 ** 9)       # which occurrence is it?
        pos, i = -1, -1
        for _ in range(k + 1):
            i = whole.find(key, i + 1)
            if i == -1:
                break
            pos = i
        if pos == -1:
            continue
        pg = max(j for j, st in enumerate(starts) if st <= pos)
        if pos + len(key) > starts[pg] + len(page_norm[pg]) and pg + 1 < len(starts):
            pass                                                              # crosses a page break: keep the first page
        local = pos - starts[pg]
        out[f["id"]] = {"page": pg + 1, "ordinal": _count(page_norm[pg], key, local), "key": key}
    return out


def _boxes_for(words, key, ordinal):
    """Word boxes covering the `ordinal`-th occurrence of `key` among the page's words."""
    concat, owner = "", []
    for wi, w in enumerate(words):
        n = norm(w[4])
        concat += n
        owner += [wi] * len(n)
    pos, i = -1, -1
    for _ in range(ordinal + 1):
        i = concat.find(key, i + 1)
        if i == -1:
            return None
        pos = i
    idx = sorted(set(owner[pos:pos + len(key)]))
    return [words[j] for j in idx]


def _merge_line_boxes(ws):
    """One rectangle per line of text."""
    lines = []
    for x0, y0, x1, y1, _ in ws:
        for ln in lines:
            if abs((ln[1] + ln[3]) / 2 - (y0 + y1) / 2) < (ln[3] - ln[1]) * 0.6:
                ln[0], ln[1], ln[2], ln[3] = min(ln[0], x0), min(ln[1], y0), max(ln[2], x1), max(ln[3], y1)
                break
        else:
            lines.append([x0, y0, x1, y1])
    return lines


def render_page(data, page, findings, located, scanned=False):
    """A PNG of one page with a rectangle around every finding on it. Returns a JSON-ready dict."""
    from PIL import ImageDraw
    dpi = SCAN_DPI if scanned else TEXT_DPI
    with tempfile.TemporaryDirectory() as tmp:
        path = str(Path(tmp) / "in.pdf")
        Path(path).write_bytes(data)
        img = _render_png(path, page, dpi)
        if scanned:
            words, sx, sy = _ocr_words(img), 1.0, 1.0
        else:
            pw, ph, words = _text_words(path, page)
            sx, sy = img.width / pw, img.height / ph
    draw = ImageDraw.Draw(img)
    outlines, unmatched = [], []
    by_id = {f["id"]: f for f in findings}
    on_page = [(fid, loc) for fid, loc in located.items() if loc["page"] == page]
    for n, (fid, loc) in enumerate(sorted(on_page, key=lambda x: x[0]), 1):
        f = by_id[fid]
        ws = _boxes_for(words, loc["key"], loc["ordinal"])
        if not ws:
            unmatched.append(fid)
            continue
        color = DONE_COLOR if f["decision"] != "open" else SEVERITY_COLOR.get(f["severity"], SEVERITY_COLOR["medium"])
        boxes = []
        for x0, y0, x1, y1 in _merge_line_boxes(ws):
            b = [int(x0 * sx) - 3, int(y0 * sy) - 2, int((x1 - x0) * sx) + 6, int((y1 - y0) * sy) + 4]
            boxes.append(b)
            draw.rectangle([b[0], b[1], b[0] + b[2], b[1] + b[3]], outline=color, width=3)
        bx, by = boxes[0][0], max(0, boxes[0][1] - 16)
        draw.rectangle([bx, by, bx + 18, by + 16], fill=color)
        draw.text((bx + 4, by + 2), str(n), fill=(255, 255, 255))
        outlines.append({"finding_id": fid, "n": n, "rule_code": f["rule_code"], "severity": f["severity"],
                         "decision": f["decision"], "boxes": boxes})
    buf = io.BytesIO()
    img.save(buf, "PNG", optimize=True)
    return {"page": page, "width": img.width, "height": img.height, "outlines": outlines, "not_outlined": unmatched,
            "ocr": scanned, "image": "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()}
