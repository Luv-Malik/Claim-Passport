import { h, raw, state, api, form, act, $, icon } from "../util.js";
import { loginArt } from "../art.js";

form("login", async fd => {
  const r = await api("/api/login", { body: fd });
  state.token = r.token; state.user = r.user; localStorage.setItem("cp_token", r.token);
  location.hash = "#/dashboard"; window.render();
});
act("fill", el => { const f = $("form[data-form=login]"); f.email.value = el.dataset.email; f.password.value = "demo1234"; f.querySelector("button.primary").focus(); });

export default async function () {
  const demo = state.meta && state.meta.demo_login;
  const accounts = [["Admin", "admin@demo.cp", "shield"], ["Manager", "anil@demo.cp", "users"], ["Reviewer", "meera@demo.cp", "eye"], ["Creator: Priya", "priya@demo.cp", "edit"], ["Creator: Rohan", "rohan@demo.cp", "edit"]];
  return h`<div class="login"><div class="hero-side"><div class="brand" style="padding-left:0"><span class="logo">${raw('<svg width="19" height="19" viewBox="0 0 32 32"><path d="M9 17l5 5 9-11" stroke="white" stroke-width="4" fill="none" stroke-linecap="round" stroke-linejoin="round"/></svg>')}</span>Claim Passport</div>
      <h1>Every claim you publish, backed by a source.</h1><p>Check content before it goes live. Keep it true after. When a price or a number changes, we find every page that is now wrong.</p>
      <div class="feat">${icon("shield")}<div><b>Explained findings</b><div class="small">Every issue shows the rule or approved fact behind it.</div></div></div>
      <div class="feat">${icon("users")}<div><b>People stay in control</b><div class="small">Suggestions only. Reviewers approve everything.</div></div></div>
      <div class="feat">${icon("refresh")}<div><b>Stays true after publishing</b><div class="small">Source changes flag outdated pages automatically.</div></div></div>${loginArt}</div>
    <div class="form-side"><div class="card"><h2 style="font-size:22px">Welcome back</h2><p class="muted small" style="margin-top:0">Sign in to review and publish with confidence.</p>
      <form data-form="login"><label>Email</label><input name="email" type="email" required autocomplete="username" placeholder="you@company.com"><label>Password</label><input name="password" type="password" required autocomplete="current-password">
      <button class="btn primary" style="width:100%;margin-top:16px;padding:11px">Sign in ${icon("arrow")}</button></form>
      ${demo ? h`<div class="note" style="margin-top:18px"><b>Demo accounts</b> (password <code>demo1234</code>). Tap one to fill the form:<div class="row" style="margin-top:10px;gap:6px">${accounts.map(([n, e, ic]) => h`<button type="button" class="chip" data-act="fill" data-email="${e}">${icon(ic)}${n}</button>`)}</div></div>` : ""}
      <p class="tiny muted" style="margin-top:16px">${state.meta ? state.meta.disclosure : ""}</p></div></div></div>`;
}
