import { h, api, icon, pill, fmtTime, act, state } from "../util.js";
import { okArt } from "../art.js";

export default async function () {
  const [{ notifications }, { proposals }] = await Promise.all([api("/api/notifications"), api("/api/proposals")]);
  api("/api/notifications/read", { method: "POST", body: {} }).catch(() => {});
  return h`<div style="margin-bottom:16px"><h1>Alerts</h1><div class="muted">Suggested fixes after a source changed, and notifications about your content.</div></div>
    <div class="card" style="margin-bottom:18px"><div class="card-h">${icon("zap")}<h2>Suggested fixes (${proposals.length})</h2></div>
      ${proposals.length ? proposals.map(p => h`<div style="padding:14px 0;border-top:1px solid var(--line)"><div class="row sp"><a href="#/content/${p.content_id}"><b>${p.content_title}</b></a><div class="row"><button class="btn small teal" data-act="proposal-apply" data-id="${p.id}">Apply as new draft</button><button class="btn small ghost" data-act="proposal-dismiss" data-id="${p.id}">Dismiss</button></div></div>
        <div class="small muted" style="margin:6px 0">${p.message}</div><div class="ba"><div class="b">${p.old_text}</div><span class="muted">${icon("arrow")}</span><div class="a">${p.new_text}</div></div>
        ${p.new_text === p.old_text ? h`<div class="tiny muted">This is a reminder only. Re-verify the fact, then dismiss.</div>` : ""}</div>`)
        : h`<div class="empty">${okArt}<div><b>No open suggestions</b></div>When a source changes, fixes appear here.</div>`}</div>
    <div class="card"><div class="card-h">${icon("bell")}<h2>Notifications</h2></div>${notifications.length ? notifications.map(n => h`<a class="row" href="${n.link || "#/inbox"}" style="padding:11px 0;border-top:1px solid var(--line);color:var(--ink);flex-wrap:nowrap">${icon("alert")}<span style="flex:1">${n.message}<div class="tiny muted">${fmtTime(n.created_at)}</div></span>${n.read ? "" : pill("amber", "new")}</a>`) : h`<div class="empty">No notifications.</div>`}</div>`;
}
