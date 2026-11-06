import { h, state, api, act, later, $, $$, icon, pill, isManager, daysText, fmtDate, qs, toast, PASS_COLOR, PASS_LABEL } from "../util.js";
import { donut, legend, life } from "../charts.js";
import { emptyArt } from "../art.js";

act("run-watcher", async () => { const r = await api("/api/watcher/run", { body: {} }); toast(`${r.new_alerts} new alert(s).`); window.render(); });
act("ps", el => { filter(el.dataset.k); });
function filter(k) {
  $$("[data-ps]").forEach(c => c.classList.toggle("hide", k && c.dataset.ps !== k));
  $$("[data-act=ps]").forEach(c => c.classList.toggle("on", c.dataset.k === k));
}

export default async function () {
  const { passports } = await api("/api/passports");
  const counts = {}; passports.forEach(p => { counts[p.status] = (counts[p.status] || 0) + 1; });
  const segs = Object.entries(counts).map(([k, v]) => ({ label: PASS_LABEL[k], value: v, color: PASS_COLOR[k] }));
  const initial = qs().get("status") || "";
  later(() => filter(initial));
  return h`<div class="row sp" style="margin-bottom:16px"><div><h1>Claim Passports</h1><div class="muted">Every fact in published content is linked to its approved source. Colours update when a source changes or expires.</div></div>
      ${isManager() ? h`<button class="btn ghost" data-act="run-watcher">${icon("refresh")}Run expiry check</button>` : ""}</div>
    <div class="grid g12"><div class="card" style="text-align:center"><div class="card-h"><h3>Status overview</h3></div>${passports.length ? h`${donut(segs, { size: 170, center: { big: passports.length, small: "claims" } })}<div style="margin-top:10px;text-align:left">${legend(segs)}</div>` : h`<div class="empty">No passports yet.</div>`}</div>
      <div><div class="row" style="margin-bottom:14px"><button class="chip on" data-act="ps" data-k="">All<b>${passports.length}</b></button>${Object.keys(PASS_LABEL).filter(k => counts[k]).map(k => h`<button class="chip" data-act="ps" data-k="${k}"><i style="width:9px;height:9px;border-radius:3px;background:${PASS_COLOR[k]}"></i>${PASS_LABEL[k]}<b>${counts[k]}</b></button>`)}</div>
        ${passports.length ? h`<div class="grid g2">${passports.map(p => { const pct = p.interval_days && p.days_left != null ? 100 * p.days_left / p.interval_days : 100;
          return h`<div class="card tight" data-ps="${p.status}" style="border-top:4px solid ${PASS_COLOR[p.status]}"><div class="row sp">${pill(p.color, p.label)}<span class="tiny muted">${p.channel}</span></div>
            <div style="margin:10px 0 6px"><b>${p.claim_text}</b></div>
            <div class="small muted">${p.fact_key ? h`${icon("shield")} <b>${p.fact_key}</b> · ${p.source_doc} ${p.source_ref}` : "Approved without a verified source"}</div>
            ${p.expires_on ? h`<div style="margin-top:10px"><div class="row sp tiny muted"><span>Source valid until ${fmtDate(p.expires_on)}</span><span>${daysText(p.days_left)}</span></div>${life(pct, p.days_left < 0 ? "#d64545" : p.days_left <= 14 ? "#e3a008" : "#1fa463")}</div>` : ""}
            <div style="margin-top:10px"><a class="small" href="#/content/${p.content_id}">${p.content_title} ${icon("arrow")}</a></div></div>`; })}</div>`
          : h`<div class="card empty">${emptyArt}<div><b>No passports yet</b></div>Publish approved content to create claim passports.</div>`}</div></div>`;
}
