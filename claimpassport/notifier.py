"""Alerts outside the app: email, Slack and a signed webhook, plus the weekly digest.

How it works
- Every in-app notification also puts one row in `alert_queue` (see watcher.notify).
- `process_queue` sends the waiting rows. Each person chooses their channels in Settings (`notification_prefs`).
  Slack and webhook addresses are organisation settings (admin), stored encrypted.
- Every attempt is written to `alert_deliveries`, so you can see what was sent, to whom, and any error.
- A failed send is retried on the next run, up to MAX_ATTEMPTS times. A channel that already succeeded for a row is
  never sent twice.
- A Slack or webhook alert for the same event is sent once for the whole organisation, not once per person."""
import hashlib
import hmac
import json
import smtplib
import ssl
import urllib.request
from email.message import EmailMessage
from urllib.parse import urlparse

from . import audit, clock, passports, settings
from .db import jdump
from .errors import AppError

MAX_ATTEMPTS = 3
CHANNELS = ("email", "slack", "webhook")
DEFAULT_PREFS = {"email_enabled": 1, "slack_enabled": 1, "webhook_enabled": 0, "digest_enabled": 1}


# ---------------------------------------------------------------- settings and preferences
def get_prefs(db, user_id):
    row = db.one("SELECT * FROM notification_prefs WHERE user_id=?", (user_id,)) or {}
    return {k: int(row.get(k, v)) for k, v in DEFAULT_PREFS.items()}


def set_prefs(db, user_id, data):
    cur = get_prefs(db, user_id)
    for k in DEFAULT_PREFS:
        if k in data:
            cur[k] = 1 if data[k] else 0
    if db.one("SELECT user_id FROM notification_prefs WHERE user_id=?", (user_id,)):
        db.run("UPDATE notification_prefs SET email_enabled=?, slack_enabled=?, webhook_enabled=?, digest_enabled=?, updated_at=? "
               "WHERE user_id=?", (cur["email_enabled"], cur["slack_enabled"], cur["webhook_enabled"], cur["digest_enabled"],
                                   clock.now(), user_id))
    else:
        db.run("INSERT INTO notification_prefs(user_id, email_enabled, slack_enabled, webhook_enabled, digest_enabled, updated_at) "
               "VALUES(?,?,?,?,?,?)", (user_id, cur["email_enabled"], cur["slack_enabled"], cur["webhook_enabled"],
                                       cur["digest_enabled"], clock.now()))
    return cur


def slack_url(db, cfg):
    return settings.get_secret(db, cfg, "slack_webhook_url") or cfg.get("SLACK_WEBHOOK_URL") or ""


def webhook_target(db, cfg):
    url = settings.get_secret(db, cfg, "webhook_url") or cfg.get("WEBHOOK_URL") or ""
    secret = settings.get_secret(db, cfg, "webhook_secret") or cfg.get("WEBHOOK_SECRET") or ""
    return url, secret


def channel_status(db, cfg):
    """Which channels are set up (never reveals the addresses themselves)."""
    return {"email": bool(cfg.get("SMTP_HOST")), "slack": bool(slack_url(db, cfg)), "webhook": bool(webhook_target(db, cfg)[0])}


def check_url(url):
    p = urlparse(url or "")
    if p.scheme not in ("http", "https") or not p.netloc:
        raise AppError("The address must start with http:// or https://")
    return url


# ---------------------------------------------------------------- senders (each raises on failure)
def send_email(cfg, to, subject, body):
    msg = EmailMessage()
    msg["From"], msg["To"], msg["Subject"] = cfg.get("SMTP_FROM") or "claim-passport@localhost", to, subject
    msg.set_content(body)
    mode = (cfg.get("SMTP_TLS") or "starttls").lower()
    host, port = cfg["SMTP_HOST"], int(cfg.get("SMTP_PORT") or 587)
    if mode == "ssl":
        smtp = smtplib.SMTP_SSL(host, port, timeout=15, context=ssl.create_default_context())
    else:
        smtp = smtplib.SMTP(host, port, timeout=15)
    try:
        if mode == "starttls":
            smtp.starttls(context=ssl.create_default_context())
        if cfg.get("SMTP_USER"):
            smtp.login(cfg["SMTP_USER"], cfg.get("SMTP_PASSWORD", ""))
        smtp.send_message(msg)
    finally:
        try:
            smtp.quit()
        except Exception:
            pass


