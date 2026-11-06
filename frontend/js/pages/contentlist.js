import { h, raw, state, api, icon, pill, statusPill, avatar, fmtDate, STATUS, scoreColor, later, $, qs, act } from "../util.js";
import { emptyArt } from "../art.js";

export default async function () {
  const { contents } = await api("/api/contents");
  const q = qs(), ui = { status: q.get("status") || "", q: "", sort: "updated" };
  const counts = { "": contents.length }; contents.forEach(c => { counts[c.status] = (counts[c.status] || 0) + 1; });
  const rows = () => {
    let list = contents.filter(c => (!ui.status || c.status === ui.status) && (!ui.q || (c.title + c.owner_name + c.channel).toLowerCase().includes(ui.q)));
    list = [...list].sort((a, b) => ui.sort === "score" ? (a.score ?? 101) - (b.score ?? 101) : ui.sort === "title" ? a.title.localeCompare(b.title) : (b.updated_at || "").localeCompare(a.updated_at || ""));
    return list.length ? h`<table><thead><tr><th>Title</th><th>Owner</th><th>Status</th><th style="width:150px">Brand score</th><th>Open</th><th>Updated</th></tr></thead><tbody>${list.map(c => h`<tr class="clickable" data-act="go" data-href="#/content/${c.id}">
      <td><b>${c.title}</b> ${c.needs_refresh ? pill("amber", "needs refresh") : ""}<div class="tiny muted">${c.fmt} · v${c.current_version} · ${c.channel}</div></td>
      <td><div class="row" style="flex-wrap:nowrap">${avatar(c.owner_name, 28)}<div><div class="small">${c.owner_name}</div><div class="tiny muted">${c.owner_team}</div></div></div></td><td>${statusPill(c.status)}</td>
      <td>${c.score == null ? "" : h`<div class="row" style="gap:8px;flex-wrap:nowrap"><b style="color:${scoreColor(c.score)};width:28px">${c.score}</b><div class="life" style="flex:1"><i style="width:${Math.max(3, c.score)}%;background:${scoreColor(c.score)}"></i></div></div>`}</td>
      <td>${c.open_findings ? pill("amber", c.open_findings) : pill("green", "0")}</td><td class="small muted">${fmtDate(c.updated_at)}</td></tr>`)}</tbody></table>`
      : h`<div class="empty">${emptyArt}<div><b>Nothing matches</b></div>Try another filter or <a href="#/new">start a new review</a>.</div>`;
  };
  later(() => {
    const paint = () => { $("#clist").innerHTML = rows().s; $$chips(); };
    const $$chips = () => document.querySelectorAll("[data-st]").forEach(c => c.classList.toggle("on", c.dataset.st === ui.status));
    $("#csearch").oninput = e => { ui.q = e.target.value.toLowerCase(); paint(); };
    $("#csort").onchange = e => { ui.sort = e.target.value; paint(); };
    document.querySelectorAll("[data-st]").forEach(c => c.onclick = () => { ui.status = c.dataset.st; paint(); });
    $$chips();
  });
  return h`<div class="row sp" style="margin-bottom:16px"><div><h1>Content</h1><div class="muted">${contents.length} item(s). Filter, search and sort instantly.</div></div><a class="btn primary" href="#/new">${icon("plus")}New review</a></div>
    <div class="card"><div class="row" style="margin-bottom:14px"><div class="row" style="flex:1;min-width:260px;position:relative"><input id="csearch" placeholder="Search title, owner or channel..." style="padding-left:38px"><span style="position:absolute;left:11px;top:9px;color:var(--muted)">${icon("search")}</span></div>
      <select id="csort" style="width:auto"><option value="updated">Newest first</option><option value="score">Lowest score first</option><option value="title">Title A to Z</option></select></div>
      <div class="row" style="margin-bottom:12px">${[["", "All"], ...Object.entries(STATUS)].map(([k, l]) => h`<button class="chip" data-st="${k}">${l}<b>${counts[k] || 0}</b></button>`)}</div>
      <div id="clist">${rows()}</div></div>`;
}
