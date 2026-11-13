"""Accuracy Lab: measure how well claim checking works, on a labelled set, in two modes.

    rules   - the Round 2 checker (explicit wording, TF-IDF fact search)
    hybrid  - adds the meaning layer (concept lexicon, optional embeddings) and implied-claim finder
    hybrid+ai - hybrid plus the cited AI judge. Only measured when an AI key is configured.

A sentence counts as correct when the set of claim rules the checker reports (C-1 to C-6) equals the set a person
labelled as correct. We report precision, recall and F1 per rule and per claim type, plus the sentences it got wrong.

Run from the command line:   python -m claimpassport.accuracy            (prints a table)
                             python -m claimpassport.accuracy --json out.json
The numbers describe THIS labelled set only (see the dataset's 'limits' text, which the page always shows)."""
import argparse
import datetime as dt
import json
import time
from collections import defaultdict

from . import clock, vault
from .config import BASE_DIR, load_config
from .db import DB, jdump, jload
from .engine import pipeline
from .engine import semantic as SEM

CLAIM_RULES = ("C-1", "C-2", "C-3", "C-4", "C-5", "C-6")
DATASET_PATH = BASE_DIR / "data" / "accuracy" / "labelled_set.json"
FACTS_PATH = BASE_DIR / "data" / "sample" / "approved_facts.json"
MODE_LABEL = {"rules": "Rules only (Round 2)", "hybrid": "Hybrid (meaning layer)", "hybrid+ai": "Hybrid + cited AI judge"}


def load_dataset(path=None):
    return json.loads((path or DATASET_PATH).read_text("utf-8"))


def build_facts_db(dataset, today=None):
    """A throwaway in-memory database holding only the approved facts of the labelled set's demo brand."""
    today = today or clock.today()
    db = DB(":memory:")
    db.init()
    vault.ensure_builtin_rules(db)
    facts = json.loads(FACTS_PATH.read_text("utf-8")) + list(dataset.get("extra_facts") or [])
    for f in facts:
        d = {k: v for k, v in f.items() if k not in ("days_since_verified", "expires_in_days")}
        d["verified_on"] = (today - dt.timedelta(days=f["days_since_verified"])).isoformat()
        d["expires_on"] = (today + dt.timedelta(days=f["expires_in_days"])).isoformat()
        vault.create_fact(db, d, None)
    return db


def predict(db, text, hybrid, cfg, llm=None, today=None):
    res = pipeline.analyze(db, text, "text", {}, cfg, llm, today, hybrid=hybrid, claims_only=True)
    return {f["rule_code"] for f in res["findings"] if f["rule_code"] in CLAIM_RULES}


def _prf(tp, fp, fn):
    p = tp / (tp + fp) if tp + fp else None
    r = tp / (tp + fn) if tp + fn else None
    f1 = 2 * p * r / (p + r) if p and r else (0.0 if (p is not None and r is not None) else None)
    return {"tp": tp, "fp": fp, "fn": fn, "precision": _r(p), "recall": _r(r), "f1": _r(f1)}


def _r(x):
    return None if x is None else round(x, 3)


def score(items, preds):
    """`preds` maps item id -> set of reported rule codes."""
    per_rule = {c: [0, 0, 0] for c in CLAIM_RULES}                 # tp, fp, fn
    per_type = defaultdict(lambda: {"n": 0, "exact": 0, "tp": 0, "fp": 0, "fn": 0})
    exact, errors = 0, []
    clean = [i for i in items if not i["expected"]]
    false_alarms = misses = flagged_items = 0
    for it in items:
        want, got = set(it["expected"]), preds[it["id"]]
        ok = want == got
        exact += ok
        t = per_type[it["type"]]
        t["n"] += 1
        t["exact"] += ok
        for c in CLAIM_RULES:
            tp, fp, fn = (c in want and c in got), (c in got and c not in want), (c in want and c not in got)
            per_rule[c][0] += tp
            per_rule[c][1] += fp
            per_rule[c][2] += fn
            t["tp"] += tp
            t["fp"] += fp
            t["fn"] += fn
        if not it["expected"] and got:
            false_alarms += 1
        if it["expected"] and not got:
            misses += 1
        if it["expected"]:
            flagged_items += 1
        if not ok:
            errors.append({"id": it["id"], "type": it["type"], "text": it["text"],
                           "expected": sorted(want), "reported": sorted(got)})
    tp = sum(v[0] for v in per_rule.values())
    fp = sum(v[1] for v in per_rule.values())
    fn = sum(v[2] for v in per_rule.values())
    return {
        "n": len(items), "exact_match": exact, "accuracy": _r(exact / len(items)) if items else None,
        "overall": _prf(tp, fp, fn),
        "false_alarm_rate": _r(false_alarms / len(clean)) if clean else None, "false_alarms": false_alarms, "clean_items": len(clean),
        "miss_rate": _r(misses / flagged_items) if flagged_items else None, "misses": misses, "problem_items": flagged_items,
        "per_rule": {c: _prf(*v) for c, v in per_rule.items() if any(v)},
        "per_type": {k: {"n": v["n"], "exact": v["exact"], "accuracy": _r(v["exact"] / v["n"]),
                         **{m: _prf(v["tp"], v["fp"], v["fn"])[m] for m in ("precision", "recall", "f1")}}
                     for k, v in sorted(per_type.items())},
        "errors": errors[:80], "error_count": len(errors),
    }


