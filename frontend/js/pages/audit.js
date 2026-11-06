import { h, api, act, later, $, $$, icon, pill, fmtTime } from "../util.js";
import { donut, legend } from "../charts.js";

export default async function () {
  const d = await api("/api/audit");
  const local = d.ai.filter(a => a.engine === "rules-engine").length, ext = d.ai.length - local, masked = d.ai.reduce((a, x) => a + (x.masked_items || 0), 0);
  const byAction = {}; d.audit.forEach(a => { const k = a.action.split(".")[0]; byAction[k] = (byAction[k] || 0) + 1; });
  const PAL = ["#C75B0B", "#127C7A", "#2F6DB5", "#8a5cc2", "#d64545", "#e3a008", "#1fa463", "#6b7686"];
  const segs = Object.entries(byAction).sort((a, b) => b[1] - a[1]).slice(0, 7).map(([k, v], i) => ({ label: k, value: v, color: PAL[i] }));
  later(() => { const s = $("#asearch"); s.oninput = () => $$("#atable tbody tr").forEach(r => r.classList.toggle("hide", !r.textContent.toLowerCase().includes(s.value.toLowerCase()))); });
  return h`<div style="margin-bottom:16px"><h1>Audit trail and AI log</h1><div class="muted">Who did what, and exactly where AI or outside services touched your content.</div></div>
    <div class="grid g4"><div class="card kpi"><span class="lbl">Recorded actions</span><span class="num" data-count="${d.audit.length}">${d.audit.length}</span><span class="small muted">latest 200 shown</span></div>
      <div class="card kpi"><span class="lbl">Checks run locally</span><span class="num" data-count="${local}">${local}</span><span class="small muted">nothing left the server</span></div>
      <div class="card kpi"><span class="lbl">Outside AI calls</span><span class="num" data-count="${ext}">${ext}</span><span class="small muted">${masked} personal item(s) masked</span></div>
      <div class="card kpi" style="align-items:center"><span class="lbl">Actions by type</span>${donut(segs, { size: 110, center: { big: d.audit.length } })}</div></div>
    <div class="card" style="margin-top:18px"><div class="card-h">${icon("robot")}<h2>Where AI and external services were used</h2></div><table><thead><tr><th>When</th><th>Step</th><th>Engine</th><th>Data sent</th><th>Masked</th></tr></thead><tbody>${d.ai.slice(0, 15).map(a => h`<tr><td class="small">${fmtTime(a.ts)}</td><td>${a.step}<div class="tiny muted">content ${a.content_id} ${a.note}</div></td><td>${a.engine === "rules-engine" ? pill("green", "local rules") : pill("amber", a.engine)} <span class="tiny muted">${a.model}</span></td><td class="small">${a.data_sent}</td><td>${a.masked_items}</td></tr>`)}</tbody></table></div>
    <div class="card" style="margin-top:18px"><div class="card-h">${icon("activity")}<h2>Who did what</h2><div style="position:relative;margin-left:auto;max-width:260px"><input id="asearch" placeholder="Filter..." style="padding-left:36px"><span style="position:absolute;left:11px;top:9px;color:var(--muted)">${icon("search")}</span></div></div>
      <table id="atable"><thead><tr><th>When</th><th>Who</th><th>Action</th><th>Detail</th></tr></thead><tbody>${d.audit.map(a => h`<tr><td class="small">${fmtTime(a.ts)}</td><td>${a.actor}</td><td><span class="pill">${a.action}</span></td><td class="small muted">${a.detail}</td></tr>`)}</tbody></table></div>`;
}
