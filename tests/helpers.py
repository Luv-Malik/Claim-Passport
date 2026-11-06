import os
import sys
import tempfile
from pathlib import Path

os.environ["CP_TODAY"] = "2026-11-02"
os.environ["CP_PBKDF2_ITERS"] = "1000"
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from claimpassport import seed, vault  # noqa: E402
from claimpassport.db import DB  # noqa: E402


def demo_db():
    """A fresh in-memory database filled with the demo data."""
    db = DB(":memory:")
    db.init()
    seed.seed_demo(db, {})
    return db


def empty_db():
    db = DB(":memory:")
    db.init()
    vault.ensure_builtin_rules(db)
    return db


def user(db, email):
    return db.one("SELECT * FROM users WHERE email=?", (email,))


def temp_app(**over):
    from claimpassport.api import create_app
    d = tempfile.mkdtemp()
    cfg = {"DB_PATH": os.path.join(d, "t.db"), "UPLOAD_DIR": os.path.join(d, "up"), "ANTHROPIC_API_KEY": ""}
    cfg.update(over)
    return create_app(cfg)


def login(client, email, password="demo1234"):
    r = client.post("/api/login", json={"email": email, "password": password})
    return {"Authorization": "Bearer " + r.get_json()["token"]}
