import { h, raw, state, api, act, change, form, later, modal, toast, $, $$, icon, pill, isManager, isPriv, daysText, fmtDate, qs, CAT, CAT_COLOR } from "../util.js";
import { life } from "../charts.js";

const edit = () => isManager();
function factModal(f) {
  const v = k => (f && f[k] != null ? f[k] : "");
  modal({ title: f ? "Edit fact: " + f.key : "Add approved fact", wide: true, submit: "Save", onSubmit: async fd => {
      const body = { ...fd, confidential: !!fd.confidential, review_interval_days: Number(fd.review_interval_days) || 90 }; if (f) delete body.key;
      const r = f ? await api("/api/vault/facts/" + f.id, { method: "PUT", body }) : await api("/api/vault/facts", { body });
      toast(f && r.proposals_created ? `Saved. ${r.proposals_created} published page(s) now need a fix.` : "Saved."); window.render(); },
    body: h`<div class="grid g2"><div><label>Key</label><input name="key" value="${v("key")}" ${f ? raw("readonly") : raw("required")}></div><div><label>Category</label><input name="category" value="${v("category") || "general"}"></div></div>
      <label>Statement (what is true)</label><input name="statement" value="${v("statement")}" required>
      <div class="grid g2"><div><label>Value as written (used in fixes)</label><input name="value" value="${v("value")}"></div><div><label>Owner</label><input name="owner" value="${v("owner")}"></div>
      <div><label>Source document</label><input name="source_doc" value="${v("source_doc")}"></div><div><label>Page or section</label><input name="source_ref" value="${v("source_ref")}"></div>
      <div><label>Verified on</label><input type="date" name="verified_on" value="${fmtDate(v("verified_on"))}"></div><div><label>Expires on</label><input type="date" name="expires_on" value="${fmtDate(v("expires_on"))}"></div>
      <div><label>Review every (days)</label><input name="review_interval_days" value="${v("review_interval_days") || 90}"></div><div><label>Search keywords</label><input name="keywords" value="${v("keywords")}"></div></div>
      <label class="inline"><input type="checkbox" name="confidential" ${f && f.confidential ? raw("checked") : ""}> Confidential (hidden from writers and the public feed)</label>` });
}
change("logo-up", async el => { const fd = new FormData(); fd.append("file", el.files[0]); await api("/api/vault/logo", { form: fd }); toast("Logo saved."); window.render(); });
act("logo-del", async () => { await api("/api/vault/logo", { method: "DELETE" }); window.render(); });
act("fact-new", () => factModal(null));
act("fact-edit", async el => { const { facts } = await api("/api/vault/facts"); factModal(facts.find(f => f.id == el.dataset.id)); });
act("fact-history", async el => { const { history } = await api(`/api/vault/facts/${el.dataset.id}/history`);
  modal({ title: "Fact history", wide: true, body: h`<div class="timeline">${history.map(x => h`<div class="tl"><b>Version ${x.version}</b> <span class="tiny muted">${x.changed_by} · ${fmtDate(x.changed_at)}</span><div>${x.statement}</div><div class="tiny muted">${x.note}</div></div>`)}</div>` }); });
act("glossary-del", async el => { await api("/api/vault/glossary/" + el.dataset.id, { method: "DELETE" }); window.render(); });
act("copyhex", async el => { try { await navigator.clipboard.writeText(el.dataset.hex); toast("Copied " + el.dataset.hex); } catch (e) { toast(el.dataset.hex); } });
act("fcat", el => { $$("[data-act=fcat]").forEach(c => c.classList.toggle("on", c === el)); factFilter(); });
act("sample-guide", () => { $("textarea[name=markdown]").value = '## Tone\n- [T-9] Avoid filler words. avoid: "basically", "literally" use: "in short", "truly" severity: low ref: Brand Guidelines v3, section 1.4\n\n## Claims\n- [C-9] Never quote customer numbers without a source. lock: yes'; $("textarea[name=markdown]").dispatchEvent(new Event("input")); });
function factFilter() {
  const q = ($("#fsearch")?.value || "").toLowerCase(), cat = $("[data-act=fcat].on")?.dataset.k || "";
  $$("[data-fact]").forEach(c => c.classList.toggle("hide", !(c.dataset.fact.includes(q) && (!cat || c.dataset.cat === cat))));
}
change("rule", async el => {
  const f = el.dataset.field, body = f === "severity" ? { severity: el.value } : f === "lock" ? { human_lock: el.checked } : { active: el.checked };
  try { await api("/api/vault/rules/" + el.dataset.code, { method: "PUT", body }); toast("Rule updated."); } catch (e) { toast(e.message, true); window.render(); }
});
form("glossary", async fd => { await api("/api/vault/glossary", { body: { preferred: fd.preferred, banned: fd.banned.split(","), case_sensitive: !!fd.case_sensitive } }); window.render(); });
form("import", async fd => { const r = await api("/api/vault/guidelines/import", { body: fd }); toast(`Imported: ${r.created} new, ${r.updated} updated rule(s).`); location.hash = "#/vault?tab=rules"; });

