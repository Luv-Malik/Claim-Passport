import { h, raw, state, act, later, $, $$, icon, pill, toast, fmtDate, daysText, esc } from "../util.js";
import { life } from "../charts.js";

act("copy-feed", async () => { try { await navigator.clipboard.writeText(location.origin + "/.well-known/claims.json"); toast("Feed address copied."); } catch (e) { toast(location.origin + "/.well-known/claims.json"); } });
act("toggle-json", () => $("#jsonbox").classList.toggle("hide"));

export default async function () {
  const feed = await (await fetch("/.well-known/claims.json")).json();
  later(() => { const s = $("#feedsearch"); s.oninput = () => $$("[data-f]").forEach(c => c.classList.toggle("hide", !c.dataset.f.includes(s.value.toLowerCase()))); });
  return h`<div class="row sp" style="margin-bottom:16px"><div><h1>Truth Feed</h1><div class="muted">The public list of verified facts that AI assistants and partners can read, so they quote your latest information.</div></div>
      <div class="row"><button class="btn ghost" data-act="copy-feed">${icon("copy")}Copy feed address</button><a class="btn" href="/.well-known/claims.json" target="_blank" rel="noopener">${icon("link")}Open raw JSON</a></div></div>
    <div class="grid g3"><div class="card kpi"><span class="lbl">Verified facts published</span><span class="num" data-count="${feed.facts.length}">${feed.facts.length}</span><span class="small muted">updated ${feed.generated_on}</span></div>
      <div class="card kpi"><span class="lbl">Left out on purpose</span><span class="small">${icon("lock")} Confidential facts<br>${icon("clock")} Expired facts</span></div>
      <div class="card kpi"><span class="lbl">Address</span><code class="small" style="word-break:break-all">/.well-known/claims.json</code><span class="small muted">No login needed. Machine-readable.</span></div></div>
    <div class="card" style="margin:18px 0"><div class="card-h">${icon("robot")}<h3>How it works</h3></div><div class="grid g3 small">
      <div class="row" style="flex-wrap:nowrap;align-items:flex-start"><span class="avatar" style="background:var(--brand);width:30px;height:30px">1</span><span>Your team keeps facts verified in the <a href="#/vault">Brand Vault</a>, with a source and an expiry date.</span></div>
      <div class="row" style="flex-wrap:nowrap;align-items:flex-start"><span class="avatar" style="background:var(--teal);width:30px;height:30px">2</span><span>Only valid, non-confidential facts appear in this feed. Expired facts disappear automatically.</span></div>
      <div class="row" style="flex-wrap:nowrap;align-items:flex-start"><span class="avatar" style="background:var(--blue);width:30px;height:30px">3</span><span>AI assistants and partner sites can read the feed and quote the current price, number or certificate.</span></div></div></div>
    <div class="row" style="margin-bottom:12px"><div style="position:relative;flex:1;max-width:380px"><input id="feedsearch" placeholder="Filter facts..." style="padding-left:38px"><span style="position:absolute;left:11px;top:9px;color:var(--muted)">${icon("search")}</span></div><button class="btn small ghost" data-act="toggle-json">${icon("eye")}Show or hide JSON</button></div>
    <div class="grid g3">${feed.facts.map(f => h`<div class="card tight" data-f="${(f.key + " " + f.statement + " " + f.category).toLowerCase()}"><div class="row sp"><b>${f.key}</b><span class="pill">${f.category}</span></div><div style="margin:8px 0">${f.statement}</div>
      <div class="row" style="gap:6px">${pill("green", "valid until " + fmtDate(f.valid_until))}${f.value ? h`<span class="pill">${f.value}</span>` : ""}</div><div class="tiny muted" style="margin-top:8px">Source: ${f.source || "n/a"} · version ${f.version}</div></div>`)}</div>
    <pre class="doc hide" id="jsonbox" style="margin-top:18px">${JSON.stringify(feed, null, 2)}</pre>`;
}
