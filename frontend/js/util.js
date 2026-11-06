/* Core helpers: safe HTML templates, API calls, state, icons, toast, modal. */
const ESC = {"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"};
export const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ESC[c]);
export class Raw { constructor(s) { this.s = s; } toString() { return this.s; } }
export const raw = s => new Raw(s);
const val = v => v instanceof Raw ? v.s : Array.isArray(v) ? v.map(val).join("") : v === false || v == null ? "" : esc(v);
/** Tagged template: every value is HTML-escaped unless it is already `Raw`. This prevents XSS. */
export const h = (strings, ...vals) => new Raw(strings.reduce((o, s, i) => o + s + (i < vals.length ? val(vals[i]) : ""), ""));
export const $ = (s, r = document) => r.querySelector(s);
export const $$ = (s, r = document) => [...r.querySelectorAll(s)];

export const state = {
  token: localStorage.getItem("cp_token"), user: null, meta: null, ws: null, unread: 0, notifs: [],
  theme: localStorage.getItem("cp_theme") || (matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light"),
};
export const hooks = { onAuthFail: () => {} };
export const PRIV = ["reviewer", "manager", "admin"];
export const isManager = () => ["manager", "admin"].includes(state.user?.role);
export const isPriv = () => PRIV.includes(state.user?.role);

export const STATUS = {draft: "Draft", in_review: "In review", changes_requested: "Changes requested", approved: "Approved", published: "Published"};
export const CAT = {claims: "Facts and claims", tone: "Tone", terminology: "Terminology", messaging: "Messaging", accessibility: "Accessibility", visual: "Visual"};
export const CAT_COLOR = {claims: "#d64545", tone: "#C75B0B", terminology: "#2F6DB5", messaging: "#8a5cc2", accessibility: "#127C7A", visual: "#e3a008"};
export const PASS_COLOR = {valid: "#1fa463", expiring: "#e3a008", source_changed: "#d64545", expired: "#a32b2b", override: "#8a5cc2", source_removed: "#6b7686"};
export const PASS_LABEL = {valid: "Valid", expiring: "Expiring soon", source_changed: "Source changed", expired: "Source expired", override: "No source", source_removed: "Source removed"};

// ---- icons (simple stroke icons)
const ICONS = {
  home: '<path d="M3 11l9-8 9 8"/><path d="M5 10v10h14V10"/>', file: '<path d="M14 3H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z"/><path d="M14 3v6h6M8 13h8M8 17h8"/>',
  plus: '<path d="M12 5v14M5 12h14"/>', shield: '<path d="M12 3l8 3v6c0 5-3.5 8-8 9-4.5-1-8-4-8-9V6z"/><path d="M8.5 12l2.5 2.5 4.5-5"/>',
  book: '<path d="M4 5a2 2 0 0 1 2-2h13v16H6a2 2 0 0 0-2 2z"/><path d="M4 21V5M9 8h6"/>', chart: '<path d="M4 20V10M10 20V4M16 20v-8M22 20H2"/>',
  clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>', search: '<circle cx="11" cy="11" r="7"/><path d="M21 21l-4.3-4.3"/>',
  bell: '<path d="M6 8a6 6 0 0 1 12 0c0 7 3 8 3 8H3s3-1 3-8"/><path d="M10 20a2 2 0 0 0 4 0"/>', out: '<path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4M16 17l5-5-5-5M21 12H9"/>',
  sun: '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/>',
  moon: '<path d="M21 13A9 9 0 1 1 11 3a7 7 0 0 0 10 10z"/>', check: '<path d="M5 12l5 5 9-10"/>', x: '<path d="M6 6l12 12M18 6L6 18"/>',
  alert: '<path d="M12 3l10 18H2z"/><path d="M12 10v4M12 17.5v.5"/>', lock: '<rect x="5" y="11" width="14" height="10" rx="2"/><path d="M8 11V8a4 4 0 0 1 8 0v3"/>',
  upload: '<path d="M12 16V4M7 9l5-5 5 5M4 20h16"/>', edit: '<path d="M4 20h4L19 9l-4-4L4 16z"/>', send: '<path d="M22 2L11 13M22 2l-7 20-4-9-9-4z"/>',
  refresh: '<path d="M20 11a8 8 0 0 0-14-4M4 4v4h4M4 13a8 8 0 0 0 14 4M20 20v-4h-4"/>', link: '<path d="M10 14a5 5 0 0 0 7 0l3-3a5 5 0 0 0-7-7l-1 1M14 10a5 5 0 0 0-7 0l-3 3a5 5 0 0 0 7 7l1-1"/>',
  zap: '<path d="M13 2L4 14h7l-1 8 9-12h-7z"/>', eye: '<path d="M2 12s4-7 10-7 10 7 10 7-4 7-10 7S2 12 2 12z"/><circle cx="12" cy="12" r="3"/>',
  arrow: '<path d="M5 12h14M13 6l6 6-6 6"/>', menu: '<path d="M4 6h16M4 12h16M4 18h16"/>', globe: '<circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3a14 14 0 0 1 0 18M12 3a14 14 0 0 0 0 18"/>',
  layers: '<path d="M12 3l9 5-9 5-9-5z"/><path d="M3 13l9 5 9-5"/>', users: '<circle cx="9" cy="8" r="3.5"/><path d="M2 20a7 7 0 0 1 14 0M16 5a3.5 3.5 0 0 1 0 7M18 20a6 6 0 0 0-3-5"/>',
  activity: '<path d="M3 12h4l3-8 4 16 3-8h4"/>', inbox: '<path d="M3 13l3-8h12l3 8v6H3z"/><path d="M3 13h5l1 3h6l1-3h5"/>', copy: '<rect x="9" y="9" width="11" height="11" rx="2"/><path d="M5 15V6a2 2 0 0 1 2-2h8"/>',
  info: '<circle cx="12" cy="12" r="9"/><path d="M12 11v6M12 7.5v.5"/>', flag: '<path d="M5 21V4h11l-2 4 2 4H5"/>', history: '<path d="M3 12a9 9 0 1 0 3-6.7M3 4v5h5"/><path d="M12 8v5l3 2"/>',
  tag: '<path d="M3 12V4h8l10 10-8 8z"/><circle cx="8" cy="9" r="1.5"/>', robot: '<rect x="4" y="8" width="16" height="11" rx="3"/><path d="M12 8V4M9 13v1M15 13v1M9 17h6"/>',
};
export const icon = (name, cls = "") => raw(`<svg class="ic ${cls}" viewBox="0 0 24 24" aria-hidden="true">${ICONS[name] || ""}</svg>`);

// ---- formatting
export const fmtDate = s => (s || "").slice(0, 10);
export const fmtTime = s => (s || "").slice(0, 16).replace("T", " ");
export const daysText = d => d == null ? "" : d < 0 ? `${-d} day${d === -1 ? "" : "s"} ago` : d === 0 ? "today" : `in ${d} day${d === 1 ? "" : "s"}`;
export const initials = n => (n || "?").split(" ").map(x => x[0]).slice(0, 2).join("").toUpperCase();
const AV = ["#C75B0B", "#127C7A", "#2F6DB5", "#8a5cc2", "#d64545", "#1fa463"];
export const avatar = (name, size = 36) => h`<span class="avatar" style="width:${size}px;height:${size}px;background:${AV[[...String(name || "?")].reduce((a, c) => a + c.charCodeAt(0), 0) % AV.length]};font-size:${Math.round(size * .36)}px">${initials(name)}</span>`;
export const pill = (cls, text) => h`<span class="pill ${cls}">${text}</span>`;
export const statusPill = s => pill(s, STATUS[s] || s);
export const scoreColor = s => s >= 80 ? "#1fa463" : s >= 50 ? "#e3a008" : "#d64545";
export const greeting = () => { const t = new Date().getHours(); return t < 5 ? "Working late" : t < 12 ? "Good morning" : t < 17 ? "Good afternoon" : "Good evening"; };

// ---- later queue: run after the page HTML is in the DOM (charts, counters, listeners)
const queue = [];
export const later = fn => queue.push(fn);
export function flush() { while (queue.length) { try { queue.shift()(); } catch (e) { console.error(e); } } }
export function countUp(root = document) {
  $$("[data-count]", root).forEach(el => {
    const to = Number(el.dataset.count), t0 = performance.now(), dur = 800;
    const tick = now => { const p = Math.min(1, (now - t0) / dur); el.textContent = Math.round(to * (1 - Math.pow(1 - p, 3))); if (p < 1) requestAnimationFrame(tick); };
    requestAnimationFrame(tick);
  });
}

// ---- actions registry: pages call act("name", fn); clicks on [data-act=name] run it
export const ACT = {};
export const act = (name, fn) => { ACT[name] = fn; };

// ---- toast and modal
export function toast(msg, err) {
  const t = document.createElement("div");
  t.className = "toast" + (err ? " err" : "");
  t.append(msg);
  $("#toast").appendChild(t);
  setTimeout(() => t.remove(), err ? 6500 : 3800);
}
export function closeOverlay() { $("#overlay").innerHTML = ""; }
export function modal({ title, body, submit = "Save", onSubmit, wide, cancel = "Cancel" }) {
  const root = $("#overlay");
  root.innerHTML = h`<div class="modal-bg"><form class="modal ${wide ? "wide" : ""}"><h2>${title}</h2>${body instanceof Raw ? body : raw(body || "")}
    <div class="row" style="margin-top:18px;justify-content:flex-end"><button type="button" class="btn ghost" data-close>${cancel}</button>${onSubmit ? h`<button class="btn primary">${submit}</button>` : ""}</div></form></div>`.s;
  root.querySelector("[data-close]").onclick = closeOverlay;
  root.querySelector(".modal-bg").onclick = e => { if (e.target.classList.contains("modal-bg")) closeOverlay(); };
  const first = root.querySelector("input:not([readonly]),textarea,select"); if (first) first.focus();
  root.querySelector("form").onsubmit = async e => {
    e.preventDefault();
    if (!onSubmit) return closeOverlay();
    const fd = Object.fromEntries(new FormData(e.target).entries());
    try { await onSubmit(fd); closeOverlay(); } catch (err) { toast(err.message, true); }
  };
}

// ---- API
export async function api(path, opts = {}) {
  const headers = {};
  if (state.token) headers.Authorization = "Bearer " + state.token;
  let body;
  if (opts.form) body = opts.form;
  else if (opts.body !== undefined) { headers["Content-Type"] = "application/json"; body = JSON.stringify(opts.body); }
  const res = await fetch(path, { method: opts.method || (body ? "POST" : "GET"), headers, body });
  let data = null;
  try { data = await res.json(); } catch (e) { /* not json */ }
  if (res.status === 401 && state.token && path !== "/api/login") { hooks.onAuthFail(); throw new Error("Please sign in again."); }
  if (!res.ok) throw Object.assign(new Error((data && data.error) || "Request failed (" + res.status + ")"), { data, status: res.status });
  return data;
}
export const qs = () => new URLSearchParams(location.hash.split("?")[1] || "");

// ---- forms and change handlers registry (pages register, app.js dispatches)
export const FORMS = {};
export const form = (name, fn) => { FORMS[name] = fn; };
export const CHG = {};
export const change = (name, fn) => { CHG[name] = fn; };
export const go = hash => { location.hash = hash; };
