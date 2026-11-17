"""Small database layer for SQLite (default) and PostgreSQL.

Queries are written with `?` placeholders. For PostgreSQL they are
translated to `%s` here. The schema comes from versioned migrations
(see migrations.py), not from this file.

Choose the database with CP_DATABASE_URL, for example
postgresql://user:pass@host:5432/claimpassport.
If it is empty, the SQLite file in CP_DB_PATH is used."""
import json
import sqlite3
import threading
import time
from pathlib import Path

# Tables with no auto-numbered id column.
# INSERT into these must not use RETURNING id.
NO_ID_TABLES = {"settings", "notification_prefs", "schema_migrations"}

# How many times to retry a SQLite write that hits a lock.
LOCK_RETRIES = 5


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
    """Turn `?` into `%s` and a literal `%` into `%%`.
    A `?` inside single quotes is left alone."""
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
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(
            "PostgreSQL needs the 'psycopg' package: "
            "pip install 'psycopg[binary]'"
        ) from exc

    class _Driver:
        KIND = "psycopg3"

        @staticmethod
        def connect(url):
            return psycopg.connect(url, autocommit=True, row_factory=dict_row)
    return _Driver


class DB:
    def __init__(self, target, driver=None):
        self.target = str(target)
        self.path = self.target  # kept for older code
        self.pg = is_pg_url(self.target)
        self.lock = threading.RLock()
        if self.pg:
            self.driver = driver or _load_psycopg()
            self.conn = self.driver.connect(self.target)
        else:
            if self.target != ":memory:":
                Path(self.target).parent.mkdir(parents=True, exist_ok=True)
            # isolation_level=None is autocommit: every statement ends
            # right away, so no transaction is left open holding a lock.
            # timeout=30 waits up to 30s for a lock instead of 5s.
            self.conn = sqlite3.connect(
                self.target,
                timeout=30,
                check_same_thread=False,
                isolation_level=None,
            )
            self.conn.row_factory = sqlite3.Row
            self.conn.execute("PRAGMA foreign_keys=ON")
            self.conn.execute("PRAGMA busy_timeout=30000")
            if self.target != ":memory:":
                try:
                    self.conn.execute("PRAGMA journal_mode=WAL")
                    self.conn.execute("PRAGMA synchronous=NORMAL")
                except sqlite3.OperationalError:
                    pass  # fall back to the default journal mode

    @property
    def kind(self):
        return "postgresql" if self.pg else "sqlite"

    # ---------------------------------------------------------- helpers
    def _sqlite_exec(self, sql, params=()):
        """Run one SQLite statement, retrying if the database is locked."""
        for attempt in range(LOCK_RETRIES):
            try:
                return self.conn.execute(sql, params)
            except sqlite3.OperationalError as exc:
                locked = "locked" in str(exc).lower()
                if locked and attempt < LOCK_RETRIES - 1:
                    time.sleep(0.5 * (attempt + 1))
                    continue
                raise

    # ---------------------------------------------------------- schema
    def exec_ddl(self, statements):
        """Run schema statements.
        `{PK}` becomes the right auto-number column for this database."""
        if isinstance(statements, str):
            statements = [statements]
        if self.pg:
            pk = "SERIAL PRIMARY KEY"
        else:
            pk = "INTEGER PRIMARY KEY AUTOINCREMENT"
        with self.lock:
            for st in statements:
                st = st.replace("{PK}", pk)
                if self.pg:
                    self.conn.execute(to_pg(st), ())
                else:
                    self._sqlite_exec(st)

    def init(self):
        from . import migrations
        migrations.migrate(self)

    # --------------------------------------------------------- queries
    @staticmethod
    def _params(params):
        return tuple(int(p) if isinstance(p, bool) else p for p in params)

    def q(self, sql, params=()):
        with self.lock:
            if self.pg:
                cur = self.conn.execute(to_pg(sql), self._params(params))
                if cur.description:
                    return [dict(r) for r in cur.fetchall()]
                return []
            cur = self._sqlite_exec(sql, self._params(params))
            return [dict(r) for r in cur.fetchall()]

    def one(self, sql, params=()):
        rows = self.q(sql, params)
        return rows[0] if rows else None

    def run(self, sql, params=()):
        """Run a write.
        Returns the new row id for INSERTs, else the rows changed."""
        with self.lock:
            if self.pg:
                text = sql.strip()
                is_insert = text[:6].upper() == "INSERT"
                if is_insert and " RETURNING " not in text.upper():
                    table = text.split()[2].split("(")[0].lower()
                    if table not in NO_ID_TABLES:
                        text += " RETURNING id"
                cur = self.conn.execute(to_pg(text), self._params(params))
                if cur.description:
                    rows = cur.fetchall()
                    return rows[0]["id"] if rows else None
                return cur.rowcount
            cur = self._sqlite_exec(sql, self._params(params))
            if sql.lstrip()[:6].upper() == "INSERT":
                return cur.lastrowid
            return cur.rowcount

    def insert(self, table, data):
        cols = ",".join(data)
        marks = ",".join("?" * len(data))
        sql = f"INSERT INTO {table}({cols}) VALUES({marks})"
        return self.run(sql, tuple(data.values()))

    def update(self, table, row_id, data):
        if not data:
            return
        sets = ",".join(f"{k}=?" for k in data)
        sql = f"UPDATE {table} SET {sets} WHERE id=?"
        self.run(sql, (*data.values(), row_id))

    def close(self):
        self.conn.close()
