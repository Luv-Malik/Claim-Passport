import { h, raw, state, api, icon, isManager, greeting, pill, statusPill, daysText, PASS_COLOR, PASS_LABEL, STATUS, fmtDate } from "../util.js";
import { gauge, donut, legend, hbars, area, life, spark } from "../charts.js";
import { heroArt, okArt } from "../art.js";

export default async function () {
  const o = await api("/api/insights/overview");
  const priv = state.user.role !== "creator";
  const [trend, hl] = priv ? await Promise.all([api("/api/insights/trend"), api("/api/insights/half-life")]) : [null, null];
  const td = o.truth_debt, cs = o.content_status, sev = o.open_by_severity;
  const gColor = td.score >= 25 ? "#d64545" : td.score > 0 ? "#e3a008" : "#1fa463";
  const segs = Object.entries(td.counts).filter(([, v]) => v > 0).map(([k, v]) => ({ label: PASS_LABEL[k], value: v, color: PASS_COLOR[k], href: "#/passports?status=" + k }));
  const total = Object.values(cs).reduce((a, b) => a + b, 0);
  const funnel = ["draft", "in_review", "changes_requested", "approved", "published"].map(k => ({ label: STATUS[k], value: cs[k] || 0, href: "#/content?status=" + k, color: { draft: "#9aa8b8", in_review: "#2F6DB5", changes_requested: "#e3a008", approved: "#127C7A", published: "#1fa463" }[k] }));
  const role = state.user.role;
  const steps = role === "creator"
    ? [["Paste or upload something to check", "#/new", "upload"], ["Fix what the checker found", "#/content", "edit"], ["Send it for review", "#/content", "send"], ["Watch your claim passports", "#/passports", "shield"]]
    : [["Review content waiting for approval", "#/content?status=in_review", "eye"], ["Update an approved fact in the Vault", "#/vault", "book"], ["Check what goes stale next", "#/insights", "clock"], ["Open the Proof Time Machine", "#/proof", "history"]];
  return h`<div class="hero" style="margin-bottom:18px">${heroArt}<h1>${greeting()}, ${state.user.name.split(" ")[0]}</h1>
      <p>${o.open_proposals ? `${o.open_proposals} published page(s) use a fact that changed. Fixes are ready for you to review.` : td.score ? "Some live claims need attention." : "Every live claim is backed by a valid source."}</p>
      <div class="row" style="margin-top:16px"><a class="btn white" href="#/new">${icon("plus")}New review</a>${o.open_proposals ? h`<a class="btn primary" href="#/inbox">${icon("zap")}Review ${o.open_proposals} fix(es)</a>` : ""}<a class="btn" style="background:rgba(255,255,255,.14)" href="#/passports">${icon("shield")}Claim passports</a></div></div>
    <div class="grid g4">
      <div class="card kpi click" data-act="go" data-href="#/passports"><span class="lbl">Truth Debt</span>${gauge(td.score, { color: gColor, label: "of live claims out of date", size: 200 })}</div>
      <div class="card kpi click" data-act="go" data-href="#/passports"><span class="lbl">Live claims</span><span class="num" data-count="${td.total}">${td.total}</span><span class="small muted">${td.counts.valid} valid · ${td.counts.expiring} expiring soon</span>${spark([2, 3, 3, 5, 6, 8, td.total || 1], "#127C7A")}</div>
      <div class="card kpi click" data-act="go" data-href="#/content"><span class="lbl">Open findings</span><span class="num" data-count="${o.open_findings}">${o.open_findings}</span>
        <div class="row" style="gap:6px">${pill("high", sev.high + " high")}${pill("medium", sev.medium + " medium")}${pill("low", sev.low + " low")}</div></div>
      <div class="card kpi click" data-act="go" data-href="#/content?status=in_review"><span class="lbl">Waiting for review</span><span class="num" data-count="${cs.in_review || 0}">${cs.in_review || 0}</span><span class="small muted">${cs.published || 0} published · ${total} in total</span>${spark([1, 2, 2, 4, 3, 5, cs.in_review || 1], "#2F6DB5")}</div>
    </div>
    <div class="grid g21" style="margin-top:18px">
      <div class="card"><div class="card-h">${icon("shield")}<h2>Needs attention</h2><a class="small right" href="#/passports">All passports</a></div>
        ${o.attention.length ? h`<table><tbody>${o.attention.map(p => h`<tr class="clickable" data-act="go" data-href="#/content/${p.content_id}"><td style="width:150px">${pill(p.color, p.label)}</td><td><b>${p.content_title}</b><div class="small muted">${p.claim_text}</div></td><td class="small muted" style="width:110px">${p.days_left != null ? daysText(p.days_left) : ""}</td></tr>`)}</tbody></table>`
          : h`<div class="empty">${okArt}<div><b>All clear</b></div>Every live claim is valid.</div>`}</div>
      <div class="card"><div class="card-h">${icon("activity")}<h2>Claim health</h2></div>
        ${td.total ? h`<div class="row" style="justify-content:center;gap:22px">${donut(segs, { size: 150, center: { big: td.total, small: "live claims" } })}${legend(segs)}</div>` : h`<div class="empty">No published claims yet.</div>`}</div></div>
    <div class="grid g2" style="margin-top:18px">
      <div class="card"><div class="card-h">${icon("layers")}<h2>Content pipeline</h2></div>${hbars(funnel)}<div class="tiny muted" style="margin-top:6px">Click a bar to see those items.</div></div>
      <div class="card"><div class="card-h">${icon("flag")}<h2>Quick start</h2></div><div class="col">${steps.map(([t, href, ic], i) => h`<a class="row" href="${href}" style="padding:9px 10px;border:1px solid var(--line);border-radius:12px;color:var(--ink)"><span class="avatar" style="width:30px;height:30px;background:var(--brand)">${i + 1}</span><span>${t}</span><span class="right muted">${icon(ic)}</span></a>`)}</div></div></div>
    ${priv ? h`<div class="grid g2" style="margin-top:18px">
      <div class="card"><div class="card-h">${icon("chart")}<h2>Issues found per day</h2></div>${area(trend.trend.map(t => ({ label: t.date, value: t.count })), { color: "#127C7A" })}</div>
      <div class="card"><div class="card-h">${icon("clock")}<h2>What goes stale next</h2><a class="small right" href="#/insights">Insights</a></div>
        ${hl.items.slice(0, 5).map(i => { const pct = 100 * i.days_left / Math.max(i.interval_days, 1); const c = i.days_left < 0 ? "#d64545" : i.days_left <= 14 ? "#e3a008" : "#1fa463";
          return h`<div style="margin:11px 0"><div class="row sp small"><b>${i.key}</b><span class="muted">${daysText(i.days_left)} · used ${i.live_uses}x</span></div>${life(pct, c)}</div>`; })}</div></div>` : ""}`;
}
