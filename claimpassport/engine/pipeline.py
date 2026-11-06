"""The review pipeline: text in, explained findings out.

Steps: find claims -> verify against approved facts -> run rule checkers -> add reasons, sources,
confidence and human-lock flags -> (optional) AI rewrite ideas. Nothing here changes the content."""
from .. import clock, vault
from . import checkers as K
from . import claims as C
from . import suggest as S
from . import verify as V
from .text_utils import mask_html, reading_ease, sentences, words

LOCK_FACT_CATEGORIES = {"pricing", "legal", "certification"}
WEIGHT = {"high": 12, "medium": 6, "low": 2}


def confidence_label(score):
    return "high" if score >= 0.8 else "medium" if score >= 0.6 else "low"


def _claim_findings(c, res, today):
    out, supports, issues = [], [], []

    def add(code, s, e, msg, sugg, conf, fact=None, **extra):
        out.append({"rule_code": code, "span": (s, e), "message": msg, "suggestions": sugg,
                    "confidence": conf, "fact": fact, **extra})
        issues.append(code)

    def stale(fact, s, e):
        add("C-3", s, e, f'This claim relies on "{fact["key"]}", but its source expired on {fact["expires_on"]}. '
            f"Ask {fact['owner'] or 'the owner'} to re-check it before publishing.",
            [S.note("Ask the owner to re-verify", "Once the fact is re-verified in the Vault, this warning goes away.")],
            0.9, fact)

    for nr in res["numbers"]:
        n, fact = nr["number"], nr["fact"]
        if nr["status"] == "supported":
            supports.append({"fact_id": fact["id"], "fact_version": fact["version"], "matched_raw": n["raw"], "kind": "number"})
            if V.is_expired(fact, today):
                stale(fact, n["start"], n["end"])
        elif nr["status"] == "mismatch":
            conf = min(0.97, 0.7 + nr["score"] * 0.9)
            if fact["confidential"]:
                add("C-2", n["start"], n["end"],
                    f'The number {n["raw"]} does not match an approved confidential fact. Ask {fact["owner"] or "the owner"} for the correct figure.',
                    [S.note("Ask the fact owner", "The approved value is confidential and is not shown here.")], conf, fact)
            else:
                good = V.approved_number_raw(fact, n["kind"])
                add("C-2", n["start"], n["end"],
                    f'The text says {n["raw"]}, but the approved fact says "{fact["statement"]}"',
                    [S.rep(f'Use the approved value ({good})', good, "Keeps your sentence and fixes only the number."),
                     S.note(f'Ask {fact["owner"] or "the owner"}', "If the number really changed, the fact in the Vault must be updated first.")],
                    conf, fact)
        else:
            add("C-4", n["start"], n["end"],
                f'The number {n["raw"]} has no approved source in the Brand Vault.',
                [S.note("Add the fact to the Vault", "A manager can add it with a source document, owner and expiry date."),
                 S.note("Reword without the number", "Describe the benefit without a figure.")], 0.55)
    for tr in res["triggers"]:
        t, fact = tr["trigger"], tr["fact"]
        if tr["status"] == "supported":
            supports.append({"fact_id": fact["id"], "fact_version": fact["version"], "matched_raw": t["text"], "kind": "trigger"})
            if V.is_expired(fact, today):
                stale(fact, t["start"], t["end"])
        elif t["type"] == "comparison":
            add("C-5", t["start"], t["end"], f'"{t["text"]}" compares us with another brand. This needs proof and Legal review.',
                S.compare_options(t["text"]), 0.9)
        else:
            if t["type"] in ("superlative", "absolute"):
                sugg, conf = S.hype_options(t["text"], t["type"]), 0.85
            else:
                sugg = [S.note("Ask for a verified fact", "Security or Legal can add it to the Vault with proof."),
                        S.rep("Remove this phrase", "", "Keeps the rest of your sentence.")]
                conf = 0.8 if t["type"] == "certification" else 0.7
            add("C-1", t["start"], t["end"], f'"{t["text"].strip()}" is a strong claim with no approved source in the Brand Vault.',
                sugg, conf, None, force_lock=(t["type"] == "certification"))
    info = {"text": c["text"], "start": c["start"], "end": c["end"], "supports": supports, "issues": issues}
    return out, info


