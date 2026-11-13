/* App shell, router, command palette, tooltips, theme and global events. Pages live in ./pages/. */
import { $, $$, h, raw, esc, state, hooks, api, act, ACT, FORMS, CHG, toast, flush, countUp, icon, isManager, isPriv, avatar, modal, closeOverlay, fmtTime, qs } from "./util.js";

const ROUTES = [
  [/^#\/dashboard/, () => import("./pages/dashboard.js")], [/^#\/content\/(\d+)/, () => import("./pages/workspace.js")],
  [/^#\/content/, () => import("./pages/contentlist.js")], [/^#\/new/, () => import("./pages/newreview.js")],
  [/^#\/passports/, () => import("./pages/passports.js")], [/^#\/inbox/, () => import("./pages/inbox.js")],
  [/^#\/vault/, () => import("./pages/vault.js")], [/^#\/insights/, () => import("./pages/insights.js")],
  [/^#\/proof/, () => import("./pages/proof.js")], [/^#\/feed/, () => import("./pages/feed.js")], [/^#\/audit/, () => import("./pages/audit.js")],
  [/^#\/accuracy/, () => import("./pages/accuracy.js")], [/^#\/settings/, () => import("./pages/settings.js")],
];

function applyTheme() {
  document.documentElement.dataset.theme = state.theme;
  localStorage.setItem("cp_theme", state.theme);
}

hooks.onAuthFail = () => logout();
function logout() {
  localStorage.removeItem("cp_token");
  state.token = null; state.user = null; state.shell = false;
  location.hash = "#/login";
  render();
}
act("logout", () => logout());
act("go", el => { location.hash = el.dataset.href; });
act("theme", () => { state.theme = state.theme === "dark" ? "light" : "dark"; applyTheme(); const b = $("[data-act=theme]"); if (b) b.innerHTML = themeIcon().s; });
act("menu", () => $(".side").classList.toggle("open"));
const themeIcon = () => state.theme === "dark" ? icon("sun") : icon("moon");

// ---------------------------------------------------------------- shell
function navLinks() {
  const u = state.user, groups = [
    ["Overview", [["#/dashboard", "Dashboard", "home"], ["#/content", "Content", "file"], ["#/new", "New review", "plus"]]],
    ["Trust", [["#/passports", "Claim Passports", "shield"], ["#/inbox", "Alerts", "inbox"], ["#/feed", "Truth Feed", "globe"]]],
    ["Brand", [["#/vault", "Brand Vault", "book"]]],
  ];
  if (u.role !== "creator") groups[2][1].push(["#/insights", "Insights", "chart"], ["#/proof", "Proof Time Machine", "history"], ["#/accuracy", "Accuracy Lab", "check"]);
  groups.push(["Account", [["#/settings", "Settings", "bell"]]]);
  if (isManager()) groups.push(["Admin", [["#/audit", "Audit and AI log", "activity"]]]);
  return groups;
}
function shellHtml() {
  const u = state.user;
  return h`<div class="shell"><aside class="side"><div class="brand"><span class="logo">${raw('<svg width="19" height="19" viewBox="0 0 32 32"><path d="M9 17l5 5 9-11" stroke="white" stroke-width="4" fill="none" stroke-linecap="round" stroke-linejoin="round"/></svg>')}</span>Claim Passport</div>
    <nav class="nav">${navLinks().map(([g, links]) => h`<div class="nav-h">${g}</div>${links.map(([href, label, ic]) => h`<a href="${href}" data-nav="${href}">${icon(ic)}${label}${href === "#/inbox" ? h`<span class="badge hide" id="nav-badge">0</span>` : ""}</a>`)}`)}</nav>
    <div class="who" style="margin-top:auto">${avatar(u.name, 38)}<div style="min-width:0"><b>${u.name}</b><span>${u.role}${u.team ? " · " + u.team : ""}</span></div><button class="iconbtn right" data-act="logout" title="Sign out" style="background:transparent;border-color:#2c3a49;color:#c5cfda">${icon("out")}</button></div></aside>
    <div class="main"><div class="topbar"><button class="iconbtn menu-btn" data-act="menu" aria-label="Menu">${icon("menu")}</button>
      <div class="search" data-act="cmdk" role="button" tabindex="0">${icon("search")}<span>Search pages and content...</span><span class="kbd right">Ctrl K</span></div>
      <a class="btn primary" href="#/new">${icon("plus")}New review</a>
      <button class="iconbtn" data-act="theme" title="Light or dark mode">${themeIcon()}</button>
      <div style="position:relative"><button class="iconbtn" data-act="bell" aria-label="Notifications">${icon("bell")}<span class="dot hide" id="bell-dot">0</span></button><div id="bell-menu"></div></div></div>
      <div class="content" id="page"></div></div></div>`;
}
function ensureShell() {
  if (state.shell && $("#page")) return;
  $("#app").innerHTML = shellHtml().s;
  state.shell = true;
}
function markNav() {
  const cur = location.hash || "#/dashboard";
  $$("[data-nav]").forEach(a => a.classList.toggle("on", cur.startsWith(a.dataset.nav)));
  $(".side")?.classList.remove("open");
}
async function refreshBell() {
  try {
    const { notifications } = await api("/api/notifications");
    state.notifs = notifications; state.unread = notifications.filter(n => !n.read).length;
    for (const id of ["nav-badge", "bell-dot"]) { const el = $("#" + id); if (el) { el.textContent = state.unread; el.classList.toggle("hide", !state.unread); } }
  } catch (e) { /* ignore */ }
}
act("bell", e => {
  const m = $("#bell-menu");
  if (m.innerHTML) { m.innerHTML = ""; return; }
  m.innerHTML = h`<div class="dropdown"><div class="row sp" style="padding:12px 14px;border-bottom:1px solid var(--line)"><b>Notifications</b><a href="#/inbox" class="small">See all</a></div>
    ${state.notifs.slice(0, 6).map(n => h`<a class="it" href="${n.link || "#/inbox"}">${n.message}<div class="tiny muted">${fmtTime(n.created_at)}</div></a>`)}
    ${state.notifs.length ? "" : h`<div class="empty small">You are all caught up.</div>`}</div>`.s;
});
document.addEventListener("click", e => { if (!e.target.closest("[data-act=bell]") && !e.target.closest("#bell-menu")) { const m = $("#bell-menu"); if (m) m.innerHTML = ""; } });

// ---------------------------------------------------------------- router
let renderId = 0;
async function render() {
  const my = ++renderId;
  if (!state.token) { const m = await import("./pages/login.js"); $("#app").innerHTML = (await m.default()).s; state.shell = false; flush(); return; }
  try {
    if (!state.user) state.user = (await api("/api/me")).user;
    if (!location.hash || /^#\/?(login)?$/.test(location.hash)) { location.hash = "#/dashboard"; return; }
    ensureShell(); markNav();
    const page = $("#page");
    page.innerHTML = '<div class="grid g3"><div class="skeleton"></div><div class="skeleton"></div><div class="skeleton"></div></div><div class="skeleton" style="margin-top:18px;height:260px"></div>';
    const hash = location.hash, route = ROUTES.find(([rx]) => rx.test(hash));
    if (!route) { page.innerHTML = h`<div class="empty">Page not found. <a href="#/dashboard">Go to the dashboard</a></div>`.s; return; }
    const mod = await route[1]();
    const html = await mod.default(...(hash.match(route[0]) || []).slice(1));
    if (my !== renderId) return;          // a newer navigation started
    page.innerHTML = html.s; page.style.animation = "none"; void page.offsetWidth; page.style.animation = "";
    window.scrollTo({ top: 0 });
    flush(); countUp(page); refreshBell();
  } catch (err) {
    if (!state.token) return;
    ensureShell();
    $("#page").innerHTML = h`<div class="card"><h2>Something went wrong</h2><p>${err.message}</p><a class="btn" href="#/dashboard">Back to the dashboard</a></div>`.s;
    toast(err.message, true);
  }
}
window.render = render;

// ---------------------------------------------------------------- command palette (Ctrl/Cmd + K or /)
let cmdItems = [], cmdSel = 0;
async function openCmd() {
  if (!state.token) return;
  const pages = navLinks().flatMap(([, l]) => l).map(([href, label, ic]) => ({ href, label, ic, sub: "Page" }));
  let content = [];
  try { content = (await api("/api/contents")).contents.map(c => ({ href: "#/content/" + c.id, label: c.title, ic: "file", sub: `${c.status.replace("_", " ")} · ${c.owner_name}` })); } catch (e) { /* ignore */ }
  const all = [...pages, ...content];
  $("#overlay").innerHTML = h`<div class="modal-bg" style="align-items:start"><div class="cmdk"><input id="cmdk-in" placeholder="Jump to a page or content..." autocomplete="off"><div class="items" id="cmdk-items"></div></div></div>`.s;
  const input = $("#cmdk-in"); input.focus();
  const paint = () => {
    const q = input.value.toLowerCase();
    cmdItems = all.filter(i => i.label.toLowerCase().includes(q)).slice(0, 9);
    cmdSel = Math.min(cmdSel, Math.max(0, cmdItems.length - 1));
    $("#cmdk-items").innerHTML = cmdItems.length ? cmdItems.map((i, n) => h`<div class="it ${n === cmdSel ? "sel" : ""}" data-i="${n}">${icon(i.ic)}<div><div>${i.label}</div><div class="tiny muted">${i.sub}</div></div></div>`).map(x => x.s).join("") : '<div class="empty small">No matches</div>';
  };
  const choose = n => { const it = cmdItems[n]; if (it) { closeOverlay(); location.hash = it.href; } };
  input.oninput = () => { cmdSel = 0; paint(); };
  input.onkeydown = e => {
    if (e.key === "ArrowDown") { cmdSel = Math.min(cmdItems.length - 1, cmdSel + 1); paint(); e.preventDefault(); }
    else if (e.key === "ArrowUp") { cmdSel = Math.max(0, cmdSel - 1); paint(); e.preventDefault(); }
    else if (e.key === "Enter") choose(cmdSel);
    else if (e.key === "Escape") closeOverlay();
  };
  $("#cmdk-items").onclick = e => { const it = e.target.closest(".it"); if (it) choose(Number(it.dataset.i)); };
  $(".modal-bg").onclick = e => { if (e.target.classList.contains("modal-bg")) closeOverlay(); };
  paint();
}
act("cmdk", () => openCmd());
document.addEventListener("keydown", e => {
  const typing = /INPUT|TEXTAREA|SELECT/.test(document.activeElement?.tagName);
  if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") { e.preventDefault(); openCmd(); }
  else if (e.key === "/" && !typing && !$(".modal-bg")) { e.preventDefault(); openCmd(); }
  else if (e.key === "Escape") closeOverlay();
  else if (!typing && !$(".modal-bg")) window.dispatchEvent(new CustomEvent("cp-key", { detail: e }));
});

// ---------------------------------------------------------------- tooltips
const tip = $("#tooltip");
document.addEventListener("mouseover", e => {
  const el = e.target.closest("[data-tip]");
  if (!el) { tip.classList.remove("show"); return; }
  tip.textContent = el.dataset.tip; tip.classList.add("show");
});
document.addEventListener("mousemove", e => { if (tip.classList.contains("show")) { tip.style.left = Math.min(innerWidth - 300, e.clientX + 14) + "px"; tip.style.top = (e.clientY + 16) + "px"; } });
document.addEventListener("mouseout", e => { if (!e.relatedTarget || !e.relatedTarget.closest?.("[data-tip]")) tip.classList.remove("show"); });

// ---------------------------------------------------------------- global events
document.addEventListener("click", async e => {
  const el = e.target.closest("[data-act]");
  if (!el) return;
  const fn = ACT[el.dataset.act];
  if (!fn) return;
  if (el.tagName === "SELECT" || el.type === "checkbox") return;
  if (el.tagName !== "A" || el.getAttribute("href") === "#") e.preventDefault();
  try { await fn(el, e); } catch (err) { toast(err.message, true); }
});
document.addEventListener("change", async e => {
  const el = e.target.closest("[data-change]");
  if (!el) return;
  try { await CHG[el.dataset.change]?.(el, e); } catch (err) { toast(err.message, true); }
});
document.addEventListener("submit", async e => {
  const f = e.target.closest("form[data-form]");
  if (!f) return;
  e.preventDefault();
  const fd = Object.fromEntries(new FormData(f).entries());
  try { await FORMS[f.dataset.form]?.(fd, f); } catch (err) { toast(err.message, true); }
});
window.addEventListener("hashchange", render);

applyTheme();
(async function init() {
  try { state.meta = await api("/api/meta"); } catch (e) { state.meta = null; }
  render();
})();
