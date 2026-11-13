import { h, raw, esc, state, api, act, later, modal, toast, $, $$, icon, pill, statusPill, avatar, fmtDate, fmtTime, daysText, CAT, CAT_COLOR, scoreColor, isManager, closeOverlay, form } from "../util.js";
import { gauge, radar, donut, legend, stepper } from "../charts.js";
import { okArt } from "../art.js";

let pdfPage = 1, tab = "comments", FL = "all", focusId = null;
const reload = () => window.render();
const cid = () => state.ws.content.id;

// ---------------------------------------------------------------- document with highlights
function highlight(text, findings) {
  const spans = findings.filter(f => f.span_end > f.span_start).sort((a, b) => a.span_start - b.span_start);
  let out = "", pos = 0;
  for (const f of spans) {
    if (f.span_start < pos) continue;
    out += esc(text.slice(pos, f.span_start));
    out += `<mark class="hl ${f.decision !== "open" ? "done" : f.severity}" data-act="focus" data-f="${f.id}" data-tip="${esc(f.rule_code)}: ${esc(f.message.slice(0, 90))}">${esc(text.slice(f.span_start, f.span_end))}</mark>`;
    pos = f.span_end;
  }
  return out + esc(text.slice(pos));
}

// ---------------------------------------------------------------- finding card
function findingCard(f, d) {
  const can = d.actions.decide, done = f.decision !== "open", text = d.text;
  const sugg = f.suggestions.map((s, i) => {
    const sp = s.span || [f.span_start, f.span_end];
    const before = text.slice(sp[0], sp[1]), after = s.replacement;
    return h`<div class="sugg"><div class="row sp"><b>${s.label}</b>${s.kind === "replace" ? "" : pill("", "advice")}</div>
      ${s.kind === "replace" ? h`<div class="ba"><div class="b">${before.length > 70 ? before.slice(0, 70) + "..." : before || "(insert)"}</div><span class="muted">${icon("arrow")}</span><div class="a">${after === "" ? "(removed)" : after.length > 90 ? after.slice(0, 90) + "..." : after}</div></div>` : ""}
      <div class="tiny muted">${s.rationale}</div>
      ${can && !done ? h`<button class="btn small teal" data-act="decide" data-id="${f.id}" data-d="accepted" data-i="${i}" style="margin-top:8px">${s.kind === "replace" ? "Use this fix" : "Got it, I will handle this"}</button>` : ""}</div>`;
  });
  return h`<div class="finding ${done ? "done" : f.severity}" id="f${f.id}" data-f="${f.id}" data-open="${done ? 0 : 1}" data-sev="${f.severity}" data-cat="${f.category}" data-lock="${f.human_lock ? 1 : 0}">
    <div class="row sp"><div class="row" style="gap:6px">${pill(f.severity, f.severity)}<span class="pill" style="color:${CAT_COLOR[f.category]}">${CAT[f.category] || f.category}</span><span class="tiny muted">${f.rule_code}</span></div>
      <div class="row" style="gap:6px">${f.human_lock ? h`<span class="pill lock" data-tip="A reviewer must decide on this one">${icon("lock")}Needs a person</span>` : ""}<span class="pill ${f.confidence === "high" ? "green" : f.confidence === "medium" ? "amber" : "red"}" data-tip="How sure the checker is">${f.confidence}</span></div></div>
    ${f.excerpt ? h`<div style="margin:9px 0 4px"><span class="ex">${f.excerpt.length > 90 ? f.excerpt.slice(0, 90) + "..." : f.excerpt}</span></div>` : ""}
    <div style="margin-top:4px">${f.message}</div>
    <div class="src">${icon(f.source_type === "fact" ? "shield" : "book")}<span><b>${f.source_type === "fact" ? "Approved fact" : "Guideline"}:</b> ${f.source_ref}${f.produced_by === "rules+llm" ? " · includes AI rewrite ideas" : ""}${f.produced_by === "rules+ai-judge" ? " · AI-assisted finding (cited)" : f.produced_by === "semantic" ? " · found by meaning match" : ""}</span></div>
    ${done ? h`<div class="note"><div class="row sp"><span>${pill(f.decision, f.decision)} by <b>${f.decision_by_name || "someone"}</b>${f.decision_reason ? ": " + f.decision_reason : ""}</span>${can ? h`<button class="btn small ghost" data-act="decide" data-id="${f.id}" data-d="open">Undo</button>` : ""}</div>
        ${f.final_text != null ? h`<div class="small" style="margin-top:6px">Will change to: <span class="ex">${f.final_text === "" ? "(removed)" : f.final_text}</span></div>` : ""}</div>`
      : h`${sugg}${can ? h`<div class="row" style="margin-top:12px"><button class="btn small ghost" data-act="edit-finding" data-id="${f.id}" data-ex="${f.excerpt}">${icon("edit")}Write my own</button><button class="btn small ghost" data-act="reject-finding" data-id="${f.id}">Keep as written</button></div>` : ""}`}</div>`;
}

