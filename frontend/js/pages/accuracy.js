import { h, api, act, icon, pill, toast, fmtTime } from "../util.js";

const pct = x => x == null ? "-" : Math.round(x * 100) + "%";
const f2 = x => x == null ? "-" : x.toFixed(2);

act("acc-run", async el => {
  el.disabled = true; el.textContent = "Running... (can take a minute)";
  try { await api("/api/accuracy/run", { method: "POST" }); toast("Benchmark finished."); } catch (e) { toast(e.message, true); }
  window.render();
});

export default async function () {
  const { run, can_run, ai_judge_available } = await api("/api/accuracy/latest");
  const head = h`<div class="row sp" style="margin-bottom:16px"><div><h1>Accuracy Lab</h1>
    <div class="muted">How well claim checking works on a set of sentences a person labelled. Measured, not claimed.</div></div>
    ${can_run ? h`<button class="btn primary" data-act="acc-run">${icon("refresh")}Run benchmark now</button>` : ""}</div>`;
  if (!run) return h`${head}<div class="card empty"><b>No benchmark has been run yet.</b><div>${can_run ? "Press “Run benchmark now”, or run python -m claimpassport.accuracy --save." : "A manager can run it."}</div></div>`;
  const modes = Object.entries(run.modes), measured = modes.filter(([, m]) => !m.skipped);
  const types = [...new Set(measured.flatMap(([, m]) => Object.keys(m.per_type)))];
  return h`${head}
    <div class="note" style="margin-bottom:14px"><b>${run.dataset.name}</b>: ${run.dataset.size} sentences, ${run.facts_used} approved facts. Run ${fmtTime(run.finished_at)} by ${run.run_by || "system"} (${run.seconds}s).
      Embeddings: ${run.embeddings.available ? run.embeddings.model : "not installed (meaning layer uses the concept lexicon only)"}. AI judge: ${ai_judge_available ? "configured" : "no AI key, not measured"}.</div>
    <div class="card"><table><thead><tr><th>Mode</th><th>Exact match</th><th>Precision</th><th>Recall</th><th>F1</th><th>False alarms</th><th>Missed problems</th></tr></thead><tbody>
    ${modes.map(([k, m]) => m.skipped ? h`<tr><td><b>${run.labels[k]}</b></td><td colspan="6" class="muted">${m.skipped}</td></tr>` :
      h`<tr><td><b>${run.labels[k]}</b></td><td>${m.exact_match}/${m.n} (${pct(m.accuracy)})</td><td>${f2(m.overall.precision)}</td><td>${f2(m.overall.recall)}</td><td><b>${f2(m.overall.f1)}</b></td><td>${m.false_alarms}/${m.clean_items}</td><td>${m.misses}/${m.problem_items}</td></tr>`)}</tbody></table></div>
    <div class="card" style="margin-top:18px"><div class="card-h"><h2>Exact-match accuracy by claim type</h2></div><table><thead><tr><th>Type</th>${measured.map(([k]) => h`<th>${run.labels[k]}</th>`)}</tr></thead><tbody>
    ${types.map(t => h`<tr><td>${t}</td>${measured.map(([, m]) => h`<td>${m.per_type[t] ? pct(m.per_type[t].accuracy) + " (" + m.per_type[t].exact + "/" + m.per_type[t].n + ")" : "-"}</td>`)}</tr>`)}</tbody></table></div>
    ${measured.map(([k, m]) => h`<div class="card" style="margin-top:18px"><div class="card-h"><h2>Sentences it got wrong: ${run.labels[k]} ${pill("amber", m.error_count)}</h2></div>
      ${m.errors.length ? h`<table><thead><tr><th>Sentence</th><th>Labelled</th><th>Reported</th></tr></thead><tbody>${m.errors.slice(0, 25).map(e => h`<tr><td class="small">${e.text}</td><td>${e.expected.join(", ") || "clean"}</td><td>${e.reported.join(", ") || "clean"}</td></tr>`)}</tbody></table>` : h`<div class="muted">None.</div>`}</div>`)}
    <div class="warn" style="margin-top:18px"><b>Limits of this set.</b> ${run.dataset.limits || ""}</div>`;
}
