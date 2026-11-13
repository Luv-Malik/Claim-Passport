"""The 'Dependabot for claims': when a source changes or expires, find every published item that is
affected, notify the owner and prepare a suggested fix. The owner always decides."""
from . import audit, clock, passports, workflow
from .engine import claims as claim_utils
from .engine import verify
from .errors import AppError


def _recipients(db, owner_id):
    ids = {owner_id}
    ids.update(u["id"] for u in db.q("SELECT id FROM users WHERE role IN ('manager','admin')"))
    return ids


def notify(db, user_id, message, ref="", link=""):
    if ref and db.one("SELECT id FROM notifications WHERE user_id=? AND ref=?", (user_id, ref)):
        return
    db.insert("notifications", {"user_id": user_id, "message": message, "ref": ref, "link": link, "created_at": clock.now()})
    # The in-app notice above is always created at once. This queues the same alert for email, Slack and webhook;
    # the scheduler sends it (see notifier.py), so a slow mail server never slows down a request.
    db.insert("alert_queue", {"user_id": user_id, "message": message, "link": link, "ref": ref, "kind": "alert",
                              "status": "pending", "created_at": clock.now()})


def on_fact_changed(db, before, after, actor):
    """Call this after update_fact. Returns the list of created proposals."""
    if after["version"] <= before["version"]:
        return []
    created = []
    for p in db.q("SELECT p.*, c.owner_id, c.title FROM passports p JOIN contents c ON c.id=p.content_id "
                  "WHERE p.fact_id=? AND p.active=1 AND p.fact_version<?", (after["id"], after["version"])):
        old = p["claim_text"]
        new = old
        if p["matched_raw"] and p["matched_raw"] in old:
            kinds = [n["kind"] for n in claim_utils.parse_numbers(p["matched_raw"], 0, False)]
            if kinds:
                new = old.replace(p["matched_raw"], verify.approved_number_raw(after, kinds[0]), 1)
            elif after["value"]:
                new = old.replace(p["matched_raw"], after["value"], 1)
        msg = (f'The source "{after["key"]}" changed. Old: "{before["statement"]}" New: "{after["statement"]}".'
               if not after["confidential"] else f'The confidential source "{after["key"]}" changed.')
        if not db.one("SELECT id FROM refresh_proposals WHERE passport_id=? AND status='open' AND message=?", (p["id"], msg)):
            pid = db.insert("refresh_proposals", {"content_id": p["content_id"], "passport_id": p["id"], "old_text": old,
                                                  "new_text": new, "message": msg, "created_at": clock.now()})
            created.append(pid)
        db.update("contents", p["content_id"], {"needs_refresh": 1})
        for uid in _recipients(db, p["owner_id"]):
            notify(db, uid, f'"{p["title"]}" uses an outdated fact ({after["key"]}). A suggested fix is ready.',
                   f"src:{p['id']}:{after['version']}", f"#/content/{p['content_id']}")
    audit.log(db, actor["name"] if actor else "system", "watcher.fact_changed", "fact", after["id"], {"proposals": len(created)})
    return created


def scan_expiry(db, today=None, warn_days=14):
    """Notify owners about claims that will expire soon or already expired."""
    today = today or clock.today()
    n = 0
    for p in passports.list_passports(db, today, warn_days):
        if p["status"] in ("expiring", "expired"):
            word = "expires soon" if p["status"] == "expiring" else "has expired"
            ref = f"exp:{p['id']}:{p['status']}"
            before = db.one("SELECT COUNT(*) n FROM notifications WHERE ref=?", (ref,))["n"]
            for uid in _recipients(db, p["owner_id"]):
                notify(db, uid, f'The source "{p["fact_key"]}" used in "{p["content_title"]}" {word}.', ref, f"#/content/{p['content_id']}")
            n += 0 if before else 1
    audit.log(db, "system", "watcher.scan_expiry", "system", None, {"new_alerts": n})
    return n


def list_proposals(db, status="open", user=None):
    sql = ("SELECT r.*, c.title AS content_title, c.owner_id FROM refresh_proposals r "
           "JOIN contents c ON c.id=r.content_id WHERE r.status=?")
    rows = db.q(sql, (status,))
    if user and user["role"] == "creator":
        rows = [r for r in rows if r["owner_id"] == user["id"]]
    return rows


def apply_proposal(db, cfg, user, proposal_id, llm=None):
    r = db.one("SELECT * FROM refresh_proposals WHERE id=?", (proposal_id,))
    if not r or r["status"] != "open":
        raise AppError("Proposal not found or already handled.", 404)
    c = workflow.get_content(db, r["content_id"])
    if c["owner_id"] != user["id"] and user["role"] not in ("manager", "admin"):
        raise AppError("Only the owner or a manager can apply this.", 403)
    if r["new_text"] == r["old_text"]:
        raise AppError("This is a reminder only (no wording to replace). Re-verify the fact, then dismiss it.", 409)
    cur = workflow.current_version(db, c)
    if r["old_text"] not in cur["text"]:
        raise AppError("The text has changed since this proposal was made. Please edit it by hand.", 409)
    nv = workflow.add_version(db, cfg, user, c["id"], cur["text"].replace(r["old_text"], r["new_text"], 1),
                              "Updated after a source change", llm)
    db.update("refresh_proposals", proposal_id, {"status": "applied", "resolved_by": user["id"], "resolved_at": clock.now()})
    audit.log(db, user["name"], "proposal.apply", "content", c["id"], {"proposal": proposal_id, "version": nv})
    return nv


def dismiss_proposal(db, user, proposal_id):
    r = db.one("SELECT * FROM refresh_proposals WHERE id=?", (proposal_id,))
    if not r or r["status"] != "open":
        raise AppError("Proposal not found or already handled.", 404)
    c = workflow.get_content(db, r["content_id"])
    if c["owner_id"] != user["id"] and user["role"] not in ("manager", "admin"):
        raise AppError("Only the owner or a manager can dismiss this.", 403)
    db.update("refresh_proposals", proposal_id, {"status": "dismissed", "resolved_by": user["id"], "resolved_at": clock.now()})
    audit.log(db, user["name"], "proposal.dismiss", "content", c["id"], {"proposal": proposal_id})