def analyze(db, text, fmt, meta=None, cfg=None, llm=None, today=None):
    meta = meta or {}
    today = today or clock.today()
    rules, facts = vault.rules_by_code(db), vault.list_facts(db)
    index = V.FactIndex(facts)
    visible = mask_html(text) if fmt == "html" else text
    ctx = K.Ctx(text, visible, fmt, meta, rules, vault.list_glossary(db),
                vault.get_asset(db, "palette", []), vault.get_asset(db, "fonts", []), vault.get_asset(db, "image_rules", {}))
    raw, claim_info = [], []
    for c in C.extract_claims(visible):
        found, info = _claim_findings(c, V.verify_claim(c, index, facts, today), today)
        raw.extend(found)
        claim_info.append(info)
    raw.extend(K.run_all(ctx))

    findings, seen = [], set()
    for r in raw:
        rule = rules.get(r["rule_code"]) or {"category": "general", "severity": "medium", "guideline_ref": "", "human_lock": 0}
        s, e = r["span"]
        if (r["rule_code"], s, e) in seen:
            continue
        seen.add((r["rule_code"], s, e))
        fact = r.get("fact")
        label = confidence_label(r["confidence"])
        lock = bool(rule.get("human_lock")) or bool(r.get("force_lock")) or bool(
            fact and fact["category"] in LOCK_FACT_CATEGORIES and r["rule_code"] in ("C-2", "C-3"))
        if fact:
            ref = ", ".join(x for x in (fact["source_doc"], fact["source_ref"]) if x) or fact["key"]
            src = ("fact", fact["id"], ref, int(fact["confidential"]))
        else:
            src = ("guideline", None, f'{rule.get("guideline_ref", "")} [{r["rule_code"]}]'.strip(), 0)
        findings.append({
            "rule_code": r["rule_code"], "category": rule["category"], "severity": r.get("severity") or rule["severity"],
            "span_start": s, "span_end": e, "excerpt": text[s:e], "message": r["message"],
            "source_type": src[0], "source_id": src[1], "source_ref": src[2], "source_confidential": src[3],
            "confidence": label, "confidence_score": round(r["confidence"], 2), "suggestions": r["suggestions"],
            "needs_human": 1 if (lock or label == "low") else 0, "human_lock": 1 if lock else 0, "produced_by": "rules",
            "_fact": fact})
    findings.sort(key=lambda f: (f["span_start"], f["span_end"]))

    events = [{"step": "analysis", "engine": "rules-engine", "model": "local",
               "data_sent": "Nothing leaves your server. Checks run inside the application.", "masked": 0}]
    if llm is not None and getattr(llm, "available", False):
        sents = sentences(visible)
        picked, masked_total = 0, 0
        for f in findings:
            if picked >= 3:
                break
            if f["category"] not in ("claims", "tone") or f["severity"] == "low":
                continue
            sent = next(((s, e, t) for s, e, t in sents if s <= f["span_start"] < e), None)
            if not sent:
                continue
            fact = f["_fact"]
            statement = None if (fact and fact["confidential"]) else (fact["statement"] if fact else None)
            rewrites, masked = llm.rewrite(sent[2], f["message"], statement)
            masked_total += masked
            picked += 1
            for rw in rewrites:
                f["suggestions"].append(S.rep("AI rewrite (please check)", rw, "Written by an AI model from your sentence and the approved fact only.", (sent[0], sent[1])))
            if rewrites:
                f["produced_by"] = "rules+llm"
        events.append({"step": "rewrite-ideas", "engine": "anthropic", "model": getattr(llm, "model", "llm"),
                       "data_sent": f"{picked} sentence(s) with the issue text and approved statement. Personal data masked, confidential facts withheld.",
                       "masked": masked_total})
    for f in findings:
        f.pop("_fact", None)

    sev = {"high": 0, "medium": 0, "low": 0}
    cat_pen = {}
    for f in findings:
        sev[f["severity"]] = sev.get(f["severity"], 0) + 1
        cat_pen[f["category"]] = cat_pen.get(f["category"], 0) + WEIGHT.get(f["severity"], 4)
    summary = {
        "score": max(0, 100 - sum(cat_pen.values())),
        "category_scores": {c: max(0, 100 - p) for c, p in cat_pen.items()},
        "counts": {"total": len(findings), **sev, "needs_human": sum(f["needs_human"] for f in findings)},
        "words": len(words(visible)), "reading_ease": reading_ease(visible),
        "claims_total": len(claim_info),
        "claims_clean": sum(1 for c in claim_info if c["supports"] and not c["issues"]),
    }
    return {"findings": findings, "summary": summary, "claims": claim_info, "ai_events": events}