// ---------------------------------------------------------------- tabs
function tabBody(d) {
  if (tab === "comments") return h`<div class="card">${d.comments.length ? d.comments.map(m => h`<div class="comment">${avatar(m.author, 34)}<div><b>${m.author}</b> <span class="tiny muted">${fmtTime(m.created_at)}</span><div>${m.body}</div></div></div>`) : h`<div class="muted small">No comments yet. Ask a question or leave guidance for the writer.</div>`}
      <form data-form="comment" class="row" style="margin-top:12px;flex-wrap:nowrap"><input name="body" placeholder="Write a comment..." required><button class="btn">${icon("send")}Post</button></form></div>`;
  if (tab === "versions") return h`<div class="card"><div class="timeline">${d.versions.map(v => h`<div class="tl"><div class="row sp"><div><b class="tt">Version ${v.version}</b> <span class="muted small">${v.note}</span><div class="tiny muted">${v.author || ""} · ${fmtDate(v.created_at)}</div></div>
      ${v.version > 1 ? h`<button class="btn small ghost" data-act="diff" data-v="${v.version}">${icon("eye")}Compare with v${v.version - 1}</button>` : ""}</div></div>`)}</div><div id="diffbox"></div></div>`;
  if (tab === "passports") return h`<div class="card">${d.passports.length ? h`<table><tbody>${d.passports.map(p => h`<tr><td style="width:150px">${pill(p.color, p.label)}</td><td>${p.claim_text}<div class="tiny muted">${p.fact_key ? "Source: " + p.fact_key : "Approved without a verified source"}</div></td><td class="small muted">${p.days_left != null ? daysText(p.days_left) : ""}</td></tr>`)}</tbody></table>` : h`<div class="muted small">Claim passports are created when this content is published.</div>`}</div>`;
  if (tab === "approvals") return h`<div class="card">${d.approvals.length ? d.approvals.map(a => h`<div class="comment">${avatar(a.reviewer, 34)}<div>${pill(a.decision === "approved" ? "green" : "amber", a.decision.replace("_", " "))} <b>${a.reviewer}</b> on v${a.version} <span class="tiny muted">${fmtDate(a.created_at)}</span><div>${a.note}</div></div></div>`) : h`<div class="muted small">No review decisions yet.</div>`}</div>`;
  return h`<div class="card"><div id="tbox" class="muted">Loading...</div></div>`;
}
async function loadTransparency() {
  const box = $("#tbox"); if (!box) return;
  const t = await api(`/api/contents/${cid()}/transparency`);
  box.className = "";
  box.innerHTML = h`<div class="note">${state.meta.disclosure}</div><div class="row" style="margin:12px 0">${pill(t.llm_enabled ? "amber" : "green", t.llm_enabled ? "AI rewrite ideas: on" : "AI rewrite ideas: off (nothing leaves the server)")}${pill(t.ai_assisted ? "amber" : "", t.ai_assisted ? "Marked AI-assisted by the writer" : "Not marked AI-assisted")}</div>
    <table><thead><tr><th>When</th><th>Step</th><th>Engine</th><th>What was sent</th></tr></thead><tbody>${t.events.map(e => h`<tr><td class="small">${fmtTime(e.ts)}</td><td>${e.step}</td><td>${e.engine} <span class="tiny muted">${e.model}</span></td><td class="small">${e.data_sent}${e.masked_items ? ` (${e.masked_items} personal item(s) masked)` : ""}</td></tr>`)}</tbody></table>`.s;
}

