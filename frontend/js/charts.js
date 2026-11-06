/* Hand-made SVG/HTML charts (no libraries). Every chart is animated with CSS and has hover tooltips (data-tip). */
import { h, raw, esc } from "./util.js";

const fmt = n => Number(n).toLocaleString("en-IN");

/** Half-circle gauge, 0..100. */
export function gauge(value, { color = "#1fa463", label = "", size = 210 } = {}) {
  const r = 80, len = Math.PI * r, v = Math.max(0, Math.min(100, value));
  const arc = "M 20 100 A 80 80 0 0 1 180 100";
  return h`<svg viewBox="0 0 200 118" width="${size}" style="max-width:100%"><path d="${arc}" fill="none" stroke="var(--surface2)" stroke-width="16" stroke-linecap="round"/>
    <path d="${arc}" fill="none" stroke="var(--line)" stroke-width="1" stroke-dasharray="2 6" opacity=".0"/>
    <path class="anim-arc" d="${arc}" fill="none" stroke="${color}" stroke-width="16" stroke-linecap="round" style="stroke-dasharray:${len * v / 100} ${len + 5}" data-tip="${label}: ${value}%"/>
    <text x="100" y="86" text-anchor="middle" style="font:800 38px Inter,system-ui;fill:var(--ink)"><tspan data-count="${value}">${value}</tspan><tspan style="font-size:18px">%</tspan></text>
    <text x="100" y="108" text-anchor="middle" style="font:600 12px Inter,system-ui;fill:var(--muted)">${label}</text></svg>`;
}

/** Donut chart. segments: [{label, value, color, href}] */
export function donut(segments, { size = 170, center = {} } = {}) {
  const r = 46, C = 2 * Math.PI * r, total = segments.reduce((a, s) => a + s.value, 0);
  let cum = 0;
  const arcs = total ? segments.filter(s => s.value > 0).map(s => {
    const len = C * s.value / total, off = -cum; cum += len;
    const attrs = s.href ? `data-act="go" data-href="${esc(s.href)}"` : "";
    return `<circle class="anim-arc chart-seg" ${attrs} cx="60" cy="60" r="${r}" fill="none" stroke="${s.color}" stroke-width="15" style="stroke-dasharray:${Math.max(0, len - 1.5)} ${C};stroke-dashoffset:${off}" transform="rotate(-90 60 60)" data-tip="${esc(s.label)}: ${s.value} (${Math.round(100 * s.value / total)}%)"/>`;
  }).join("") : "";
  return h`<svg viewBox="0 0 120 120" width="${size}" height="${size}"><circle cx="60" cy="60" r="${r}" fill="none" stroke="var(--surface2)" stroke-width="15"/>${raw(arcs)}
    <text x="60" y="${center.small ? 62 : 67}" text-anchor="middle" style="font:800 24px Inter,system-ui;fill:var(--ink)">${center.big ?? total}</text>
    ${center.small ? h`<text x="60" y="78" text-anchor="middle" style="font:600 8px Inter,system-ui;fill:var(--muted)">${center.small}</text>` : ""}</svg>`;
}
export const legend = (segments, total) => h`<div class="legend">${segments.map(s => {
  const inner = h`<i style="background:${s.color}"></i>${s.label}<b>${s.value}</b>`;
  return s.href ? h`<a href="${s.href}">${inner}</a>` : h`<div>${inner}</div>`;
})}</div>`;

/** Horizontal bars. rows: [{label, value, max, color, href, tip, sub}] */
export function hbars(rows, { color = "var(--brand)", format = v => fmt(v) } = {}) {
  const max = Math.max(1, ...rows.map(r => r.max ?? r.value));
  return h`${rows.map(r => {
    const inner = h`<span class="lab" title="${r.label}">${r.label}${r.sub ? h`<div class="tiny muted">${r.sub}</div>` : ""}</span>
      <div class="track" data-tip="${r.tip || `${r.label}: ${r.value}`}"><i class="anim-bar" style="width:${100 * r.value / max}%;background:${r.color || color}"></i></div><b>${r.display ?? format(r.value)}</b>`;
    return r.href ? h`<a class="hbar" href="${r.href}">${inner}</a>` : h`<div class="hbar">${inner}</div>`;
  })}`;
}

/** One stacked bar per row. rows: [{label, parts:[{value,color,tip}], total}] */
export function stacked(rows) {
  const max = Math.max(1, ...rows.map(r => r.parts.reduce((a, p) => a + p.value, 0)));
  return h`${rows.map(r => {
    const tot = r.parts.reduce((a, p) => a + p.value, 0);
    return h`<div class="hbar"><span class="lab" title="${r.label}">${r.label}</span><div class="track" style="width:${100 * tot / max}%;min-width:8px">${r.parts.map(p => h`<i class="anim-bar" style="width:${tot ? 100 * p.value / tot : 0}%;background:${p.color}" data-tip="${p.tip}"></i>`)}</div><b>${tot}</b></div>`;
  })}`;
}