def _post_json(url, payload, headers=None):
    check_url(url)
    req = urllib.request.Request(url, data=json.dumps(payload).encode(), method="POST",
                                 headers={"Content-Type": "application/json", **(headers or {})})
    with urllib.request.urlopen(req, timeout=10) as r:
        if r.status >= 300:
            raise RuntimeError(f"HTTP {r.status}")
        return r.status


def send_slack(url, text):
    return _post_json(url, {"text": text})


def sign(secret, body_bytes):
    return "sha256=" + hmac.new(secret.encode(), body_bytes, hashlib.sha256).hexdigest()


def send_webhook(url, secret, payload):
    """POST JSON. When a secret is set, `X-CP-Signature: sha256=<hmac of the body>` lets the receiver verify it."""
    check_url(url)
    body = json.dumps(payload, sort_keys=True).encode()
    headers = {"Content-Type": "application/json"}
    if secret:
        headers["X-CP-Signature"] = sign(secret, body)
    req = urllib.request.Request(url, data=body, method="POST", headers=headers)
    with urllib.request.urlopen(req, timeout=10) as r:
        if r.status >= 300:
            raise RuntimeError(f"HTTP {r.status}")
        return r.status


# ---------------------------------------------------------------- queue
def enqueue(db, user_id, message, link="", ref="", kind="alert"):
    return db.insert("alert_queue", {"user_id": user_id, "message": message, "link": link, "ref": ref, "kind": kind,
                                     "status": "pending", "created_at": clock.now()})


def _full_link(cfg, link):
    return (cfg.get("PUBLIC_URL") or "").rstrip("/") + "/" + (link or "")


def _log(db, queue_id, user_id, channel, target, subject, status, error=""):
    db.insert("alert_deliveries", {"queue_id": queue_id, "user_id": user_id, "channel": channel, "target": target,
                                   "subject": subject[:200], "status": status, "error": str(error)[:300], "ts": clock.now()})


def _already_sent_for_ref(db, channel, ref, queue_id):
    if not ref:
        return False
    return bool(db.one("SELECT d.id FROM alert_deliveries d JOIN alert_queue q ON q.id=d.queue_id "
                       "WHERE d.channel=? AND d.status='sent' AND q.ref=? AND q.id<>?", (channel, ref, queue_id)))


def process_queue(db, cfg, limit=200):
    """Send waiting alerts. Returns {"delivered": n, "failed": n, "skipped": n} counting delivery attempts."""
    status = channel_status(db, cfg)
    surl = slack_url(db, cfg)
    wurl, wsecret = webhook_target(db, cfg)
    out = {"delivered": 0, "failed": 0, "skipped": 0}
    rows = db.q("SELECT * FROM alert_queue WHERE status='pending' ORDER BY id LIMIT ?", (limit,))
    for row in rows:
        user = db.one("SELECT id, name, email FROM users WHERE id=?", (row["user_id"],))
        if not user:
            db.update("alert_queue", row["id"], {"status": "skipped", "processed_at": clock.now()})
            continue
        prefs = get_prefs(db, user["id"])
        done = {d["channel"] for d in db.q("SELECT channel FROM alert_deliveries WHERE queue_id=? AND status='sent'", (row["id"],))}
        text = row["message"] + (("\n" + _full_link(cfg, row["link"])) if row["link"] else "")
        subject = "Claim Passport weekly digest" if row["kind"] == "digest" else "Claim Passport alert: " + row["message"][:80]
        wanted, failed_now, sent_now = [], False, 0
        if status["email"] and prefs["email_enabled"] and user["email"] and (row["kind"] == "digest" and prefs["digest_enabled"] or row["kind"] != "digest"):
            wanted.append(("email", user["email"]))
        if row["kind"] != "digest":
            if status["slack"] and prefs["slack_enabled"]:
                wanted.append(("slack", "slack webhook"))
            if status["webhook"] and prefs["webhook_enabled"]:
                wanted.append(("webhook", "webhook"))
        for channel, target in wanted:
            if channel in done:
                continue
            if channel in ("slack", "webhook") and _already_sent_for_ref(db, channel, row["ref"], row["id"]):
                _log(db, row["id"], user["id"], channel, target, subject, "skipped", "already sent for this event")
                out["skipped"] += 1
                continue
            try:
                if channel == "email":
                    send_email(cfg, user["email"], subject, text)
                elif channel == "slack":
                    send_slack(surl, ":warning: " + text)
                else:
                    send_webhook(wurl, wsecret, {"event": "claim_passport." + row["kind"], "message": row["message"],
                                                 "link": _full_link(cfg, row["link"]), "ref": row["ref"], "queued_at": row["created_at"]})
                _log(db, row["id"], user["id"], channel, target, subject, "sent")
                out["delivered"] += 1
                sent_now += 1
            except Exception as exc:                       # network, auth, bad address...
                _log(db, row["id"], user["id"], channel, target, subject, "failed", f"{type(exc).__name__}: {exc}")
                out["failed"] += 1
                failed_now = True
        attempts = row["attempts"] + (1 if failed_now else 0)
        if failed_now:
            final = "failed" if attempts >= MAX_ATTEMPTS else "pending"
        else:
            final = "sent" if (sent_now or done) else "no_channel"
        db.update("alert_queue", row["id"], {"status": final, "attempts": attempts,
                                             "processed_at": clock.now() if final != "pending" else None})
    return out