// ---------------------------------------------------------------- filters and focus
function applyFilter() {
  $$("#flist .finding").forEach(el => {
    const k = FL; let show = true;
    if (k === "open") show = el.dataset.open === "1"; else if (k === "high") show = el.dataset.sev === "high"; else if (k === "lock") show = el.dataset.lock === "1"; else if (k.startsWith("cat:")) show = el.dataset.cat === k.slice(4);
    el.classList.toggle("hide", !show);
  });
  $$("[data-act=fl]").forEach(c => c.classList.toggle("on", c.dataset.k === FL));
}
function focusFinding(id, scroll = true) {
  focusId = Number(id);
  $$(".focus").forEach(x => x.classList.remove("focus"));
  const card = document.getElementById("f" + id); if (card) { card.classList.add("focus"); if (scroll) card.scrollIntoView({ behavior: "smooth", block: "center" }); }
  $$(`mark[data-f="${id}"]`).forEach(x => { x.classList.add("focus"); });
}
const visibleCards = () => $$("#flist .finding").filter(c => !c.classList.contains("hide"));
function step(dir) {
  const cards = visibleCards().filter(c => c.dataset.open === "1"); if (!cards.length) return toast("Nothing left to decide here.");
  const i = cards.findIndex(c => Number(c.dataset.f) === focusId);
  const next = cards[(i + dir + cards.length) % cards.length];
  focusFinding(next.dataset.f);
  const mk = document.querySelector(`mark[data-f="${next.dataset.f}"]`); if (mk) mk.scrollIntoView({ block: "nearest", behavior: "smooth" });
}

// ---------------------------------------------------------------- actions
act("focus", el => focusFinding(el.dataset.f));
act("fl", el => { FL = el.dataset.k; applyFilter(); });
act("next-issue", () => step(1));
act("wtab", el => { tab = el.dataset.t; $$("[data-act=wtab]").forEach(b => b.classList.toggle("on", b === el)); $("#tabbody").innerHTML = tabBody(state.ws).s; if (tab === "transparency") loadTransparency(); });
act("decide", async el => {
  const body = { decision: el.dataset.d }; if (el.dataset.i !== undefined) body.suggestion_index = Number(el.dataset.i);
  await api(`/api/findings/${el.dataset.id}/decision`, { body }); reload();
});
act("edit-finding", el => modal({ title: "Write your own fix", submit: "Save my fix", onSubmit: async fd => { await api(`/api/findings/${el.dataset.id}/decision`, { body: { decision: "edited", final_text: fd.final_text } }); reload(); },
  body: h`<p class="muted small">Replace the highlighted text with your own wording.</p><label>Your text</label><textarea name="final_text" style="min-height:90px">${el.dataset.ex}</textarea>` }));
act("reject-finding", el => modal({ title: "Keep this wording", submit: "Keep it", onSubmit: async fd => { await api(`/api/findings/${el.dataset.id}/decision`, { body: { decision: "rejected", reason: fd.reason } }); reload(); },
  body: h`<p class="muted small">Tell the reviewer why this wording is right. Your reason also helps the brand team find rules that are unclear.</p><label>Reason</label><textarea name="reason" required style="min-height:90px"></textarea>` }));
