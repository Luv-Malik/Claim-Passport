import { h, state, api, act, icon, pill, fmtDate, fmtTime, qs } from "../util.js";
import { emptyArt } from "../art.js";

export default async function () {
  const { contents } = await api("/api/contents?status=published");
  const q = qs(); let cid = Number(q.get("content_id")) || (contents[0] && contents[0].id) || 0;
 const at = q.get("at") || state.meta?.today || new Date().toISOString().slice(0, 10);
  if (!contents.length) return h`<h1>Proof Time Machine</h1><div class="card empty" style="margin-top:16px">${emptyArt}<div><b>Nothing published yet</b></div>Publish approved content to build a proof trail.</div>`;
  const [{ events }, r] = await Promise.all([api(`/api/contents/${cid}/timeline`), api(`/api/proof?content_id=${cid}&at=${at}`)]);
  return h`<div style="margin-bottom:16px"><h1>Proof Time Machine</h1><div class="muted">Pick a published page and a date. See exactly what was live, which approved sources backed it, and who approved it.</div></div>
    <div class="grid g12"><div class="card"><div class="card-h">${icon("history")}<h3>Timeline</h3></div>
      <label style="margin-top:0">Published item</label><select data-change="proofsel">${contents.map(c => h`<option value="${c.id}" ${c.id === cid ? "selected" : ""}>${c.title}</option>`)}</select>
      <label>Date</label><input type="date" value="${at}" data-change="proofdate" data-cid="${cid}">
      <div class="timeline" style="margin-top:16px">${events.map(e => h`<div class="tl ${e.type} ${fmtDate(e.at) === at ? "on" : ""}" data-act="go" data-href="#/proof?content_id=${cid}&at=${fmtDate(e.at)}"><b class="tt">${e.title}</b><div class="tiny muted">${fmtTime(e.at)}</div>${e.detail ? h`<div class="small">${e.detail}</div>` : ""}</div>`)}</div>
      <div class="tiny muted">Click an event to see the proof for that day.</div></div>
    <div>${r.found ? h`<div class="card"><div class="row sp"><div><h2 style="margin:0">${r.content.title}</h2><div class="muted small">Version ${r.content.version} · published ${fmtTime(r.published_at)} · approved by ${(r.approvals || []).map(a => a.by).join(", ") || "n/a"}</div></div>${pill("green", "snapshot for " + at)}</div>
        <table style="margin-top:12px"><thead><tr><th>Claim</th><th>Approved source then</th><th>Consistent on this date?</th></tr></thead><tbody>${r.claims.map(c => h`<tr><td>${c.claim}</td><td class="small">${c.fact ? h`${c.fact.statement}<div class="tiny muted">v${c.fact.version} · ${c.fact.source}</div>` : "none"}</td><td>${pill(c.consistent_on_date ? "green" : "red", c.consistent_on_date ? "yes" : "no")}<div class="tiny muted">${c.explanation}</div></td></tr>`)}</tbody></table>
        <h3 style="margin-top:16px">Text as published</h3><div class="doc">${r.text}</div></div>`
      : h`<div class="card empty">${emptyArt}<div><b>Not published on that date</b></div>${r.message}</div>`}</div></div>`;
}
import { change, go } from "../util.js";
change("proofsel", el => go(`#/proof?content_id=${el.value}`));
change("proofdate", el => go(`#/proof?content_id=${el.dataset.cid}&at=${el.value}`));
