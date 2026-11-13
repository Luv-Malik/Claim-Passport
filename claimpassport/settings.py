"""Small key-value settings stored in the database, so admins can change them without restarting.
Secrets (Slack and webhook addresses) are stored encrypted."""
from . import clock, crypto
from .db import jdump, jload

SECRET_KEYS = {"slack_webhook_url", "webhook_url", "webhook_secret"}


def get(db, key, default=None):
    row = db.one("SELECT value FROM settings WHERE key=?", (key,))
    return default if row is None else row["value"]


def put(db, key, value, actor=None):
    value = "" if value is None else str(value)
    if db.one("SELECT key FROM settings WHERE key=?", (key,)):
        db.run("UPDATE settings SET value=?, updated_at=?, updated_by=? WHERE key=?", (value, clock.now(), actor or "", key))
    else:
        db.run("INSERT INTO settings(key, value, updated_at, updated_by) VALUES(?,?,?,?)", (key, value, clock.now(), actor or ""))


def get_json(db, key, default=None):
    return jload(get(db, key), default)


def put_json(db, key, value, actor=None):
    put(db, key, jdump(value), actor)


def get_secret(db, cfg, key):
    return crypto.open_text(cfg, get(db, key, "") or "")


def put_secret(db, cfg, key, value, actor=None):
    put(db, key, crypto.seal_text(cfg, value) if value else "", actor)


def hybrid_enabled(db, cfg):
    """Hybrid verification: the admin's choice if one was saved, otherwise the install default."""
    v = get(db, "hybrid_mode")
    if v in (None, ""):
        return bool((cfg or {}).get("HYBRID"))
    return v == "1"
