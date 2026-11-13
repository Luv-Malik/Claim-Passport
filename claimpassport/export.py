"""Fix-in-place export: write the accepted text changes back into the ORIGINAL Word or PowerPoint file.

How: the text of the original file is compared with the current version's text, word by word. Every difference is a
small edit (for example "449" -> "499"). Each edit is written into the exact paragraph or text run it came from, so
fonts, colours, spacing, images and layout stay exactly as they were.

What it will NOT do (it lists these instead of guessing, so a person can copy them by hand):
- an edit that crosses paragraphs, table cells or slide text boxes,
- text that spans several runs with different formatting (bold in the middle of the phrase, for example),
- paragraphs with links or fields (their text is not a plain run),
- a table cell with more than one paragraph."""
import difflib
import html
import io
import re
import zipfile
from xml.sax.saxutils import escape

from . import ingest
from .errors import AppError

FORMATS = {"docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
           "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation"}


def edits_between(orig, cur):
    """Word-level edits that turn `orig` into `cur`: [(start, end, replacement)] in `orig` offsets."""
    a, b = re.findall(r"\s+|\S+", orig), re.findall(r"\s+|\S+", cur)
    starts, pos = [], 0
    for t in a:
        starts.append(pos)
        pos += len(t)
    starts.append(pos)
    out = []
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
        if tag != "equal":
            out.append((starts[i1], starts[i2], "".join(b[j1:j2])))
    return out


def _rpr(run):
    from lxml import etree
    pr = run._r.rPr
    return b"" if pr is None else etree.tostring(pr)


def _edit_paragraph(par, a, b, repl):
    """Apply one edit inside one paragraph. Returns None on success or the reason it was skipped."""
    runs = par.runs
    if "".join(r.text for r in runs) != par.text:
        return "the paragraph contains links or fields"
    spans, pos = [], 0
    for r in runs:
        spans.append((pos, pos + len(r.text), r))
        pos += len(r.text)
    if a == b:                                                   # pure insertion
        for s, e, r in spans:
            if s < a <= e or (a == 0 and s == 0):
                r.text = r.text[:a - s] + repl + r.text[a - s:]
                return None
        return "no text run to insert into"
    touched = [(s, e, r) for s, e, r in spans if s < b and e > a]
    if not touched:
        return "no matching text run"
    if len(touched) == 1:
        s, e, r = touched[0]
        r.text = r.text[:a - s] + repl + r.text[b - s:]
        return None
    if len({_rpr(r) for _, _, r in touched}) != 1:
        return "the text runs across several formatting styles"
    (s1, _, first), (sl, _, last) = touched[0], touched[-1]
    for _, _, r in touched[1:-1]:
        r.text = ""
    tail = last.text[b - sl:]
    last.text = tail
    first.text = first.text[:a - s1] + repl
    return None


def _line_offsets(texts, sep="\n"):
    out, pos = [], 0
    for t in texts:
        out.append((pos, pos + len(t)))
        pos += len(t) + len(sep)
    return out


# ------------------------------------------------------------------------------------------------ Word
def _export_docx(data, cur_text):
    from docx import Document
    doc = Document(io.BytesIO(data))
    lines = ingest.docx_lines(doc)
    orig = "\n".join(l["text"] for l in lines)
    bounds = _line_offsets([l["text"] for l in lines])
    applied, skipped, plan = [], [], {}
    for a, b, repl in edits_between(orig, cur_text):
        old = orig[a:b]
        rec = {"old": old, "new": repl}
        if not (old.strip() or repl.strip()):
            continue                                              # whitespace only
        li = next((i for i, (s, e) in enumerate(bounds) if s <= a and b <= e), None)
        if li is None:
            skipped.append({**rec, "reason": "the change crosses paragraphs"})
            continue
        line, s0 = lines[li], bounds[li][0]
        la, lb = a - s0, b - s0
        if line["kind"] == "p":
            plan.setdefault(("p", line["para"]), []).append((la, lb, repl, rec))
            continue
        pos, hit = 0, None
        for ci, ct in enumerate(line["cells"]):
            if pos <= la and lb <= pos + len(ct):
                hit = (ci, pos)
                break
            pos += len(ct) + 3
        if hit is None:
            skipped.append({**rec, "reason": "the change crosses table cells"})
            continue
        cell = doc.tables[line["table"]].rows[line["row"]].cells[hit[0]]
        if len(cell.paragraphs) != 1:
            skipped.append({**rec, "reason": "the table cell has several paragraphs"})
            continue
        par = cell.paragraphs[0]
        lead = len(par.text) - len(par.text.lstrip())
        plan.setdefault(("c", line["table"], line["row"], hit[0]), []).append((la - hit[1] + lead, lb - hit[1] + lead, repl, rec))
    for key, items in plan.items():
        par = doc.paragraphs[key[1]] if key[0] == "p" else doc.tables[key[1]].rows[key[2]].cells[key[3]].paragraphs[0]
        for la, lb, repl, rec in sorted(items, key=lambda x: x[0], reverse=True):     # later edits first
            why = _edit_paragraph(par, la, lb, repl)
            (skipped.append({**rec, "reason": why}) if why else applied.append(rec))
    out = io.BytesIO()
    doc.save(out)
    return out.getvalue(), applied, skipped


