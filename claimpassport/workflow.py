"""Content lifecycle: draft -> in review -> approved -> published, with versions, decisions, comments,
and strict human control. Nothing is ever changed or published without a person's decision."""
import difflib
import re

from . import audit, clock, security
from .db import jdump, jload
from .engine import pipeline
from .engine.text_utils import clean_gap
from .errors import AppError

STATUSES = ("draft", "in_review", "changes_requested", "approved", "published")


# ---------------------------------------------------------------- reading
def get_content(db, content_id):
    c = db.one("SELECT c.*, u.name AS owner_name, u.team AS owner_team FROM contents c "
               "JOIN users u ON u.id=c.owner_id WHERE c.id=?", (content_id,))
    if not c:
        raise AppError("Content not found.", 404)
    return c


def visible_to(content, user):
    return user["role"] != "creator" or content["owner_id"] == user["id"]


def current_version(db, content):
    v = db.one("SELECT * FROM content_versions WHERE content_id=? AND version=?", (content["id"], content["current_version"]))
    v["meta"] = jload(v["meta"], {})
    v["analysis"] = jload(v["analysis"], {})
    return v


def findings_for(db, content_id, version):
    rows = db.q("SELECT * FROM findings WHERE content_id=? AND version=? ORDER BY span_start, id", (content_id, version))
    for r in rows:
        r["suggestions"] = jload(r["suggestions"], [])
    return rows


def blocking_findings(db, content_id, version):
    return [f for f in findings_for(db, content_id, version)
            if f["decision"] == "open" and (f["needs_human"] or f["severity"] == "high")]


# ---------------------------------------------------------------- analysis
def run_analysis(db, cfg, content_id, version, llm=None):
    content = get_content(db, content_id)
    v = db.one("SELECT * FROM content_versions WHERE content_id=? AND version=?", (content_id, version))
    meta = jload(v["meta"], {})
    result = pipeline.analyze(db, v["text"], content["fmt"], meta, cfg, llm)
    old = findings_for(db, content_id, version)
    carry = {(f["rule_code"], f["span_start"], f["span_end"], f["excerpt"]): f for f in old if f["decision"] != "open"}
    db.run("DELETE FROM findings WHERE content_id=? AND version=?", (content_id, version))
    now = clock.now()
    for f in result["findings"]:
        row = {**f, "content_id": content_id, "version": version, "suggestions": jdump(f["suggestions"]), "created_at": now}
        prev = carry.get((f["rule_code"], f["span_start"], f["span_end"], f["excerpt"]))
        if prev:
            for k in ("decision", "decision_by", "decision_reason", "final_text", "apply_start", "apply_end", "decided_at"):
                row[k] = prev[k]
        db.insert("findings", row)
    db.update("content_versions", v["id"], {"analysis": jdump({"summary": result["summary"], "claims": result["claims"]})})
    for ev in result["ai_events"]:
        audit.ai_log(db, content_id, ev["step"], ev["engine"], ev["model"], ev["data_sent"], ev["masked"],
                     f"version {version}")
    audit.log(db, "system", "analysis.run", "content", content_id,
              {"version": version, "findings": len(result["findings"]), "score": result["summary"]["score"]})
    return result


def create_content(db, cfg, user, title, fmt, text, meta=None, channel="website", ai_assisted=False, filename="", llm=None):
    title = (title or "").strip()
    if not title:
        raise AppError("Please give the content a title.")
    if fmt in ("image",) and not (text or "").strip() and not (meta or {}).get("width"):
        raise AppError("Nothing to review.")
    if fmt not in ("image", "pptx", "pdf", "docx") and not (text or "").strip():
        raise AppError("The content is empty.")
    now = clock.now()
    cid = db.insert("contents", {"title": title, "fmt": fmt, "owner_id": user["id"], "status": "draft",
                                 "current_version": 1, "channel": channel or "website",
                                 "ai_assisted": 1 if ai_assisted else 0, "filename": filename,
                                 "created_at": now, "updated_at": now})
    db.insert("content_versions", {"content_id": cid, "version": 1, "text": text or "", "meta": jdump(meta or {}),
                                   "note": "First upload", "created_by": user["id"], "created_at": now})
    audit.log(db, user["name"], "content.create", "content", cid, {"title": title, "fmt": fmt})
    run_analysis(db, cfg, cid, 1, llm)
    return cid


def add_version(db, cfg, user, content_id, text, note="", llm=None, meta_updates=None):
    c = get_content(db, content_id)
    if not visible_to(c, user):
        raise AppError("Content not found.", 404)
    if c["owner_id"] != user["id"] and user["role"] not in ("manager", "admin"):
        raise AppError("Only the owner or a manager can change this content.", 403)
    if c["status"] == "in_review":
        raise AppError("This content is in review. Ask the reviewer to request changes first.", 409)
    if not (text or "").strip() and c["fmt"] in ("text", "markdown", "html"):
        raise AppError("The new text is empty.")
    cur = current_version(db, c)
    if text == cur["text"] and not meta_updates:
        raise AppError("Nothing changed.", 409)
    meta = {**cur["meta"], **(meta_updates or {})}
    nv = c["current_version"] + 1
    now = clock.now()
    db.insert("content_versions", {"content_id": content_id, "version": nv, "text": text, "meta": jdump(meta),
                                   "note": note or "Edited", "created_by": user["id"], "created_at": now})
    db.update("contents", content_id, {"current_version": nv, "status": "draft", "updated_at": now})
    audit.log(db, user["name"], "content.version", "content", content_id, {"version": nv, "note": note})
    run_analysis(db, cfg, content_id, nv, llm)
    return nv


