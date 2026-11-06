"""Claim Passports: every fact in published content is linked to its approved source.
Also: live status, Truth Debt score, claim half-life, the public Truth Feed and the Proof Time Machine."""
import datetime as dt

from . import clock
from .db import jdump, jload
from .engine import pipeline

BAD = {"source_changed", "expired", "source_removed", "override"}
COLOR = {"valid": "green", "expiring": "amber", "override": "amber", "source_changed": "red",
         "expired": "red", "source_removed": "red"}
LABEL = {"valid": "Valid", "expiring": "Expiring soon", "override": "Approved without a source",
         "source_changed": "Source changed", "expired": "Source expired", "source_removed": "Source removed"}
DEFAULT_INTERVAL = {"pricing": 30, "offers": 30, "metrics": 90, "support": 120, "security": 180, "legal": 180,
                    "certification": 365, "general": 90}


def publish_snapshot(db, cfg, user, c):
    """Freeze what was published: the text version, the approvals and every claim with its source."""
    v = db.one("SELECT * FROM content_versions WHERE content_id=? AND version=?", (c["id"], c["current_version"]))
    analysis = pipeline.analyze(db, v["text"], c["fmt"], jload(v["meta"], {}), cfg)
    approvals = db.q("SELECT a.*, u.name AS approver FROM approvals a JOIN users u ON u.id=a.user_id "
                     "WHERE a.content_id=? AND a.version=? ORDER BY a.id", (c["id"], c["current_version"]))
    approver = next((a["user_id"] for a in reversed(approvals) if a["decision"] == "approved"), user["id"])
    now = clock.now()
    db.run("UPDATE publications SET active=0 WHERE content_id=?", (c["id"],))
    db.run("UPDATE passports SET active=0 WHERE content_id=?", (c["id"],))
    pub_id = db.insert("publications", {"content_id": c["id"], "version": c["current_version"], "published_at": now,
                                        "published_by": user["id"], "snapshot": "{}", "active": 1})
    snap_claims = []
    for cl in analysis["claims"]:
        for s in cl["supports"]:
            fact = db.one("SELECT * FROM facts WHERE id=?", (s["fact_id"],))
            db.insert("passports", {"content_id": c["id"], "publication_id": pub_id, "fact_id": fact["id"],
                                    "fact_version": fact["version"], "claim_text": cl["text"],
                                    "matched_raw": s["matched_raw"], "approved_by": approver, "created_at": now})
            snap_claims.append({"claim": cl["text"], "matched": s["matched_raw"], "status": "supported",
                                "fact": {"id": fact["id"], "key": fact["key"], "statement": fact["statement"],
                                         "value": fact["value"], "version": fact["version"],
                                         "source": f'{fact["source_doc"]} {fact["source_ref"]}'.strip(),
                                         "confidential": fact["confidential"], "expires_on": fact["expires_on"]}})
        if cl["issues"]:
            db.insert("passports", {"content_id": c["id"], "publication_id": pub_id, "fact_id": None, "fact_version": None,
                                    "claim_text": cl["text"], "matched_raw": "", "approved_by": approver, "created_at": now})
            snap_claims.append({"claim": cl["text"], "matched": "", "status": "approved_without_source", "fact": None})
    snapshot = {"content": {"id": c["id"], "title": c["title"], "version": c["current_version"], "channel": c["channel"],
                            "ai_assisted": bool(c["ai_assisted"])},
                "text": v["text"], "published_at": now,
                "approvals": [{"by": a["approver"], "decision": a["decision"], "note": a["note"], "at": a["created_at"]} for a in approvals],
                "claims": snap_claims}
    db.update("publications", pub_id, {"snapshot": jdump(snapshot)})
    return pub_id


def live_status(p, fact, today=None, warn_days=14):
    today = today or clock.today()
    if p["fact_id"] is None:
        return "override"
    if not fact or not fact["active"]:
        return "source_removed"
    if fact["version"] > (p["fact_version"] or 0):
        return "source_changed"
    exp = clock.parse_date(fact["expires_on"])
    if exp and exp < today:
        return "expired"
    if exp and (exp - today).days <= warn_days:
        return "expiring"
    return "valid"


def list_passports(db, today=None, warn_days=14, content_id=None, status=None, owner_id=None):
    today = today or clock.today()
    sql = ("SELECT p.*, c.title AS content_title, c.channel, c.owner_id, u.name AS owner_name, "
           "f.key AS fact_key, f.statement AS fact_statement, f.value AS fact_value, f.expires_on, f.verified_on, "
           "f.version AS current_fact_version, f.active AS fact_active, f.confidential, f.owner AS fact_owner, "
           "f.source_doc, f.source_ref, f.category AS fact_category, f.review_interval_days AS interval_days "
           "FROM passports p JOIN contents c ON c.id=p.content_id JOIN users u ON u.id=c.owner_id "
           "LEFT JOIN facts f ON f.id=p.fact_id WHERE p.active=1")
    params = []
    if content_id:
        sql += " AND p.content_id=?"
        params.append(content_id)
    if owner_id:
        sql += " AND c.owner_id=?"
        params.append(owner_id)
    out = []
    for r in db.q(sql + " ORDER BY p.id DESC", tuple(params)):
        fact = None if r["fact_id"] is None else {"version": r["current_fact_version"], "active": r["fact_active"], "expires_on": r["expires_on"]}
        st = live_status(r, fact, today, warn_days)
        if status and st != status:
            continue
        exp = clock.parse_date(r["expires_on"])
        r.update(status=st, color=COLOR[st], label=LABEL[st], days_left=(exp - today).days if exp else None)
        out.append(r)
    return out


