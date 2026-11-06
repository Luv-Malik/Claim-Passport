"""Read different file types into plain text + metadata."""
import html
import io
import re
import zipfile
from pathlib import Path

from .errors import AppError

EXT = {".txt": "text", ".md": "markdown", ".markdown": "markdown", ".html": "html", ".htm": "html",
       ".pdf": "pdf", ".docx": "docx", ".pptx": "pptx", ".png": "image", ".jpg": "image", ".jpeg": "image",
       ".webp": "image"}
EDITABLE = {"text", "markdown", "html"}


def detect_format(filename):
    return EXT.get(Path(filename or "").suffix.lower())


def _decode(data):
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return data.decode("latin-1")


def extract(filename, data):
    fmt = detect_format(filename)
    if not fmt:
        raise AppError(f"This file type is not supported yet: {Path(filename or '').suffix or filename}. "
                       "Supported: txt, md, html, pdf, docx, pptx, png, jpg, webp.", 415)
    try:
        return globals()[f"_read_{fmt}"](data)
    except AppError:
        raise
    except Exception as exc:
        raise AppError(f"Could not read this {fmt} file: {exc}", 422)


def _read_text(data):
    return {"fmt": "text", "text": _decode(data), "meta": {}}


def _read_markdown(data):
    return {"fmt": "markdown", "text": _decode(data), "meta": {}}


def _read_html(data):
    return {"fmt": "html", "text": _decode(data), "meta": {}}


def _read_pdf(data):
    from pypdf import PdfReader
    reader = PdfReader(io.BytesIO(data))
    parts, spans, pos = [], [], 0
    for i, page in enumerate(reader.pages, 1):
        t = (page.extract_text() or "").strip()
        spans.append({"page": i, "start": pos, "end": pos + len(t)})
        parts.append(t)
        pos += len(t) + 2
    meta = {"pages": len(reader.pages), "page_spans": spans}
    text = "\n\n".join(parts)
    if not text.strip():
        meta["warning"] = "No selectable text found. This may be a scanned PDF (OCR for PDFs is on the roadmap)."
    return {"fmt": "pdf", "text": text, "meta": meta}


def _read_docx(data):
    from docx import Document
    doc = Document(io.BytesIO(data))
    lines = [p.text for p in doc.paragraphs if p.text.strip()]
    for table in doc.tables:
        for row in table.rows:
            lines.append(" | ".join(c.text.strip() for c in row.cells))
    return {"fmt": "docx", "text": "\n".join(lines), "meta": {"paragraphs": len(lines)}}


def _read_pptx(data):
    z = zipfile.ZipFile(io.BytesIO(data))
    slides = sorted((n for n in z.namelist() if re.match(r"ppt/slides/slide\d+\.xml$", n)),
                    key=lambda n: int(re.search(r"(\d+)", n.rsplit("/", 1)[1]).group(1)))
    parts, images = [], []
    for idx, name in enumerate(slides, 1):
        xml = z.read(name).decode("utf-8", "ignore")
        texts = [html.unescape(t) for t in re.findall(r"<a:t>(.*?)</a:t>", xml, re.S)]
        parts.append(f"[Slide {idx}]\n" + "\n".join(texts))
        for pic in re.findall(r"<p:pic>.*?</p:pic>", xml, re.S):
            nm = re.search(r'<p:cNvPr[^>]*\bname="([^"]*)"', pic)
            alt = re.search(r'<p:cNvPr[^>]*\bdescr="([^"]*)"', pic)
            images.append({"slide": idx, "name": html.unescape(nm.group(1)) if nm else "picture",
                           "alt": bool(alt and alt.group(1).strip())})
    return {"fmt": "pptx", "text": "\n\n".join(parts), "meta": {"slides": len(slides), "images": images}}


def _read_image(data):
    from PIL import Image
    im = Image.open(io.BytesIO(data))
    w, h = im.size
    rgb = im.convert("RGB")
    small = rgb.resize((120, max(1, int(120 * h / w))))
    q = small.quantize(colors=6)
    pal = q.getpalette()
    total = small.size[0] * small.size[1]
    colors = []
    for count, idx in sorted(q.getcolors(), reverse=True):
        r, g, b = pal[idx * 3: idx * 3 + 3]
        colors.append({"hex": "#%02X%02X%02X" % (r, g, b), "share": round(count / total, 3)})
    text, ocr = "", False
    try:
        import pytesseract
        text = pytesseract.image_to_string(rgb).strip()
        ocr = True
    except Exception:
        pass
    return {"fmt": "image", "text": text, "meta": {"width": w, "height": h, "format": im.format, "colors": colors, "ocr": ocr}}