# ---------------------------------------------------------------- decisions on findings
def decide(db, user, finding_id, decision, reason="", suggestion_index=None, final_text=None):
    f = db.one("SELECT * FROM findings WHERE id=?", (finding_id,))
    if not f:
        raise AppError("Finding not found.", 404)
    c = get_content(db, f["content_id"])
    if not visible_to(c, user):
        raise AppError("Content not found.", 404)
    if f["version"] != c["current_version"]:
        raise AppError("This finding belongs to an older version.", 409)
    if c["status"] in ("approved", "published"):
        raise AppError("This version is already approved. Create a new version to change it.", 409)
    if c["status"] == "in_review" and user["role"] == "creator":
        raise AppError("The content is in review. Only reviewers can decide now.", 403)
    if decision not in ("accepted", "edited", "rejected", "open"):
        raise AppError("Decision must be accepted, edited, rejected or open.")
    if decision == "rejected":
        if len((reason or "").strip()) < 3:
            raise AppError("Please give a short reason when you reject a finding.")
        if (f["human_lock"] or f["severity"] == "high") and not security.can(user["role"], "override"):
            raise AppError("Only a reviewer or manager can keep a locked or high-risk claim as written.", 403)
    upd = {"decision": decision, "decision_by": user["id"], "decision_reason": (reason or "").strip(),
           "decided_at": clock.now(), "final_text": None, "apply_start": None, "apply_end": None}
    if decision == "accepted" and suggestion_index is not None:
        sugg = jload(f["suggestions"], [])
        try:
            s = sugg[int(suggestion_index)]
        except (IndexError, ValueError, TypeError):
            raise AppError("That suggestion does not exist.")
        if s["kind"] == "replace":
            sp = s.get("span") or [f["span_start"], f["span_end"]]
            upd.update(final_text=s["replacement"], apply_start=sp[0], apply_end=sp[1])
    if decision == "edited":
        if final_text is None:
            raise AppError("Please provide your edited text.")
        upd.update(final_text=final_text, apply_start=f["span_start"], apply_end=f["span_end"])
    if decision == "open":
        upd.update(decision_by=None, decision_reason="", decided_at=None)
    db.update("findings", finding_id, upd)
    audit.log(db, user["name"], f"finding.{decision}", "finding", finding_id,
              {"rule": f["rule_code"], "content": f["content_id"], "reason": upd["decision_reason"]})
    return db.one("SELECT * FROM findings WHERE id=?", (finding_id,))


def apply_decisions(db, cfg, user, content_id, llm=None):
    """Build the next version by applying accepted and edited text changes. Returns (version, skipped)."""
    c = get_content(db, content_id)
    if not visible_to(c, user):
        raise AppError("Content not found.", 404)
    cur = current_version(db, c)
    todo = [f for f in findings_for(db, content_id, c["current_version"])
            if f["decision"] in ("accepted", "edited") and f["final_text"] is not None]
    if not todo:
        raise AppError("There are no accepted or edited text changes to apply.", 409)
    text, skipped, last_start = cur["text"], [], None
    for f in sorted(todo, key=lambda x: (x["apply_start"], x["apply_end"]), reverse=True):
        if last_start is not None and f["apply_end"] > last_start:
            skipped.append(f["id"])
            continue
        text = text[:f["apply_start"]] + f["final_text"] + text[f["apply_end"]:]
        last_start = f["apply_start"]
    text = clean_gap(text, 0) if any(f["final_text"] == "" for f in todo) else text
    nv = add_version(db, cfg, user, content_id, text, f"Applied {len(todo) - len(skipped)} decision(s)", llm)
    return nv, skipped


# ---------------------------------------------------------------- review flow
def allowed_actions(db, c, user):
    own = c["owner_id"] == user["id"]
    manage = user["role"] in ("manager", "admin")
    blocking = len(blocking_findings(db, c["id"], c["current_version"]))
    st = c["status"]
    return {
        "edit": (own or manage) and st != "in_review",
        "decide": st in ("draft", "changes_requested", "in_review") and (user["role"] != "creator" or st != "in_review"),
        "submit": (own or manage) and st in ("draft", "changes_requested"),
        "approve": st == "in_review" and not own and security.can(user["role"], "approve"),
        "request_changes": st == "in_review" and not own and security.can(user["role"], "approve"),
        "publish": st == "approved" and security.can(user["role"], "publish"),
        "blocking_count": blocking,
    }