export default async function () {
  const tab = qs().get("tab") || "facts";
  const tabs = [["facts", "Approved facts", "shield"], ["rules", "Rules", "flag"], ["glossary", "Glossary", "tag"], ["assets", "Assets", "layers"], ["import", "Import guidelines", "upload"]];
  let body = "";
  if (tab === "facts") {
    const { facts } = await api("/api/vault/facts");
    const cats = [...new Set(facts.map(f => f.category))];
    later(() => { const s = $("#fsearch"); if (s) s.oninput = factFilter; });
    body = h`<div class="row sp" style="margin-bottom:14px"><div class="row" style="flex:1"><div style="position:relative;flex:1;max-width:360px"><input id="fsearch" placeholder="Search facts..." style="padding-left:38px"><span style="position:absolute;left:11px;top:9px;color:var(--muted)">${icon("search")}</span></div>
      <button class="chip on" data-act="fcat" data-k="">All</button>${cats.map(c => h`<button class="chip" data-act="fcat" data-k="${c}">${c}</button>`)}</div>${edit() ? h`<button class="btn primary" data-act="fact-new">${icon("plus")}Add fact</button>` : ""}</div>
      <div class="grid g3">${facts.map(f => { const pct = 100 * (f.days_left ?? 0) / Math.max(f.review_interval_days || 90, 1);
        return h`<div class="card tight" data-fact="${(f.key + " " + f.statement).toLowerCase()}" data-cat="${f.category}"><div class="row sp"><b>${f.key}</b><div class="row" style="gap:5px">${f.confidential ? h`<span class="pill lock">${icon("lock")}confidential</span>` : ""}<span class="pill">${f.category}</span></div></div>
          <div style="margin:8px 0">${f.statement}</div><div class="tiny muted">${f.source_doc} ${f.source_ref} · ${f.owner}</div>
          <div style="margin:10px 0 4px"><div class="row sp tiny muted"><span>Valid until ${fmtDate(f.expires_on)}</span><span>${daysText(f.days_left)}</span></div>${life(pct, f.days_left < 0 ? "#d64545" : f.days_left <= 14 ? "#e3a008" : "#1fa463")}</div>
          <div class="row sp" style="margin-top:10px"><span class="tiny muted">v${f.version} · used in ${f.live_uses} live claim(s)</span><div class="row" style="gap:6px">${edit() ? h`<button class="btn small ghost" data-act="fact-edit" data-id="${f.id}">Edit</button>` : ""}${isPriv() ? h`<button class="btn small ghost" data-act="fact-history" data-id="${f.id}">History</button>` : ""}</div></div></div>`; })}</div>`;
  } else if (tab === "rules") {
    const { rules } = await api("/api/vault/rules");
    const groups = Object.keys(CAT).map(k => [k, rules.filter(r => r.category === k)]).filter(([, l]) => l.length);
    body = h`${groups.map(([k, list]) => h`<h3 style="margin-top:18px;color:${CAT_COLOR[k]}">${CAT[k]}</h3><table><tbody>${list.map(r => h`<tr><td style="width:70px"><b>${r.code}</b></td><td>${r.title}<div class="tiny muted">${r.guideline_ref}${r.kind === "note" ? " · documentation only" : ""}</div></td>
      <td style="width:130px">${edit() ? h`<select data-change="rule" data-field="severity" data-code="${r.code}">${["low", "medium", "high"].map(s => h`<option ${r.severity === s ? raw("selected") : ""}>${s}</option>`)}</select>` : pill(r.severity, r.severity)}</td>
      <td style="width:120px" class="small"><label class="inline" style="margin:0">${edit() ? h`<input type="checkbox" data-change="rule" data-field="lock" data-code="${r.code}" ${r.human_lock ? raw("checked") : ""}>` : ""}${r.human_lock ? "needs a person" : "auto"}</label></td>
      <td style="width:90px">${edit() ? h`<label class="inline" style="margin:0"><input type="checkbox" data-change="rule" data-field="active" data-code="${r.code}" ${r.active ? raw("checked") : ""}>on</label>` : pill(r.active ? "green" : "", r.active ? "on" : "off")}</td></tr>`)}</tbody></table>`)}`;
  } else if (tab === "glossary") {
    const { glossary } = await api("/api/vault/glossary");
    body = h`${edit() ? h`<form data-form="glossary" class="row" style="margin-bottom:14px"><input name="preferred" placeholder="Preferred term" required style="max-width:200px"><input name="banned" placeholder="Terms to avoid (comma separated)" required style="max-width:320px"><label class="inline" style="margin:0"><input type="checkbox" name="case_sensitive">match case</label><button class="btn">Add</button></form>` : ""}
      <table><thead><tr><th>Use this</th><th>Instead of</th><th>Note</th>${edit() ? h`<th></th>` : ""}</tr></thead><tbody>${glossary.map(g => h`<tr><td><b>${g.preferred}</b></td><td>${g.banned.map(b => h`<span class="pill red" style="margin:2px">${b}</span>`)}</td><td class="small muted">${g.note}</td>${edit() ? h`<td><button class="btn small ghost" data-act="glossary-del" data-id="${g.id}">Delete</button></td>` : ""}</tr>`)}</tbody></table>`;
  } else if (tab === "assets") {
    const { assets } = await api("/api/vault/assets");
    const logoA = assets.find(a => a.name === "logo"), hasLogo = !!(logoA && logoA.value && logoA.value.has_image);
    if (hasLogo) later(async () => { try { const r = await fetch("/api/vault/logo", { headers: { Authorization: "Bearer " + state.token } }); const im = $("#logoimg"); if (r.ok && im) im.src = URL.createObjectURL(await r.blob()); } catch (e) { /* preview is optional */ } });
    body = h`<div style="margin-bottom:20px"><h3>Brand logo</h3><div class="row">${hasLogo ? h`<img id="logoimg" alt="Approved logo" style="height:64px;background:#fff;border:1px solid var(--line);border-radius:8px;padding:6px">` : h`<span class="muted small">No logo uploaded. Without one, the logo check (V-4) is skipped.</span>`}
      ${edit() ? h`<label class="btn small ghost" style="margin:0">${icon("upload")}${hasLogo ? "Replace logo" : "Upload logo"}<input type="file" accept="image/png,image/jpeg,image/webp" data-change="logo-up" hidden></label>${hasLogo ? h`<button class="btn small ghost" data-act="logo-del">Remove</button>` : ""}` : ""}</div>
      <div class="tiny muted" style="margin-top:6px">Images are searched for this logo at different sizes. Slides and PDF pages are not searched.</div></div>
    ${assets.filter(a => a.name !== "logo").map(a => h`<div style="margin-bottom:20px"><h3>${a.name === "palette" ? "Brand colours" : a.name === "fonts" ? "Brand fonts" : "Image rules"}</h3>
      ${a.name === "palette" ? h`<div>${a.value.map(c => h`<span class="swatch" data-act="copyhex" data-hex="${c.hex}" data-tip="Click to copy"><i style="background:${c.hex}"></i><span>${c.name}<div class="tiny muted">${c.hex}</div></span></span>`)}</div>`
        : a.name === "fonts" ? h`<div class="row">${a.value.map(f => h`<span class="card tight" style="font-family:${f};font-size:22px">${f}<div class="tiny muted" style="font-family:Inter,sans-serif">Aa Bb Cc 123</div></span>`)}</div>`
        : h`<div class="small">Minimum width: <b>${a.value.min_width}px</b> · Allowed width-to-height ratios: ${(a.value.ratios || []).map(r => h`<span class="pill">${r.toFixed(2)}</span> `)}</div>`}</div>`)}
      <div class="note small">Visual checks use these assets. ${edit() ? "Edit them with PUT /api/vault/assets/&lt;name&gt; (see docs/API.md)." : ""}</div>`;
  } else {
    later(() => { const t = $("textarea[name=markdown]"); if (t) t.oninput = () => { $("#ruledet").textContent = (t.value.match(/^\s*[-*]\s*\[[A-Za-z]+-?\d+[A-Za-z]*\]/gm) || []).length + " rule line(s) detected"; }; });
    body = edit() ? h`<form data-form="import"><div class="grid g2"><div><label>Guideline title</label><input name="title" value="Brand Guidelines" required></div><div><label>Version</label><input name="version" value="1"></div></div>
      <label>Guidelines (markdown)</label><textarea name="markdown" style="min-height:240px" placeholder='## Tone&#10;- [T-9] No slang. avoid: "cool" use: "great" severity: low'></textarea><div class="row sp" style="margin:8px 0"><span class="tiny muted" id="ruledet">0 rule line(s) detected</span><button type="button" class="btn small ghost" data-act="sample-guide">Insert an example</button></div>
      <div class="note">Rule lines look like <code>- [CODE] Title. avoid: "a" use: "b" severity: low lock: yes</code>. Rules with <code>avoid:</code> become automatic checks. See docs/GUIDELINE_FORMAT.md.</div><button class="btn primary" style="margin-top:12px">Import rules</button></form>` : h`<div class="empty">Only managers and admins can import guidelines.</div>`;
  }
  return h`<div style="margin-bottom:6px"><h1>Brand Vault</h1><div class="muted">Everything the checker trusts: approved facts, rules, words and brand assets.</div></div>
    <div class="tabs">${tabs.map(([k, l, ic]) => h`<a href="#/vault?tab=${k}" class="${tab === k ? "on" : ""}">${icon(ic)}${l}</a>`)}</div><div class="card">${body}</div>`;
}