# ------------------------------------------------------------------------------------------------ PowerPoint
_AT = re.compile(r"<a:t>(.*?)</a:t>", re.S)


def _slide_names(z):
    return sorted((n for n in z.namelist() if re.match(r"ppt/slides/slide\d+\.xml$", n)),
                  key=lambda n: int(re.search(r"(\d+)", n.rsplit("/", 1)[1]).group(1)))


def _export_pptx(data, cur_text):
    z = zipfile.ZipFile(io.BytesIO(data))
    names = _slide_names(z)
    xmls = {n: z.read(n).decode("utf-8", "ignore") for n in names}
    # the exact structure of the reader's text: "[Slide n]\n" + one line per <a:t>, slides joined by a blank line
    texts_by_slide = {}
    for idx, n in enumerate(names, 1):
        ts = [html.unescape(t) for t in _AT.findall(xmls[n])]
        texts_by_slide[n] = ts
    # rebuild offsets exactly as the reader joins them
    bounds, pos = [], 0
    for idx, n in enumerate(names, 1):
        if idx > 1:
            pos += 2
        label = f"[Slide {idx}]"
        bounds.append(("label", n, -1, pos, pos + len(label)))
        pos += len(label)
        for i, t in enumerate(texts_by_slide[n]):
            pos += 1
            bounds.append(("t", n, i, pos, pos + len(t)))
            pos += len(t)
    orig = "\n\n".join(f"[Slide {idx}]\n" + "\n".join(texts_by_slide[n]) for idx, n in enumerate(names, 1))
    applied, skipped, plan = [], [], {}
    for a, b, repl in edits_between(orig, cur_text):
        old = orig[a:b]
        rec = {"old": old, "new": repl}
        if not (old.strip() or repl.strip()):
            continue
        hit = next((x for x in bounds if x[3] <= a and b <= x[4]), None)
        if hit is None or hit[0] == "label":
            skipped.append({**rec, "reason": "the change crosses text boxes or slides"})
            continue
        plan.setdefault((hit[1], hit[2]), []).append((a - hit[3], b - hit[3], repl, rec))
    for (name, ti), items in plan.items():
        text = texts_by_slide[name][ti]
        for la, lb, repl, rec in sorted(items, key=lambda x: x[0], reverse=True):
            text = text[:la] + repl + text[lb:]
            applied.append(rec)
        texts_by_slide[name][ti] = text
        count = {"i": -1}

        def sub(m, name=name):
            count["i"] += 1
            return f"<a:t>{escape(texts_by_slide[name][count['i']])}</a:t>" if count["i"] == ti else m.group(0)
        xmls[name] = _AT.sub(sub, xmls[name])
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zo:
        for item in z.infolist():
            zo.writestr(item, xmls[item.filename].encode("utf-8") if item.filename in xmls else z.read(item.filename))
    return out.getvalue(), applied, skipped


def export_corrected(fmt, data, cur_text):
    """Return (file_bytes, report). Raises AppError when there is nothing to export."""
    if fmt not in FORMATS:
        raise AppError("Corrected-file export works for Word (.docx) and PowerPoint (.pptx) files.", 415)
    orig = ingest.extract("x." + fmt, data)["text"]
    if orig == cur_text:
        raise AppError("There are no text changes to write into the file yet. Accept fixes and apply them first.", 409)
    blob, applied, skipped = (_export_docx if fmt == "docx" else _export_pptx)(data, cur_text)
    return blob, {"applied": applied, "skipped": skipped, "total": len(applied) + len(skipped)}