/** Smooth area chart. points: [{label, value}] */
export function area(points, { color = "#127C7A", height = 170, id = "a" + Math.random().toString(36).slice(2, 7) } = {}) {
  const W = 600, H = height, pad = { l: 30, r: 10, t: 12, b: 24 };
  const max = Math.max(3, ...points.map(p => p.value));
  const x = i => pad.l + (W - pad.l - pad.r) * (points.length > 1 ? i / (points.length - 1) : .5);
  const y = v => pad.t + (H - pad.t - pad.b) * (1 - v / max);
  let d = "";
  points.forEach((p, i) => {
    if (i === 0) d = `M ${x(0)} ${y(p.value)}`;
    else { const cx = (x(i - 1) + x(i)) / 2; d += ` C ${cx} ${y(points[i - 1].value)}, ${cx} ${y(p.value)}, ${x(i)} ${y(p.value)}`; }
  });
  const fill = `${d} L ${x(points.length - 1)} ${H - pad.b} L ${x(0)} ${H - pad.b} Z`;
  const ticks = [0, Math.round(max / 2), max];
  return h`<svg viewBox="0 0 ${W} ${H}" width="100%" style="display:block"><defs><linearGradient id="${id}" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="${color}" stop-opacity=".35"/><stop offset="1" stop-color="${color}" stop-opacity="0"/></linearGradient></defs>
    ${raw(ticks.map(t => `<line class="gridline" x1="${pad.l}" x2="${W - pad.r}" y1="${y(t)}" y2="${y(t)}"/><text class="axis" x="${pad.l - 6}" y="${y(t) + 3}" text-anchor="end">${t}</text>`).join(""))}
    <path d="${fill}" fill="url(#${id})"/><path d="${d}" fill="none" stroke="${color}" stroke-width="3" stroke-linecap="round" class="anim-arc" style="stroke-dasharray:2000 2000"/>
    ${raw(points.map((p, i) => `<circle cx="${x(i)}" cy="${y(p.value)}" r="5" fill="var(--surface)" stroke="${color}" stroke-width="3" class="chart-seg" data-tip="${esc(p.label)}: ${p.value}"/>${i % 2 === 0 || points.length < 8 ? `<text class="axis" x="${x(i)}" y="${H - 6}" text-anchor="middle">${esc(p.label.slice(5))}</text>` : ""}`).join(""))}</svg>`;
}

/** Radar chart for 0..100 values. items: [{label, value, color}] */
export function radar(items, { size = 260 } = {}) {
  const c = 130, R = 74, n = items.length;
  const pt = (i, v) => { const a = -Math.PI / 2 + 2 * Math.PI * i / n; return [c + Math.cos(a) * R * v / 100, c + Math.sin(a) * R * v / 100]; };
  const rings = [25, 50, 75, 100].map(v => `<polygon points="${items.map((_, i) => pt(i, v).join(",")).join(" ")}" fill="none" stroke="var(--line)"/>`).join("");
  const axes = items.map((_, i) => { const [x, y] = pt(i, 100); return `<line x1="${c}" y1="${c}" x2="${x}" y2="${y}" stroke="var(--line)"/>`; }).join("");
  const poly = items.map((it, i) => pt(i, it.value).join(",")).join(" ");
  const labels = items.map((it, i) => { const [x, y] = pt(i, 138); return `<text class="axis" x="${x}" y="${y + 3}" text-anchor="middle" style="font-size:10.5px">${esc(it.label)}</text>`; }).join("");
  const dots = items.map((it, i) => { const [x, y] = pt(i, it.value); return `<circle class="chart-seg" cx="${x}" cy="${y}" r="5" fill="${it.value >= 80 ? "#1fa463" : it.value >= 50 ? "#e3a008" : "#d64545"}" stroke="var(--surface)" stroke-width="2" data-tip="${esc(it.label)}: ${it.value}/100"/>`; }).join("");
  return h`<svg viewBox="0 0 260 260" width="${size}" style="max-width:100%">${raw(rings + axes)}<polygon points="${poly}" fill="rgba(199,91,11,.22)" stroke="#C75B0B" stroke-width="2.5" stroke-linejoin="round"/>${raw(dots + labels)}</svg>`;
}

/** Tiny line for KPI cards. */
export function spark(values, color = "#127C7A", w = 90, hgt = 34) {
  const max = Math.max(1, ...values), step = w / Math.max(1, values.length - 1);
  const pts = values.map((v, i) => `${i * step},${hgt - 3 - (hgt - 8) * v / max}`).join(" ");
  return h`<svg class="spark" viewBox="0 0 ${w} ${hgt}" width="${w}" height="${hgt}"><polyline points="${pts}" fill="none" stroke="${color}" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/></svg>`;
}

/** Remaining-time bar. pct = share of the review cycle that is left (0..100). */
export const life = (pct, color) => h`<div class="life"><i style="width:${Math.max(3, Math.min(100, pct))}%;background:${color}"></i></div>`;

/** Content progress stepper. */
export function stepper(status) {
  const steps = [["draft", "Draft"], ["in_review", "In review"], ["approved", "Approved"], ["published", "Published"]];
  const idx = status === "changes_requested" ? 0 : steps.findIndex(s => s[0] === status);
  return h`<div class="stepper">${steps.map(([k, l], i) => h`${i ? h`<div class="stepline ${i <= idx ? "done" : ""}"></div>` : ""}<div class="step ${i < idx ? "done" : i === idx ? "now" : ""}"><span class="n">${i < idx ? "✓" : i + 1}</span>${l}</div>`)}</div>`;
}
