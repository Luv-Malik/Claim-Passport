import { h, api, icon, pill, daysText, CAT, CAT_COLOR, PASS_COLOR } from "../util.js";
import { hbars, stacked, donut, legend, area, life, gauge } from "../charts.js";
import { okArt } from "../art.js";

const PAL = ["#C75B0B", "#127C7A", "#2F6DB5", "#8a5cc2", "#d64545", "#e3a008", "#1fa463", "#6b7686"];
export default async function () {
  const [m, gp, hl, tr, ov] = await Promise.all([api("/api/insights/mistakes"), api("/api/insights/guideline-gaps"), api("/api/insights/half-life"), api("/api/insights/trend"), api("/api/insights/overview")]);
  const ruleColor = {}; m.top_rules.forEach((r, i) => { ruleColor[r.rule_code] = PAL[i % PAL.length]; });
  const catSegs = Object.entries(m.by_category).map(([k, v]) => ({ label: CAT[k] || k, value: v, color: CAT_COLOR[k] || "#888" }));
  const teamRows = m.teams.map(t => { const used = t.top.reduce((a, x) => a + x.count, 0);
    return { label: t.team, parts: [...t.top.map(x => ({ value: x.count, color: ruleColor[x.rule_code] || "#888", tip: `${x.rule_code}: ${x.count}` })), ...(t.total > used ? [{ value: t.total - used, color: "#c9d1db", tip: `Other: ${t.total - used}` }] : [])] }; });
  const ch = Object.entries(ov.truth_debt.by_channel);
  return h`<div style="margin-bottom:16px"><h1>Insights</h1><div class="muted">Where mistakes repeat, which rules confuse people, and what will go stale next.</div></div>
    <div class="grid g21"><div class="card"><div class="card-h">${icon("chart")}<h2>Repeated mistakes (first drafts)</h2></div>${hbars(m.top_rules.map(r => ({ label: `${r.rule_code}  ${r.title}`, value: r.count, color: ruleColor[r.rule_code], tip: `${r.title}: ${r.count} time(s)` })))}</div>
      <div class="card" style="text-align:center"><div class="card-h"><h2>By area</h2></div>${donut(catSegs, { size: 170, center: { big: catSegs.reduce((a, s) => a + s.value, 0), small: "findings" } })}<div style="text-align:left;margin-top:10px">${legend(catSegs)}</div></div></div>
    <div class="grid g2" style="margin-top:18px"><div class="card"><div class="card-h">${icon("users")}<h2>Which teams make which mistakes</h2></div>${teamRows.length ? stacked(teamRows) : h`<div class="empty">No data yet.</div>`}<div class="legend" style="flex-direction:row;flex-wrap:wrap;margin-top:8px">${m.top_rules.slice(0, 6).map(r => h`<div><i style="background:${ruleColor[r.rule_code]}"></i>${r.rule_code}</div>`)}</div></div>
      <div class="card"><div class="card-h">${icon("activity")}<h2>Issues found per day</h2></div>${area(tr.trend.map(t => ({ label: t.date, value: t.count })), { color: "#C75B0B" })}</div></div>
    <div class="card" style="margin-top:18px"><div class="card-h">${icon("alert")}<h2>Guidelines that may be unclear</h2></div>
      ${gp.gaps.length ? h`<div class="grid g2">${gp.gaps.map(g => h`<div class="card flat" style="border-left:5px solid var(--amber)"><div class="row sp" style="align-items:flex-start;flex-wrap:nowrap"><div><b>${g.rule_code}: ${g.title}</b><div class="tiny muted">${g.guideline_ref}</div></div>
        <div style="text-align:center;flex:none" data-tip="Share of decisions that rejected this rule">${donut([{ label: "Rejected", value: Math.round(g.evidence.reject_rate * 100), color: "#d64545" }, { label: "Accepted", value: 100 - Math.round(g.evidence.reject_rate * 100), color: "#1fa463" }], { size: 78, center: { big: Math.round(g.evidence.reject_rate * 100) + "%" } })}</div></div>
        <ul style="margin:8px 0;padding-left:18px">${g.causes.map(c => h`<li class="small">${c}</li>`)}</ul>${g.evidence.sample_reasons.length ? h`<div class="small muted">${g.evidence.sample_reasons.map(r => h`<div>“${r}”</div>`)}</div>` : ""}
        <div class="note" style="margin-top:10px"><b>Suggestion:</b> ${g.suggestion}</div></div>`)}</div>` : h`<div class="empty">${okArt}<div><b>No unclear guidelines detected</b></div></div>`}</div>
    <div class="grid g2" style="margin-top:18px"><div class="card"><div class="card-h">${icon("clock")}<h2>Claim half-life: what goes stale next</h2></div>${hl.items.slice(0, 8).map(i => { const c = i.days_left < 0 ? "#d64545" : i.days_left <= 14 ? "#e3a008" : "#1fa463";
        return h`<div style="margin:12px 0"><div class="row sp small"><span><b>${i.key}</b> <span class="muted">re-check every ${i.interval_days} days${i.learned ? " (learned)" : ""}</span></span><span>${pill(i.days_left < 0 ? "red" : i.days_left <= 14 ? "amber" : "green", daysText(i.days_left))}</span></div>${life(100 * i.days_left / Math.max(i.interval_days, 1), c)}</div>`; })}</div>
      <div class="card"><div class="card-h">${icon("globe")}<h2>Truth Debt by channel</h2></div>${ch.length ? hbars(ch.map(([k, v]) => ({ label: k, value: v.bad, max: Math.max(v.total, 1), display: `${v.bad}/${v.total}`, color: "#d64545", tip: `${k}: ${v.bad} of ${v.total} live claims out of date` }))) : h`<div class="empty">No live claims yet.</div>`}
        <div style="text-align:center;margin-top:14px">${gauge(ov.truth_debt.score, { color: ov.truth_debt.score >= 25 ? "#d64545" : ov.truth_debt.score > 0 ? "#e3a008" : "#1fa463", label: "overall Truth Debt", size: 180 })}</div></div></div>`;
}
