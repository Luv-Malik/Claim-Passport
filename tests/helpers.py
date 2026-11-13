import os
import sys
import tempfile
from pathlib import Path

os.environ["CP_TODAY"] = "2026-11-02"
os.environ["CP_PBKDF2_ITERS"] = "1000"
os.environ["CP_SCHEDULER"] = "0"           # tests start the scheduler themselves when they need it
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from claimpassport import seed, vault  # noqa: E402
from claimpassport.db import DB  # noqa: E402


PG_URL = os.environ.get("CP_TEST_DB_URL", "")      # set it to run the whole suite on a real PostgreSQL server


def new_db():
    """A fresh empty database: in memory on SQLite, or a wiped schema on PostgreSQL when CP_TEST_DB_URL is set."""
    if PG_URL:
        from tests import pg_shim
        pg_shim.reset(PG_URL)
        return DB(PG_URL, pg_shim)
    return DB(":memory:")


def demo_db():
    """A fresh database filled with the demo data."""
    db = new_db()
    db.init()
    seed.seed_demo(db, {})
    return db


def empty_db():
    db = new_db()
    db.init()
    vault.ensure_builtin_rules(db)
    return db


def user(db, email):
    return db.one("SELECT * FROM users WHERE email=?", (email,))


def temp_app(**over):
    from claimpassport.api import create_app
    d = tempfile.mkdtemp()
    cfg = {"DB_PATH": os.path.join(d, "t.db"), "UPLOAD_DIR": os.path.join(d, "up"), "ANTHROPIC_API_KEY": "",
           "DATABASE_URL": "", "SCHEDULER": False}
    if PG_URL:
        from tests import pg_shim
        pg_shim.reset(PG_URL)
        cfg.update(DATABASE_URL=PG_URL, DB_DRIVER=pg_shim)
    cfg.update(over)
    return create_app(cfg)


def login(client, email, password="demo1234"):
    r = client.post("/api/login", json={"email": email, "password": password})
    return {"Authorization": "Bearer " + r.get_json()["token"]}
