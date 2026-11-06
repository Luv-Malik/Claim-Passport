"""Audit trail (who did what) and AI transparency log (which AI/service touched which data)."""
from . import clock
from .db import jdump


def log(db, actor, action, entity, entity_id=None, detail=None):
    db.insert("audit_log", {"ts": clock.now(), "actor": actor or "system", "action": action,
                            "entity": entity, "entity_id": entity_id,
                            "detail": jdump(detail) if detail is not None else ""})


def ai_log(db, content_id, step, engine, model, data_sent, masked_items=0, note=""):
    db.insert("ai_log", {"ts": clock.now(), "content_id": content_id, "step": step, "engine": engine,
                         "model": model, "data_sent": data_sent, "masked_items": masked_items, "note": note})