def truth_debt(db, today=None, warn_days=14, owner_id=None):
    items = list_passports(db, today, warn_days, owner_id=owner_id)
    total = len(items)
    counts = {k: 0 for k in LABEL}
    by_channel = {}
    for p in items:
        counts[p["status"]] += 1
        ch = by_channel.setdefault(p["channel"], {"total": 0, "bad": 0})
        ch["total"] += 1
        ch["bad"] += 1 if p["status"] in BAD else 0
    bad = sum(counts[k] for k in BAD)
    return {"score": round(100 * bad / total) if total else 0, "total": total, "bad": bad,
            "counts": counts, "by_channel": by_channel}


def half_life(db, today=None):
    """When will each approved fact probably need a re-check? Learns from how often it really changed."""
    today = today or clock.today()
    out = []
    for f in db.q("SELECT * FROM facts WHERE active=1"):
        vers = db.q("SELECT * FROM fact_versions WHERE fact_id=? ORDER BY version", (f["id"],))
        gaps = []
        for a, b in zip(vers, vers[1:]):
            if b["version"] > a["version"]:
                da, dbb = clock.parse_date(a["changed_at"]), clock.parse_date(b["changed_at"])
                if da and dbb and (dbb - da).days > 0:
                    gaps.append((dbb - da).days)
        learned = round(sum(gaps) / len(gaps)) if gaps else None
        default = DEFAULT_INTERVAL.get(f["category"], 90)
        interval = learned or f["review_interval_days"] or default
        verified = clock.parse_date(f["verified_on"]) or today
        stale_on = min(verified + dt.timedelta(days=interval), clock.parse_date(f["expires_on"]) or verified + dt.timedelta(days=interval))
        uses = db.one("SELECT COUNT(*) n FROM passports WHERE fact_id=? AND active=1", (f["id"],))["n"]
        out.append({"fact_id": f["id"], "key": f["key"], "statement": f["statement"] if not f["confidential"] else "(confidential fact)",
                    "category": f["category"], "interval_days": interval, "learned": bool(learned),
                    "likely_stale_on": stale_on.isoformat(), "days_left": (stale_on - today).days, "live_uses": uses})
    return sorted(out, key=lambda x: x["days_left"])


def truth_feed(db, today=None):
    """Public, machine-readable list of verified facts. Confidential and expired facts are never included."""
    today = today or clock.today()
    facts = []
    for f in db.q("SELECT * FROM facts WHERE active=1 AND confidential=0 ORDER BY category, key"):
        exp = clock.parse_date(f["expires_on"])
        if exp and exp < today:
            continue
        facts.append({"key": f["key"], "statement": f["statement"], "value": f["value"], "category": f["category"],
                      "verified_on": f["verified_on"], "valid_until": f["expires_on"], "version": f["version"],
                      "source": f["source_doc"]})
    return {"schema": "claim-passport/truth-feed/v1", "generated_on": today.isoformat(), "facts": facts,
            "note": "Only verified, non-confidential, non-expired facts are listed. Please quote these values."}


def proof_at(db, content_id, at):
    """Proof Time Machine: what was published on a date, and was it consistent with the approved sources then?"""
    day = clock.parse_date(at)
    if not day:
        return None
    cutoff = day.isoformat() + "T23:59:59Z"
    pub = db.one("SELECT * FROM publications WHERE content_id=? AND published_at<=? ORDER BY published_at DESC, id DESC LIMIT 1",
                 (content_id, cutoff))
    if not pub:
        return {"found": False, "message": "This content was not published on or before that date."}
    snap = jload(pub["snapshot"], {})
    claims = []
    for cl in snap.get("claims", []):
        entry = dict(cl)
        fact = cl.get("fact")
        if fact:
            row = db.one("SELECT version FROM fact_versions WHERE fact_id=? AND changed_at<=? ORDER BY version DESC LIMIT 1",
                         (fact["id"], cutoff))
            then = row["version"] if row else fact["version"]
            entry["consistent_on_date"] = then == fact["version"]
            entry["explanation"] = ("The approved source had the same wording on that date." if entry["consistent_on_date"]
                                    else "The approved source had been changed by that date, so this claim was already outdated.")
            if fact.get("confidential"):
                entry["fact"] = {**fact, "statement": "(confidential)", "value": "(confidential)"}
        else:
            entry["consistent_on_date"] = False
            entry["explanation"] = "A person approved this claim without a verified source."
        claims.append(entry)
    return {"found": True, "publication_id": pub["id"], "published_at": pub["published_at"], "snapshot_date": at,
            "content": snap.get("content"), "approvals": snap.get("approvals"), "claims": claims, "text": snap.get("text")}


def timeline(db, content_id):
    """Events for the Proof Time Machine: every publication and every change of a source it relies on."""
    events = [{"type": "published", "at": p["published_at"], "title": f"Published version {p['version']}", "detail": ""}
              for p in db.q("SELECT * FROM publications WHERE content_id=? ORDER BY published_at, id", (content_id,))]
    fact_ids = [r["fact_id"] for r in db.q("SELECT DISTINCT fact_id FROM passports WHERE content_id=? AND fact_id IS NOT NULL", (content_id,))]
    for fid in fact_ids:
        fact = db.one("SELECT key, confidential FROM facts WHERE id=?", (fid,))
        for v in db.q("SELECT * FROM fact_versions WHERE fact_id=? AND version>1 ORDER BY version", (fid,)):
            events.append({"type": "source_changed", "at": v["changed_at"],
                           "title": f'Source "{fact["key"]}" changed (version {v["version"]})',
                           "detail": "(confidential)" if fact["confidential"] else v["statement"]})
    return sorted(events, key=lambda e: e["at"])