act("fix-easy", () => {
  const easy = state.ws.findings.filter(f => f.decision === "open" && !f.human_lock && f.suggestions[0] && f.suggestions[0].kind === "replace");
  if (!easy.length) return toast("No easy fixes left. The rest need your judgement.");
  modal({ title: `Apply ${easy.length} easy fix(es)?`, submit: "Apply them", body: h`<p>This accepts the first suggested fix for every finding that does not need a reviewer. You can undo any of them afterwards.</p><div class="note small">${easy.slice(0, 6).map(f => h`<div>• ${f.rule_code}: ${f.excerpt || "(whole item)"} → ${f.suggestions[0].replacement === "" ? "(remove)" : f.suggestions[0].replacement}</div>`)}${easy.length > 6 ? `<div>...and ${easy.length - 6} more</div>` : ""}</div>`,
    onSubmit: async () => { for (const f of easy) await api(`/api/findings/${f.id}/decision`, { body: { decision: "accepted", suggestion_index: 0 } }); toast(`${easy.length} fixes accepted.`); reload(); } });
});
act("apply", async () => { const r = await api(`/api/contents/${cid()}/apply`, { method: "POST", body: {} }); toast(`Created version ${r.version}.` + (r.skipped.length ? ` ${r.skipped.length} overlapping change(s) skipped.` : "")); reload(); });
act("submit", async () => { await api(`/api/contents/${cid()}/submit`, { body: {} }); toast("Sent for review."); reload(); });
act("approve", () => modal({ title: "Approve this content", submit: "Approve", onSubmit: async fd => { await api(`/api/contents/${cid()}/approve`, { body: { note: fd.note } }); toast("Approved."); reload(); },
  body: h`<label>Note (optional)</label><textarea name="note" style="min-height:80px"></textarea>` }));
act("request-changes", () => modal({ title: "Request changes", submit: "Send back", onSubmit: async fd => { await api(`/api/contents/${cid()}/request-changes`, { body: { note: fd.note } }); reload(); },
  body: h`<label>What should change?</label><textarea name="note" required style="min-height:100px"></textarea>` }));
act("publish", () => modal({ title: "Publish this content?", submit: "Publish", onSubmit: async () => { await api(`/api/contents/${cid()}/publish`, { body: {} }); toast("Published. Claim passports created."); reload(); },
  body: h`<p>A claim passport will be created for every verified claim, linking it to its approved source.</p>` }));
act("recheck", async () => { await api(`/api/contents/${cid()}/analyze`, { body: {} }); toast("Checked again."); reload(); });
act("edit-text", () => modal({ title: "Edit text (creates a new version)", wide: true, submit: "Save new version", onSubmit: async fd => { await api(`/api/contents/${cid()}/versions`, { body: { text: fd.text, note: fd.note } }); reload(); },
  body: h`<label>Text</label><textarea name="text" style="min-height:320px">${state.ws.text}</textarea><label>What did you change?</label><input name="note" value="Edited by hand">` }));
