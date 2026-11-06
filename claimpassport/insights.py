"""Governance insights: repeated mistakes, unclear guidelines, trends and the dashboard overview."""
import re
from collections import Counter, defaultdict

from . import clock, passports, vault, watcher

UNCLEAR = re.compile(r"unclear|not sure|confus|ambiguous|what counts|doesn.?t apply|does not apply|outdated|too strict|vague|which rule", re.I)


def overview(db, user, today=None, warn_days=14):
    today = today or clock.today()
    own = user["id"] if user["role"] == "creator" else None
    where, params = ("WHERE owner_id=?", (own,)) if own else ("", ())
    status = {r["status"]: r["n"] for r in db.q(f"SELECT status, COUNT(*) n FROM contents {where} GROUP BY status", params)}
    ids = [r["id"] for r in db.q(f"SELECT id FROM contents {where}", params)]
    open_findings, open_sev = 0, {"high": 0, "medium": 0, "low": 0}
    if ids:
        marks = ",".join("?" * len(ids))
        open_findings = db.one(
            f"SELECT COUNT(*) n FROM findings f JOIN contents c ON c.id=f.content_id AND c.current_version=f.version "
            f"WHERE f.decision='open' AND f.content_id IN ({marks})", tuple(ids))["n"]
        for r in db.q(f"SELECT f.severity, COUNT(*) n FROM findings f JOIN contents c ON c.id=f.content_id AND c.current_version=f.version "
                      f"WHERE f.decision='open' AND f.content_id IN ({marks}) GROUP BY f.severity", tuple(ids)):
            open_sev[r["severity"]] = r["n"]
    debt = passports.truth_debt(db, today, warn_days, owner_id=own)
    attention = [p for p in passports.list_passports(db, today, warn_days, owner_id=own) if p["status"] != "valid"]
    attention.sort(key=lambda p: (p["color"] != "red", p["days_left"] if p["days_left"] is not None else 999))
    unread = db.one("SELECT COUNT(*) n FROM notifications WHERE user_id=? AND read=0", (user["id"],))["n"]
    recent = db.q(f"SELECT id, title, status, channel, updated_at FROM contents {where} ORDER BY updated_at DESC, id DESC LIMIT 6", params)
    return {"content_status": status, "open_findings": open_findings, "open_by_severity": open_sev, "truth_debt": debt,
            "attention": [{k: p[k] for k in ("id", "content_id", "content_title", "claim_text", "status", "label", "color", "days_left", "fact_key")} for p in attention[:6]],
            "unread_notifications": unread, "recent": recent,
            "open_proposals": len(watcher.list_proposals(db, "open", user))}


def mistakes(db):
    """Which rules are broken most often, and by which teams (first drafts only)."""
    rules = vault.rules_by_code(db)
    rows = db.q("SELECT rule_code, category, COUNT(*) n FROM findings WHERE version=1 GROUP BY rule_code, category ORDER BY n DESC")
    top = [{"rule_code": r["rule_code"], "category": r["category"], "count": r["n"],
            "title": rules.get(r["rule_code"], {}).get("title", r["rule_code"])} for r in rows[:10]]
    by_team = defaultdict(Counter)
    for r in db.q("SELECT u.team, f.rule_code FROM findings f JOIN contents c ON c.id=f.content_id "
                  "JOIN users u ON u.id=c.owner_id WHERE f.version=1"):
        by_team[r["team"] or "No team"][r["rule_code"]] += 1
    teams = [{"team": t, "total": sum(c.values()),
              "top": [{"rule_code": k, "count": v, "title": rules.get(k, {}).get("title", k)} for k, v in c.most_common(3)]}
             for t, c in by_team.items()]
    cats = Counter()
    for r in rows:
        cats[r["category"]] += r["n"]
    return {"top_rules": top, "teams": sorted(teams, key=lambda t: -t["total"]), "by_category": dict(cats)}


def guideline_gaps(db):
    """Rules that people often reject, ignore or repeat are probably unclear. Show the evidence."""
    rules = vault.rules_by_code(db)
    gaps = []
    for code, rule in rules.items():
        decided = db.q("SELECT decision, decision_reason FROM findings WHERE rule_code=? AND decision IN ('accepted','edited','rejected')", (code,))
        flagged = db.q("SELECT c.owner_id FROM findings f JOIN contents c ON c.id=f.content_id WHERE f.rule_code=? AND f.version=1", (code,))
        n_dec = len(decided)
        rejected = [d for d in decided if d["decision"] == "rejected"]
        reasons = [d["decision_reason"] for d in rejected if d["decision_reason"]]
        unclear_reasons = [r for r in reasons if UNCLEAR.search(r)]
        authors = len({f["owner_id"] for f in flagged})
        rate = round(len(rejected) / n_dec, 2) if n_dec else 0
        causes = []
        if n_dec >= 3 and rate >= 0.4:
            causes.append(f"{round(rate * 100)}% of decisions rejected this rule ({len(rejected)} of {n_dec}).")
        if unclear_reasons:
            causes.append(f"{len(unclear_reasons)} reviewer note(s) say the rule is unclear or outdated.")
        if len(flagged) >= 5 and authors >= 3:
            causes.append(f"{authors} different authors keep making this mistake ({len(flagged)} times).")
        if causes:
            if unclear_reasons:
                tip = "Rewrite the rule in plain words and add two examples of good and bad wording. Check whether it is still current."
            elif rate >= 0.4:
                tip = "Add exact limits and examples (what is allowed and what is not), or narrow the rule so it applies only where it should."
            else:
                tip = "Add a short example to the writer's checklist and train agencies on this rule."
            gaps.append({"rule_code": code, "title": rule["title"], "guideline_ref": rule["guideline_ref"], "causes": causes,
                         "suggestion": tip, "evidence": {"flagged": len(flagged), "authors": authors, "decided": n_dec,
                                                         "rejected": len(rejected), "reject_rate": rate, "sample_reasons": reasons[:3]}})
    return sorted(gaps, key=lambda g: -len(g["causes"]))


def trend(db, days=14, today=None):
    today = today or clock.today()
    start = today.toordinal() - days + 1
    counts = Counter()
    for r in db.q("SELECT substr(created_at,1,10) d FROM findings WHERE version=1"):
        d = clock.parse_date(r["d"])
        if d and d.toordinal() >= start:
            counts[d.isoformat()] += 1
    import datetime as dt
    return [{"date": (dt.date.fromordinal(start + i)).isoformat(), "count": counts.get((dt.date.fromordinal(start + i)).isoformat(), 0)} for i in range(days)]
