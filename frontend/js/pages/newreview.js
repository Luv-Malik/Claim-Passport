import { h, raw, api, form, act, later, $, $$, icon, toast, state } from "../util.js";

const SAMPLES = {
  "Wrong price and hype": ["Launch post", "text", "Lumio Invoice is the best invoicing app in India! Plans start at Rs. 599 per month. Try it free for 30 days. Guys, it is AMAZING!!!"],
  "Clean example": ["Pricing update", "text", "The Starter plan costs Rs. 499 per month, and every new account gets a 14-day free trial. Terms apply."],
  "HTML with problems": ["Landing page snippet", "html", '<style>.hero{font-family:"Comic Sans MS";color:#cccccc;background:#ffffff}</style>\n<div class="hero"><h1>Invoices without stress</h1><img src="hero.png"><a href="/demo">click here</a></div>'],
};
let picked = null;

form("new", async (fd, f) => {
  const btn = f.querySelector("button.primary"); btn.disabled = true; btn.textContent = "Checking...";
  try {
    const body = new FormData(f);
    let r;
    if (picked) { body.set("file", picked); r = await api("/api/contents", { form: body }); }
    else r = await api("/api/contents", { body: { title: fd.title, channel: fd.channel, fmt: fd.fmt, text: fd.text, ai_assisted: !!fd.ai_assisted } });
    location.hash = "#/content/" + r.id;
  } finally { btn.disabled = false; btn.innerHTML = "Check my content"; }
});
act("sample", el => { const [t, fmt, text] = SAMPLES[el.dataset.k]; const f = $("form[data-form=new]"); f.title.value = t; f.fmt.value = fmt; f.text.value = text; f.text.dispatchEvent(new Event("input")); showTab("paste"); });
act("ntab", el => showTab(el.dataset.t));
act("pickfile", () => $("#filein").click());
act("clearfile", () => { picked = null; paintFile(); });
function showTab(t) { $$("[data-ntab]").forEach(x => x.classList.toggle("hide", x.dataset.ntab !== t)); $$("[data-act=ntab]").forEach(b => b.classList.toggle("on", b.dataset.t === t)); if (t === "paste") picked = null, paintFile(); }
function setFile(f) { picked = f; const t = $("form[data-form=new]").title; if (!t.value) t.value = f.name.replace(/\.[^.]+$/, ""); paintFile(); }
function paintFile() {
  const el = $("#fileinfo"); if (!el) return;
  el.innerHTML = picked ? h`<div class="note row sp" style="margin-top:12px"><span>${icon("file")} <b>${picked.name}</b> <span class="muted">(${Math.round(picked.size / 1024)} KB)</span></span><button type="button" class="btn small ghost" data-act="clearfile">Remove</button></div>`.s : "";
}

export default async function () {
  later(() => {
    const ta = $("textarea[name=text]"), cnt = $("#count");
    ta.oninput = () => { const w = (ta.value.match(/\S+/g) || []).length; cnt.textContent = `${w} words · ${ta.value.length} characters`; };
    const dz = $("#drop"), fi = $("#filein");
    fi.onchange = () => { if (fi.files[0]) setFile(fi.files[0]); };
    ["dragover", "dragenter"].forEach(ev => dz.addEventListener(ev, e => { e.preventDefault(); dz.classList.add("over"); }));
    ["dragleave", "drop"].forEach(ev => dz.addEventListener(ev, e => { e.preventDefault(); dz.classList.remove("over"); }));
    dz.addEventListener("drop", e => { if (e.dataTransfer.files[0]) setFile(e.dataTransfer.files[0]); });
    showTab("paste");
  });
  picked = null;
  return h`<div style="margin-bottom:16px"><h1>New review</h1><div class="muted">Paste your content or upload a file. We check it against your approved facts and brand rules. Nothing is changed or published automatically.</div></div>
    <div class="grid g21"><div class="card"><form data-form="new"><div class="grid g3"><div><label>Title</label><input name="title" required placeholder="Launch blog post"></div>
        <div><label>Channel</label><select name="channel">${["website", "social", "email", "ads", "print", "other"].map(c => h`<option>${c}</option>`)}</select></div>
        <div><label>Pasted text format</label><select name="fmt"><option value="text">Plain text</option><option value="markdown">Markdown</option><option value="html">HTML</option></select></div></div>
      <div class="tabs"><button type="button" class="on" data-act="ntab" data-t="paste">${icon("edit")}Paste text</button><button type="button" data-act="ntab" data-t="upload">${icon("upload")}Upload a file</button></div>
      <div data-ntab="paste"><textarea name="text" placeholder="Paste text, markdown or HTML here..." style="min-height:220px"></textarea><div class="tiny muted" id="count" style="margin-top:6px">0 words</div></div>
      <div data-ntab="upload" class="hide"><div class="dropzone" id="drop" data-act="pickfile"><div style="color:var(--brand)">${icon("upload")}</div><b>Drop a file here or click to browse</b><div class="small muted">txt, md, html, pdf, docx, pptx, png, jpg, webp (up to ${10} MB)</div></div>
        <input type="file" id="filein" class="hide" accept=".txt,.md,.html,.htm,.pdf,.docx,.pptx,.png,.jpg,.jpeg,.webp"><div id="fileinfo"></div>
        <label>Alt text (for image uploads)</label><input name="alt_text" placeholder="Describe the image in one short sentence"></div>
      <label class="inline"><input type="checkbox" name="ai_assisted"> This content was written with help from an AI tool</label>
      <button class="btn primary" style="margin-top:8px;padding:11px 22px">Check my content</button></form></div>
    <div class="col"><div class="card"><div class="card-h">${icon("zap")}<h3>Try a sample</h3></div><div class="small muted" style="margin-bottom:10px">Load an example to see how findings look.</div>
        <div class="col">${Object.keys(SAMPLES).map(k => h`<button type="button" class="btn ghost" data-act="sample" data-k="${k}" style="justify-content:flex-start">${icon("file")}${k}</button>`)}</div></div>
      <div class="card"><div class="card-h">${icon("shield")}<h3>What we check</h3></div><div class="small col"><div>✓ Numbers and claims against approved facts</div><div>✓ Tone, terminology, messaging</div><div>✓ Accessibility and visual consistency</div><div>✓ Text inside images (OCR)</div></div></div></div></div>`;
}