def submit(db, user, content_id, note=""):
    c = get_content(db, content_id)
    if not visible_to(c, user):
        raise AppError("Content not found.", 404)
    if c["owner_id"] != user["id"] and user["role"] not in ("manager", "admin"):
        raise AppError("Only the owner or a manager can submit this content.", 403)
    if c["status"] not in ("draft", "changes_requested"):
        raise AppError(f"Content in status '{c['status']}' cannot be submitted.", 409)
    db.update("contents", content_id, {"status": "in_review", "updated_at": clock.now()})
    audit.log(db, user["name"], "content.submit", "content", content_id, {"note": note})
    return get_content(db, content_id)


def approve(db, user, content_id, note=""):
    c = get_content(db, content_id)
    if c["status"] != "in_review":
        raise AppError("Only content in review can be approved.", 409)
    if not security.can(user["role"], "approve"):
        raise AppError("Your role cannot approve content.", 403)
    if c["owner_id"] == user["id"]:
        raise AppError("You cannot approve your own content. Another person must review it.", 403)
    open_ = blocking_findings(db, content_id, c["current_version"])
    if open_:
        raise AppError(f"{len(open_)} finding(s) that need a human decision are still open.", 409,
                       {"open_findings": [f["id"] for f in open_]})
    locked = [f for f in findings_for(db, content_id, c["current_version"]) if f["human_lock"]]
    if locked and not security.can(user["role"], "approve_locked"):
        raise AppError("This content has legal or price-related claims. A reviewer must approve it.", 403)
    db.insert("approvals", {"content_id": content_id, "version": c["current_version"], "user_id": user["id"],
                            "decision": "approved", "note": note, "created_at": clock.now()})
    db.update("contents", content_id, {"status": "approved", "updated_at": clock.now()})
    audit.log(db, user["name"], "content.approve", "content", content_id, {"version": c["current_version"], "note": note})
    return get_content(db, content_id)


def request_changes(db, user, content_id, note):
    c = get_content(db, content_id)
    if c["status"] != "in_review":
        raise AppError("Only content in review can be sent back.", 409)
    if not security.can(user["role"], "approve") or c["owner_id"] == user["id"]:
        raise AppError("You cannot review this content.", 403)
    if len((note or "").strip()) < 3:
        raise AppError("Please explain what should change.")
    db.insert("approvals", {"content_id": content_id, "version": c["current_version"], "user_id": user["id"],
                            "decision": "changes_requested", "note": note, "created_at": clock.now()})
    db.update("contents", content_id, {"status": "changes_requested", "updated_at": clock.now()})
    audit.log(db, user["name"], "content.request_changes", "content", content_id, {"note": note})
    return get_content(db, content_id)


def publish(db, cfg, user, content_id):
    from . import passports
    c = get_content(db, content_id)
    if not security.can(user["role"], "publish"):
        raise AppError("Only a manager or admin can publish.", 403)
    if c["status"] != "approved":
        raise AppError("Only approved content can be published.", 409)
    if blocking_findings(db, content_id, c["current_version"]):
        raise AppError("There are still open findings that need a decision.", 409)
    pub_id = passports.publish_snapshot(db, cfg, user, c)
    db.update("contents", content_id, {"status": "published", "published_at": clock.now(),
                                       "updated_at": clock.now(), "needs_refresh": 0})
    db.run("UPDATE refresh_proposals SET status='superseded' WHERE content_id=? AND status='open'", (content_id,))
    audit.log(db, user["name"], "content.publish", "content", content_id, {"publication": pub_id})
    return get_content(db, content_id)


# ---------------------------------------------------------------- comments and diff
def add_comment(db, user, content_id, body, anchor=None):
    c = get_content(db, content_id)
    if not visible_to(c, user):
        raise AppError("Content not found.", 404)
    if len((body or "").strip()) < 1:
        raise AppError("Comment is empty.")
    a = anchor or [None, None]
    cid = db.insert("comments", {"content_id": content_id, "version": c["current_version"], "author_id": user["id"],
                                 "body": body.strip(), "anchor_start": a[0], "anchor_end": a[1], "created_at": clock.now()})
    audit.log(db, user["name"], "comment.add", "content", content_id)
    return cid


def list_comments(db, content_id):
    return db.q("SELECT m.*, u.name AS author FROM comments m JOIN users u ON u.id=m.author_id "
                "WHERE m.content_id=? ORDER BY m.id", (content_id,))


def diff(db, content_id, v1, v2):
    rows = {r["version"]: r["text"] for r in db.q("SELECT version, text FROM content_versions WHERE content_id=?", (content_id,))}
    if v1 not in rows or v2 not in rows:
        raise AppError("Version not found.", 404)
    a, b = re.findall(r"\s+|\S+", rows[v1]), re.findall(r"\s+|\S+", rows[v2])
    ops = []
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
        ops.append({"op": tag, "old": "".join(a[i1:i2]), "new": "".join(b[j1:j2])})
    return {"from": v1, "to": v2, "ops": ops, "changed": any(o["op"] != "equal" for o in ops)}
