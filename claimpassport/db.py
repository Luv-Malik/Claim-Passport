"""Small database layer for SQLite (default) and PostgreSQL.

The SQL in the app is plain and standard. Queries are written with `?` placeholders; for PostgreSQL they are
translated to `%s` here. The schema comes from versioned migrations (see migrations.py), not from this file.

Choose the database with CP_DATABASE_URL (for example postgresql://user:pass@host:5432/claimpassport).
If it is empty, the SQLite file in CP_DB_PATH is used."""
import json
import sqlite3
import threading
from pathlib import Path

# Tables whose primary key is not an auto-numbered `id` column (so INSERT must not ask for RETURNING id).
NO_ID_TABLES = {"settings", "notification_prefs", "schema_migrations"}


def jdump(v):
    return json.dumps(v, ensure_ascii=False)


def jload(s, default=None):
    if s in (None, ""):
        return default
    try:
        return json.loads(s)
    except (TypeError, ValueError):
        return default


def is_pg_url(target):
    return str(target).lower().startswith(("postgres://", "postgresql://"))


def to_pg(sql):
    """`?` -> `%s` and a literal `%` -> `%%`, leaving text inside single quotes alone for `?` only."""
    out, in_str = [], False
    for ch in sql:
        if ch == "'":
            in_str = not in_str
            out.append(ch)
        elif ch == "%":
            out.append("%%")
        elif ch == "?" and not in_str:
            out.append("%s")
        else:
            out.append(ch)
    return "".join(out)


def _load_psycopg():
    try:
        import psycopg
        from psycopg.rows import dict_row
    except ImportError as exc:                                   # pragma: no cover - depends on the install
        raise RuntimeError("PostgreSQL needs the 'psycopg' package: pip install 'psycopg[binary]'") from exc

    class _Driver:
        KIND = "psycopg3"

        @staticmethod
        def connect(url):
            return psycopg.connect(url, autocommit=True, row_factory=dict_row)
    return _Driver


class DB:
    def __init__(self, target, driver=None):
        self.target = str(target)
        self.path = self.target                      # kept for older code
        self.pg = is_pg_url(self.target)
        self.lock = threading.RLock()
        if self.pg:
            self.driver = driver or _load_psycopg()
            self.conn = self.driver.connect(self.target)
        else:
            if self.target != ":memory:":
                Path(self.target).parent.mkdir(parents=True, exist_ok=True)
            self.conn = sqlite3.connect(self.target, check_same_thread=False)
            self.conn.row_factory = sqlite3.Row
            self.conn.execute("PRAGMA foreign_keys=ON")

    @property
    def kind(self):
        return "postgresql" if self.pg else "sqlite"

    # ------------------------------------------------------------ schema
    def exec_ddl(self, statements):
        """Run one or more schema statements. `{PK}` becomes the right auto-number column for this database."""
        if isinstance(statements, str):
            statements = [statements]
        pk = "SERIAL PRIMARY KEY" if self.pg else "INTEGER PRIMARY KEY AUTOINCREMENT"
        with self.lock:
            for st in statements:
                st = st.replace("{PK}", pk)
                if self.pg:
                    self.conn.execute(to_pg(st), ())
                else:
                    self.conn.execute(st)
            if not self.pg:
                self.conn.commit()

    def init(self):
        from . import migrations
        migrations.migrate(self)

    # ------------------------------------------------------------ queries
    @staticmethod
    def _params(params):
        return tuple(int(p) if isinstance(p, bool) else p for p in params)

    def q(self, sql, params=()):
        with self.lock:
            if self.pg:
                cur = self.conn.execute(to_pg(sql), self._params(params))
                return [dict(r) for r in cur.fetchall()] if cur.description else []
            return [dict(r) for r in self.conn.execute(sql, self._params(params)).fetchall()]

    def one(self, sql, params=()):
        rows = self.q(sql, params)
        return rows[0] if rows else None

    def run(self, sql, params=()):
        """Run a write. Returns the new row id for INSERTs, otherwise the number of rows changed."""
        with self.lock:
            if self.pg:
                text = sql.strip()
                if text[:6].upper() == "INSERT" and " RETURNING " not in text.upper():
                    table = text.split()[2].split("(")[0].lower()
                    if table not in NO_ID_TABLES:
                        text += " RETURNING id"
                cur = self.conn.execute(to_pg(text), self._params(params))
                if cur.description:
                    rows = cur.fetchall()
                    return rows[0]["id"] if rows else None
                return cur.rowcount
            cur = self.conn.execute(sql, self._params(params))
            self.conn.commit()
            return cur.lastrowid if sql.lstrip()[:6].upper() == "INSERT" else cur.rowcount

    def insert(self, table, data):
        cols = ",".join(data)
        marks = ",".join("?" * len(data))
        return self.run(f"INSERT INTO {table}({cols}) VALUES({marks})", tuple(data.values()))

    def update(self, table, row_id, data):
        if not data:
            return
        sets = ",".join(f"{k}=?" for k in data)
        self.run(f"UPDATE {table} SET {sets} WHERE id=?", (*data.values(), row_id))

    def close(self):
        self.conn.close()