act("pdf-page", async el => { pdfPage = Number(el.dataset.p); await loadPdf(); });
act("export-docx", async () => {
  const rep = await api(`/api/contents/${cid()}/export/report`);
    modal({ title: "Download corrected file", submit: "Download", wide: true, body: h`<p>${rep.applied.length} of ${rep.total} change(s) can be written into your original file with its formatting kept.</p>
    ${rep.skipped.length ? h`<div class="warn"><b>${rep.skipped.length} change(s) were not applied</b> because they could not be placed safely:<ul>${rep.skipped.map(x => h`<li class="small">${x.reason || ""}: “${x.old}” → “${x.new}”</li>`)}</ul>Please make these by hand.</div>` : ""}`,
    onSubmit: async () => { const r = await fetch(`/api/contents/${cid()}/export`, { headers: { Authorization: "Bearer " + state.token } });
      if (!r.ok) throw new Error((await r.json()).error); const u = URL.createObjectURL(await r.blob()); const a = document.createElement("a");
      a.href = u; a.download = (state.ws.content.filename || "content").replace(/(\.\w+)?$/, "-corrected$1"); a.click(); URL.revokeObjectURL(u); } });
});
async function loadPdf() {
  const box = $("#pdfbox"); if (!box) return;
  box.innerHTML = '<div class="skeleton" style="height:300px"></div>';
  try {
    const p = await api(`/api/contents/${cid()}/pages/${pdfPage}`);
    box.innerHTML = h`<div class="row sp small" style="margin-bottom:8px"><span>Page ${p.page} of ${p.pages} · ${p.outlines.length} problem(s) outlined${p.not_outlined.length ? ` · ${p.not_outlined.length} could not be placed` : ""}${p.ocr ? " · read by OCR" : ""}</span>
      <span class="row"><button class="btn small ghost" data-act="pdf-page" data-p="${p.page - 1}" ${p.page <= 1 ? raw("disabled") : ""}>Prev</button><button class="btn small ghost" data-act="pdf-page" data-p="${p.page + 1}" ${p.page >= p.pages ? raw("disabled") : ""}>Next</button></span></div>
      <div style="position:relative;display:inline-block;max-width:100%"><img src="${p.image}" alt="PDF page ${p.page}" style="max-width:100%;display:block">
      ${p.outlines.flatMap(o => o.boxes.map(bx => h`<a href="#f${o.finding_id}" data-act="pdf-focus" data-id="${o.finding_id}" title="${o.rule_code} (${o.severity})" style="position:absolute;left:${bx[0] / p.width * 100}%;top:${bx[1] / p.height * 100}%;width:${bx[2] / p.width * 100}%;height:${bx[3] / p.height * 100}%"></a>`))}</div>`.s;
  } catch (e) { box.innerHTML = h`<div class="warn">${e.message}</div>`.s; }
}
act("pdf-focus", (el, e) => { if (e) e.preventDefault(); const f = document.getElementById("f" + el.dataset.id) || document.querySelector(`[data-fid="${el.dataset.id}"]`); if (f) f.scrollIntoView({ behavior: "smooth", block: "center" }); });
act("alt-text", () => modal({ title: "Add alt text", onSubmit: async fd => { await api(`/api/contents/${cid()}/alt-text`, { body: fd }); reload(); }, body: h`<label>Describe the image in one short sentence</label><input name="alt_text" required>` }));
act("copy-text", async () => { try { await navigator.clipboard.writeText(state.ws.text); toast("Text copied."); } catch (e) { toast("Could not copy. Select the text and copy it.", true); } });
act("diff", async el => {
  const v = Number(el.dataset.v), d = await api(`/api/contents/${cid()}/diff?from=${v - 1}&to=${v}`);
  $("#diffbox").innerHTML = h`<div class="doc diff" style="margin-top:12px">${d.ops.map(o => o.op === "equal" ? o.new : h`${o.old ? h`<del>${o.old}</del>` : ""}${o.new ? h`<ins>${o.new}</ins>` : ""}`)}</div>`.s;
});
act("proposal-apply", async el => { await api(`/api/proposals/${el.dataset.id}/apply`, { body: {} }); toast("A new draft was created with the fix. Review it, then submit."); reload(); });
act("proposal-dismiss", async el => { await api(`/api/proposals/${el.dataset.id}/dismiss`, { body: {} }); reload(); });
form("comment", async fd => { await api(`/api/contents/${cid()}/comments`, { body: { body: fd.body } }); const d = await api("/api/contents/" + cid()); state.ws = d; $("#tabbody").innerHTML = tabBody(d).s; });