def run_benchmark(cfg=None, modes=("rules", "hybrid"), dataset=None, llm=None, today=None, progress=None):
    """Run every labelled sentence through each mode. Returns a result dict that can be saved and shown."""
    cfg = cfg if cfg is not None else load_config({})
    dataset = dataset or load_dataset()
    today = today or clock.today()
    items = dataset["items"]
    db = build_facts_db(dataset, today)
    embedder = SEM.load_embedder(cfg)
    started = clock.now()
    t0 = time.time()
    result_modes = {}
    for mode in modes:
        if mode == "hybrid+ai" and not (llm is not None and getattr(llm, "available", False)):
            result_modes[mode] = {"skipped": "No AI key is configured, so this mode was not measured."}
            continue
        hybrid = mode != "rules"
        preds = {}
        for i, it in enumerate(items):
            preds[it["id"]] = predict(db, it["text"], hybrid, cfg, llm if mode == "hybrid+ai" else None, today)
            if progress:
                progress(mode, i + 1, len(items))
        result_modes[mode] = score(items, preds)
    db.close()
    return {"started_at": started, "finished_at": clock.now(), "seconds": round(time.time() - t0, 1),
            "dataset": {k: dataset.get(k) for k in ("name", "version", "size", "scope", "how_labelled", "limits")},
            "facts_used": len(json.loads(FACTS_PATH.read_text("utf-8"))) + len(dataset.get("extra_facts") or []),
            "embeddings": {"available": bool(embedder), "model": getattr(embedder, "name", None)},
            "modes": result_modes, "labels": MODE_LABEL}


def save_run(db, result, run_by=""):
    return db.insert("accuracy_runs", {"started_at": result["started_at"], "finished_at": result["finished_at"],
                                       "dataset_name": result["dataset"]["name"], "dataset_size": result["dataset"]["size"],
                                       "modes": jdump(list(result["modes"])), "result": jdump(result), "run_by": run_by})


def latest_run(db):
    row = db.one("SELECT * FROM accuracy_runs ORDER BY id DESC LIMIT 1")
    if not row:
        return None
    out = jload(row["result"], {})
    out["run_id"], out["run_by"] = row["id"], row["run_by"]
    return out


def format_table(result):
    lines = [f'{result["dataset"]["name"]}: {result["dataset"]["size"]} sentences, {result["facts_used"]} approved facts. '
             f'Embeddings: {"yes (" + str(result["embeddings"]["model"]) + ")" if result["embeddings"]["available"] else "not installed"}',
             "", f'{"Mode":28} {"Exact":>7} {"Prec":>6} {"Recall":>7} {"F1":>6} {"FalseAlarm":>11} {"Missed":>7}']
    for mode, m in result["modes"].items():
        if "skipped" in m:
            lines.append(f'{MODE_LABEL[mode]:28} {m["skipped"]}')
            continue
        o = m["overall"]
        f = lambda x: "-" if x is None else f"{x:.2f}"
        lines.append(f'{MODE_LABEL[mode]:28} {m["exact_match"]:>3}/{m["n"]:<3} {f(o["precision"]):>6} {f(o["recall"]):>7} {f(o["f1"]):>6} '
                     f'{m["false_alarms"]:>5}/{m["clean_items"]:<5} {m["misses"]:>3}/{m["problem_items"]:<3}')
    lines += ["", "Exact-match accuracy by claim type:"]
    types = sorted({t for m in result["modes"].values() if "per_type" in m for t in m["per_type"]})
    names = [m for m in result["modes"] if "per_type" in result["modes"][m]]
    lines.append(f'{"type":30}' + "".join(f"{n:>12}" for n in names))
    for t in types:
        lines.append(f"{t:30}" + "".join(f'{result["modes"][n]["per_type"][t]["accuracy"] * 100:>11.0f}%' for n in names))
    lines += ["", "Limits of this set: " + (result["dataset"].get("limits") or "")]
    return "\n".join(lines)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Measure claim checking on the labelled set.")
    ap.add_argument("--json", help="also write the full result to this file")
    ap.add_argument("--save", action="store_true", help="save the run in the app database so the Accuracy Lab page shows it")
    ap.add_argument("--errors", action="store_true", help="print every sentence a mode got wrong")
    args = ap.parse_args(argv)
    cfg = load_config({})
    from .engine.llm import LLMClient
    result = run_benchmark(cfg, ("rules", "hybrid", "hybrid+ai"), llm=LLMClient(cfg))
    print(format_table(result))
    if args.errors:
        for mode, m in result["modes"].items():
            for e in m.get("errors", []):
                print(f'[{mode}] #{e["id"]} {e["type"]}: "{e["text"]}" expected {e["expected"]} got {e["reported"]}')
    if args.json:
        with open(args.json, "w", encoding="utf-8") as fh:
            json.dump(result, fh, indent=1)
    if args.save:
        db = DB(cfg["DATABASE_URL"] or cfg["DB_PATH"])
        db.init()
        save_run(db, result, "command line")
        print("Saved to the app database.")


if __name__ == "__main__":
    main()
