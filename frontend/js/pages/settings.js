import { h, api, act, form, change, icon, pill, toast, fmtTime, state } from "../util.js";

const PREF = [["email_enabled", "Email me alerts"], ["slack_enabled", "Send to Slack (organisation channel)"], ["webhook_enabled", "Send to the webhook"], ["digest_enabled", "Weekly digest email"]];
change("pref", async el => { await api("/api/notification-prefs", { method: "PUT", body: { [el.dataset.k]: el.checked } }); toast("Saved."); });
change("hybrid", async el => { await api("/api/settings", { method: "PUT", body: { hybrid: el.checked } }); toast(el.checked ? "Hybrid checking is on." : "Hybrid checking is off."); window.render(); });
form("integrations", async fd => {
  const body = {}; for (const k of ["slack_webhook_url", "webhook_url", "webhook_secret"]) if (fd[k]) body[k] = fd[k];
  if (!Object.keys(body).length) return toast("Nothing to save.", true);
  await api("/api/settings", { method: "PUT", body }); toast("Saved. Addresses are stored encrypted."); window.render();
});
act("clear-int", async el => { await api("/api/settings", { method: "PUT", body: { [el.dataset.k]: "" } }); window.render(); });
act("test-alert", async () => { const { results } = await api("/api/settings/test-alert", { method: "POST" }); toast(Object.entries(results).map(([k, v]) => `${k}: ${v}`).join(" · ")); });
act("sched-run", async () => { await api("/api/scheduler/run", { method: "POST" }); toast("Scan finished."); window.render(); });

export default async function () {
  const s = await api("/api/settings"), mgr = s.can.hybrid;
  let runs = null; if (mgr) runs = await api("/api/scheduler");
  return h`<div style="margin-bottom:16px"><h1>Settings</h1><div class="muted">Verification mode, alert channels and the background scan. Database: ${s.database}.</div></div>
    <div class="grid g2"><div class="card"><div class="card-h">${icon("zap")}<h2>Claim verification</h2></div>
      <label class="inline"><input type="checkbox" data-change="hybrid" ${s.hybrid.enabled ? "checked" : ""} ${mgr ? "" : "disabled"}> Hybrid checking (meaning-aware, finds implied claims)</label>
      <div class="small muted" style="margin-top:8px">Off = the original rule-based checker only. ${mgr ? "" : "A manager can change this."}</div>
      <div class="row" style="margin-top:10px">${pill(s.hybrid.embeddings_installed ? "green" : "amber", s.hybrid.embeddings_installed ? "Embeddings installed" : "Embeddings not installed")}${pill(s.hybrid.ai_judge_available ? "green" : "amber", s.hybrid.ai_judge_available ? "AI judge available" : "AI judge needs an API key")}</div></div>
      <div class="card"><div class="card-h">${icon("bell")}<h2>My notifications</h2></div>
      ${PREF.map(([k, l]) => h`<label class="inline" style="display:block;margin:8px 0"><input type="checkbox" data-change="pref" data-k="${k}" ${s.prefs[k] ? "checked" : ""}> ${l}</label>`)}
      <div class="small muted">Email ${s.channels.email ? "is set up" : "is not set up on this server"}.</div></div></div>
    <div class="card" style="margin-top:18px"><div class="card-h">${icon("send")}<h2>Channels</h2>${mgr ? h`<button class="btn small ghost right" data-act="test-alert">Send test alert to me</button>` : ""}</div>
      <div class="row" style="margin-bottom:10px">${["email", "slack", "webhook"].map(k => pill(s.channels[k] ? "green" : "", k + (s.channels[k] ? ": set up" : ": not set up")))}</div>
      ${s.can.integrations ? h`<form data-form="integrations"><div class="grid g2"><div><label>Slack incoming-webhook URL</label><input name="slack_webhook_url" placeholder="${s.channels.slack ? "(saved, type to replace)" : "https://hooks.slack.com/services/..."}" autocomplete="off"></div>
        <div><label>Webhook URL</label><input name="webhook_url" placeholder="${s.channels.webhook ? "(saved, type to replace)" : "https://example.com/hook"}" autocomplete="off"></div>
        <div><label>Webhook signing secret</label><input name="webhook_secret" type="password" autocomplete="new-password"></div></div>
        <div class="row" style="margin-top:10px"><button class="btn primary">Save</button>${s.channels.slack ? h`<button type="button" class="btn ghost small" data-act="clear-int" data-k="slack_webhook_url">Remove Slack</button>` : ""}${s.channels.webhook ? h`<button type="button" class="btn ghost small" data-act="clear-int" data-k="webhook_url">Remove webhook</button>` : ""}</div></form>` : h`<div class="small muted">An admin sets up Slack and webhook addresses. They are never shown here.</div>`}</div>
    ${runs ? h`<div class="card" style="margin-top:18px"><div class="card-h">${icon("clock")}<h2>Background scan</h2><button class="btn small primary right" data-act="sched-run">Run now</button></div>
      <div class="small muted" style="margin-bottom:8px">${runs.enabled ? "Automatic scan is on, every " + runs.interval_hours + " h." : "Automatic scan is off in this process (use Run now)."} Last run: ${runs.last_run_at ? fmtTime(runs.last_run_at) : "never"}. Alerts waiting: ${runs.pending_alerts}.</div>
      <table><thead><tr><th>Started</th><th>Trigger</th><th>Status</th><th>New alerts</th><th>Delivered</th><th>Failed</th></tr></thead><tbody>
      ${runs.runs.slice(0, 8).map(r => h`<tr><td>${fmtTime(r.started_at)}</td><td>${r.trigger}</td><td>${pill(r.status === "ok" ? "green" : r.status === "partial" ? "amber" : "red", r.status)}</td><td>${r.new_alerts}</td><td>${r.delivered}</td><td>${r.failed}</td></tr>`)}</tbody></table>
      <h3 style="margin-top:16px">Recent deliveries</h3>${runs.deliveries.length ? h`<table><thead><tr><th>When</th><th>Channel</th><th>Status</th><th>Detail</th></tr></thead><tbody>${runs.deliveries.slice(0, 10).map(d => h`<tr><td>${fmtTime(d.created_at)}</td><td>${d.channel}</td><td>${d.status}</td><td class="small">${d.error || d.subject}</td></tr>`)}</tbody></table>` : h`<div class="muted small">Nothing sent yet.</div>`}</div>` : ""}`;
}