// keyboard shortcuts while a content page is open: j/k move, a applies the first fix, r keeps wording
window.addEventListener("cp-key", ev => {
  if (!state.ws || !/^#\/content\/\d+/.test(location.hash)) return;
  const e = ev.detail; if (e.ctrlKey || e.metaKey || e.altKey) return;
  if (e.key === "j") step(1); else if (e.key === "k") step(-1);
  else if (e.key === "a" && focusId) { const f = state.ws.findings.find(x => x.id === focusId); if (f && f.decision === "open" && state.ws.actions.decide && f.suggestions[0]) { api(`/api/findings/${f.id}/decision`, { body: { decision: "accepted", suggestion_index: 0 } }).then(reload).catch(x => toast(x.message, true)); } }
  else if (e.key === "r" && focusId) { const f = state.ws.findings.find(x => x.id === focusId); if (f && f.decision === "open" && state.ws.actions.decide) ACT_REJECT(f.id); }
});
const ACT_REJECT = id => document.querySelector(`[data-act=reject-finding][data-id="${id}"]`)?.click();

// ---------------------------------------------------------------- page
export default async function (id) {
  const d = await api("/api/contents/" + id); state.ws = d; FL = "all"; focusId = null;
  const c = d.content, a = d.actions, s = d.summary || {}, counts = s.counts || {};
  const total = d.findings.length, decided = d.findings.filter(f => f.decision !== "open").length, open = total - decided;
  const pending = d.findings.filter(f => ["accepted", "edited"].includes(f.decision) && f.final_text != null).length;
  const easy = d.findings.filter(f => f.decision === "open" && !f.human_lock && f.suggestions[0] && f.suggestions[0].kind === "replace").length;
  const cats = [...new Set(d.findings.map(f => f.category))];
  const radarItems = Object.keys(CAT).map(k => ({ label: CAT[k].replace("Facts and claims", "Claims"), value: (s.category_scores || {})[k] ?? 100 }));
  const sevSegs = [["high", "#d64545"], ["medium", "#e3a008"], ["low", "#2F6DB5"]].map(([k, col]) => ({ label: k, value: counts[k] || 0, color: col }));
  let next = "";
  if (["draft", "changes_requested"].includes(c.status)) next = open ? `Decide on ${open} finding(s)${easy ? `, or use "Fix ${easy} easy ones"` : ""}.` : pending ? "Apply your accepted changes, then submit." : "Everything is decided. You can submit for review.";
  else if (c.status === "in_review") next = a.approve ? (a.blocking_count ? `${a.blocking_count} finding(s) need a person's decision before approval.` : "Read the findings, then approve or request changes.") : "Waiting for a reviewer.";
  else if (c.status === "approved") next = a.publish ? "Approved. A manager can publish now." : "Approved. Waiting for a manager to publish.";
  else next = "Published. Claim passports keep watching the sources.";
  later(() => { if (d.files && d.files.page_view) { pdfPage = 1; loadPdf(); } applyFilter(); if (tab === "transparency") loadTransparency(); });
  return h`<div class="row sp" style="align-items:flex-start;margin-bottom:6px"><div><a href="#/content" class="small">${icon("arrow")} All content</a><h1 style="margin-top:6px">${c.title}</h1>
      <div class="row">${statusPill(c.status)}<span class="muted small">${c.fmt} · version ${c.current_version} · ${c.channel} · by ${c.owner_name}</span>${c.ai_assisted ? pill("amber", "AI-assisted") : ""}${c.needs_refresh ? pill("amber", "needs refresh") : ""}</div></div>
      <div class="row">${pending ? h`<button class="btn teal" data-act="apply">${icon("check")}Apply ${pending} change(s)</button>` : ""}${d.files && d.files.export ? h`<button class="btn ghost" data-act="export-docx">${icon("upload")}Download corrected file</button>` : ""}${a.submit ? h`<button class="btn primary" data-act="submit">${icon("send")}Submit for review</button>` : ""}
        ${a.request_changes ? h`<button class="btn ghost" data-act="request-changes">Request changes</button>` : ""}${a.approve ? h`<button class="btn green" data-act="approve">${icon("check")}Approve</button>` : ""}${a.publish ? h`<button class="btn primary" data-act="publish">${icon("globe")}Publish</button>` : ""}</div></div>
    ${stepper(c.status)}
    ${d.proposals.length ? h`<div class="warn" style="margin:14px 0"><b>A fact changed after this was published.</b>${d.proposals.map(p => h`<div style="margin-top:8px">${p.message}<div class="ba"><div class="b">${p.old_text}</div><span>${icon("arrow")}</span><div class="a">${p.new_text}</div></div>
      <button class="btn small teal" data-act="proposal-apply" data-id="${p.id}">Apply fix as new draft</button> <button class="btn small ghost" data-act="proposal-dismiss" data-id="${p.id}">Dismiss</button></div>`)}</div>` : ""}
    <div class="grid g3" style="margin:16px 0">
      <div class="card" style="text-align:center"><div class="card-h"><h3>Brand score</h3></div>${gauge(s.score ?? 0, { color: scoreColor(s.score ?? 0), label: "out of 100", size: 190 })}
        <div class="row" style="justify-content:center;gap:6px">${pill("high", (counts.high || 0) + " high")}${pill("medium", (counts.medium || 0) + " medium")}${pill("low", (counts.low || 0) + " low")}</div></div>
      <div class="card" style="text-align:center"><div class="card-h"><h3>Quality by area</h3></div>${radar(radarItems, { size: 230 })}</div>
      <div class="card"><div class="card-h"><h3>Progress</h3></div><div class="row sp small"><span>${decided} of ${total} findings decided</span><b>${total ? Math.round(100 * decided / total) : 100}%</b></div>
        <div class="progress" style="margin:8px 0 14px"><i style="width:${total ? 100 * decided / total : 100}%"></i></div>
        <div class="note"><b>Next step</b><div class="small">${next}</div></div>
        <div class="small muted" style="margin-top:12px">${s.words || 0} words${s.reading_ease != null ? " · reading ease " + s.reading_ease : ""}<br>${s.claims_clean || 0} of ${s.claims_total || 0} claims fully supported<br>${counts.needs_human || 0} need a person's decision</div>
        <div class="tiny muted" style="margin-top:10px">Shortcuts: <span class="kbd">j</span> <span class="kbd">k</span> move · <span class="kbd">a</span> use first fix · <span class="kbd">r</span> keep wording</div></div></div>
    <div class="split"><div>
      <div class="card"><div class="card-h"><h2>Content</h2><div class="row right">${c.editable && a.edit ? h`<button class="btn small ghost" data-act="edit-text">${icon("edit")}Edit text</button>` : ""}${a.edit ? h`<button class="btn small ghost" data-act="recheck">${icon("refresh")}Re-check</button>` : ""}<button class="btn small ghost" data-act="copy-text">${icon("copy")}Copy</button></div></div>
        ${!c.editable ? h`<div class="note" style="margin-bottom:10px">This was read from a ${c.fmt} file. Fixes apply to the extracted text below, so you can copy the corrected text back into the original.</div>` : ""}
        ${d.meta.notice ? h`<div class="note" style="margin-bottom:10px">${d.meta.notice}</div>` : ""}${d.files && d.files.page_view ? h`<div class="card flat" style="margin-bottom:12px"><div id="pdfbox"></div></div>` : ""}
        ${d.meta.warning ? h`<div class="warn" style="margin-bottom:10px">${d.meta.warning}</div>` : ""}
        ${c.fmt === "image" ? h`<div class="small muted" style="margin-bottom:8px">${d.meta.width}x${d.meta.height}px · alt text: ${d.meta.alt_text ? "yes" : "missing"} ${a.edit ? h`<button class="btn small ghost" data-act="alt-text">Add alt text</button>` : ""}
          <div class="row" style="margin-top:8px">${(d.meta.colors || []).map(k => h`<span class="swatch" data-tip="${Math.round(k.share * 100)}% of the image"><i style="background:${k.hex}"></i>${k.hex}</span>`)}</div></div>` : ""}
        <div class="doc" id="doc">${raw(highlight(d.text, d.findings))}${!d.text ? h`<span class="muted">(no readable text)</span>` : ""}</div></div>
      <div class="tabs">${[["comments", "Comments", "users"], ["versions", "Versions", "history"], ["passports", "Passports", "shield"], ["approvals", "Approvals", "check"], ["transparency", "AI transparency", "robot"]].map(([k, l, ic]) => h`<button data-act="wtab" data-t="${k}" class="${tab === k ? "on" : ""}">${icon(ic)}${l}</button>`)}</div>
      <div id="tabbody">${tabBody(d)}</div></div>
      <div><div class="row sp" style="margin-bottom:10px"><h2 style="margin:0">Findings <span class="muted">(${total})</span></h2>
        <div class="row"><button class="btn small ghost" data-act="next-issue">Next issue</button>${a.decide && easy ? h`<button class="btn small primary" data-act="fix-easy">${icon("zap")}Fix ${easy} easy ones</button>` : ""}</div></div>
        <div class="row" style="margin-bottom:12px;gap:6px"><button class="chip on" data-act="fl" data-k="all">All<b>${total}</b></button><button class="chip" data-act="fl" data-k="open">Open<b>${open}</b></button>
          <button class="chip" data-act="fl" data-k="high">High<b>${counts.high || 0}</b></button><button class="chip" data-act="fl" data-k="lock">${icon("lock")}Needs a person<b>${counts.needs_human || 0}</b></button>
          ${cats.map(k => h`<button class="chip" data-act="fl" data-k="cat:${k}">${CAT[k]}<b>${d.findings.filter(f => f.category === k).length}</b></button>`)}</div>
        <div id="flist">${total ? d.findings.map(f => findingCard(f, d)) : h`<div class="card empty">${okArt}<div><b>No issues found</b></div>This content follows your brand rules and approved facts.</div>`}</div></div></div>`;
}