# ---------------------------------------------------------------- weekly digest
def _week_key(today):
    y, w, _ = today.isocalendar()
    return f"{y}-W{w:02d}"


def build_digest(db, cfg, user, today=None):
    """Plain-text summary for one person: what needs attention and what is about to go stale."""
    today = today or clock.today()
    own = user["id"] if user["role"] == "creator" else None
    debt = passports.truth_debt(db, today, cfg.get("EXPIRY_WARN_DAYS", 14), owner_id=own)
    c = debt["counts"]
    lines = [f"Claim Passport weekly digest for {today.isoformat()}", ""]
    if debt["total"]:
        lines.append(f"Truth Debt: {debt['score']}% ({debt['bad']} of {debt['total']} live claims need attention).")
    else:
        lines.append("You have no live claim passports yet.")
    lines.append(f"- Source changed: {c['source_changed']}   Source expired: {c['expired']}   "
                 f"Expiring soon: {c['expiring']}   Approved without a source: {c['override']}")
    props = [p for p in db.q("SELECT r.id, c.title, c.owner_id FROM refresh_proposals r JOIN contents c ON c.id=r.content_id "
                             "WHERE r.status='open'") if own is None or p["owner_id"] == own]
    if props:
        lines += ["", f"Pages waiting for a fix ({len(props)}):"] + [f"- {p['title']}" for p in props[:8]]
    if user["role"] in ("manager", "admin", "reviewer"):
        soon = [h for h in passports.half_life(db, today) if h["days_left"] <= 30][:8]
        if soon:
            lines += ["", "Facts likely to need a re-check in the next 30 days:"]
            lines += [f"- {h['key']} ({'overdue' if h['days_left'] < 0 else 'in %d days' % h['days_left']}, used in {h['live_uses']} live claim(s))" for h in soon]
    return "\n".join(lines), debt


def send_weekly_digests(db, cfg, today=None):
    """Queue one digest per person who wants it (once per ISO week). Returns how many were queued."""
    today = today or clock.today()
    week, n = _week_key(today), 0
    for u in db.q("SELECT id, name, email, role FROM users"):
        if not get_prefs(db, u["id"])["digest_enabled"]:
            continue
        ref = f"digest:{week}:{u['id']}"
        if db.one("SELECT id FROM alert_queue WHERE ref=?", (ref,)):
            continue
        text, debt = build_digest(db, cfg, u, today)
        if u["role"] == "creator" and not debt["total"]:
            continue
        enqueue(db, u["id"], text, "#/passports", ref, "digest")
        n += 1
    audit.log(db, "system", "digest.queued", "system", None, {"week": week, "count": n})
    return n


def send_test(db, cfg, user):
    """Send a test message through every channel that is set up. Returns {channel: "sent" or the error}."""
    status, out = channel_status(db, cfg), {}
    text = f"Test alert from Claim Passport, sent by {user['name']}. If you can read this, this channel works."
    tries = {"email": lambda: send_email(cfg, user["email"], "Claim Passport test alert", text),
             "slack": lambda: send_slack(slack_url(db, cfg), ":white_check_mark: " + text),
             "webhook": lambda: send_webhook(webhook_target(db, cfg)[0], webhook_target(db, cfg)[1],
                                             {"event": "claim_passport.test", "message": text})}
    for ch in CHANNELS:
        if not status[ch]:
            out[ch] = "not set up"
            continue
        try:
            tries[ch]()
            out[ch] = "sent"
        except Exception as exc:
            out[ch] = f"{type(exc).__name__}: {exc}"
    return out
