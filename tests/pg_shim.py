"""A test-only stand-in for the psycopg driver, so the whole test suite can run against a REAL PostgreSQL server
even where no Python PostgreSQL driver can be installed. It talks to the server through the `psql` program.

It is NOT used in production (production uses psycopg). It exists to check that our SQL and schema really run on
PostgreSQL. Typical use:

    CP_TEST_DB_URL="postgresql://postgres@/cptest?host=/tmp/pgtest&port=55432" python -m unittest discover -s tests -t .
"""
import itertools
import json
import os
import re
import shutil
import subprocess
from urllib.parse import parse_qs, urlparse

KIND = "psycopg3"
_counter = itertools.count(1)
_TAG = re.compile(r"^(?:INSERT \d+|UPDATE|DELETE|SELECT|MERGE) (\d+)$")


def psql_path():
    return shutil.which("psql") or "/usr/lib/postgresql/16/bin/psql"


def _args(url):
    u = urlparse(url)
    q = parse_qs(u.query)
    args = [psql_path(), "-X", "-A", "-t", "-v", "ON_ERROR_STOP=0", "-d", (u.path or "/postgres").lstrip("/") or "postgres"]
    host = q.get("host", [u.hostname or ""])[0]
    port = q.get("port", [str(u.port or 5432)])[0]
    if host:
        args += ["-h", host]
    args += ["-p", port, "-U", u.username or "postgres"]
    return args


def literal(v):
    if v is None:
        return "NULL"
    if isinstance(v, bool):
        return "1" if v else "0"
    if isinstance(v, (int, float)):
        return repr(v)
    return "'" + str(v).replace("'", "''") + "'"


def fill(sql, params):
    """Replace %s with SQL literals and %% with %. (Our DB layer already wrote the SQL in psycopg style.)"""
    out, i, n, p = [], 0, len(sql), iter(params)
    while i < n:
        two = sql[i:i + 2]
        if two == "%s":
            out.append(literal(next(p)))
            i += 2
        elif two == "%%":
            out.append("%")
            i += 2
        else:
            out.append(sql[i])
            i += 1
    return "".join(out)


class Cursor:
    def __init__(self, rows, rowcount):
        self._rows, self.rowcount = rows, rowcount
        self.description = [("col",)] if rows is not None else None

    def fetchall(self):
        return self._rows or []


class Connection:
    def __init__(self, url):
        self.p = subprocess.Popen(_args(url), stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                  text=True, bufsize=1)

    def _talk(self, text):
        marker = f"__END_{next(_counter)}__"
        self.p.stdin.write(text.rstrip().rstrip(";") + ";\n\\echo " + marker + "\n")
        self.p.stdin.flush()
        lines = []
        while True:
            line = self.p.stdout.readline()
            if line == "":
                raise RuntimeError("psql stopped unexpectedly")
            if line.strip() == marker:
                return lines
            lines.append(line.rstrip("\n"))

    def execute(self, sql, params=()):
        text = fill(sql, params)
        head = text.lstrip()[:7].upper()
        is_query = head.startswith(("SELECT", "WITH")) or " RETURNING " in text.upper()
        if is_query:
            lines = self._talk(f"WITH _t AS ({text.rstrip().rstrip(';')}) SELECT coalesce(jsonb_agg(to_jsonb(_t)), '[]'::jsonb) FROM _t")
            err = [x for x in lines if x.startswith(("ERROR:", "psql:"))]
            if err:
                raise RuntimeError("; ".join(err) + " | " + text[:200])
            payload = next((x for x in lines if x.startswith("[")), "[]")
            rows = json.loads(payload)
            return Cursor(rows, len(rows))
        lines = self._talk(text)
        err = [x for x in lines if x.startswith(("ERROR:", "psql:"))]
        if err:
            raise RuntimeError("; ".join(err) + " | " + text[:200])
        count = 0
        for x in lines:
            m = _TAG.match(x.strip())
            if m:
                count = int(m.group(1))
        return Cursor(None, count)

    def commit(self):          # every statement is already committed (autocommit)
        pass

    def rollback(self):
        pass

    def close(self):
        try:
            self.p.stdin.write("\\q\n")
            self.p.stdin.flush()
            self.p.wait(timeout=5)
        except Exception:
            self.p.kill()


def connect(url):
    return Connection(url)


def reset(url):
    """Empty the test database."""
    c = Connection(url)
    c.execute("DROP SCHEMA public CASCADE")
    c.execute("CREATE SCHEMA public")
    c.close()
