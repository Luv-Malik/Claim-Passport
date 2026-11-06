"""One place for 'today', so tests and demos can freeze time with CP_TODAY=YYYY-MM-DD."""
import datetime as dt
import os


def today():
    v = os.environ.get("CP_TODAY")
    return dt.date.fromisoformat(v) if v else dt.date.today()


def now():
    t = dt.datetime.now(dt.timezone.utc).replace(microsecond=0)
    if os.environ.get("CP_TODAY"):
        t = t.replace(year=today().year, month=today().month, day=today().day)
    return t.strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_date(s):
    if not s:
        return None
    try:
        return dt.date.fromisoformat(str(s)[:10])
    except ValueError:
        return None
