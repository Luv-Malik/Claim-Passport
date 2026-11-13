"""The scheduler: checks for expiring and changed facts by itself, then sends the alerts.

It runs inside the app as one background thread (so run ONE worker, or set CP_SCHEDULER=0 on the extra ones).
It runs a job
  - when the app starts, if the last scan is older than CP_SCAN_INTERVAL_HOURS,
  - every CP_SCAN_INTERVAL_HOURS after that,
  - straight after someone changes an approved fact (`kick("fact_change")`), and
  - on demand ("Run now" in Settings, or POST /api/scheduler/run).
Each job: scan for sources that expire soon or changed -> queue the weekly digest on the chosen weekday ->
send the waiting alerts (email, Slack, webhook) and retry failed ones. Every run is recorded in `scheduler_runs`."""
import datetime as dt
import threading

from . import audit, clock, notifier, watcher
from .db import jdump

TICK_SECONDS = 30


def _parse(ts):
    try:
        return dt.datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ")
    except (TypeError, ValueError):
        return None


class Scheduler:
    def __init__(self, db, cfg, sync=False):
        self.db, self.cfg, self.sync = db, cfg, sync
        self._job_lock = threading.Lock()
        self._wake = threading.Event()
        self._stop = threading.Event()
        self._pending = None
        self.thread = None

    # ------------------------------------------------------------ control
    def start(self):
        if self.sync or self.thread:
            return self
        self.thread = threading.Thread(target=self._loop, name="cp-scheduler", daemon=True)
        self.thread.start()
        return self

    def stop(self):
        self._stop.set()
        self._wake.set()

    def kick(self, trigger="manual"):
        """Run a job as soon as possible. In sync mode (tests) it runs right here."""
        if self.sync:
            return self.run_job(trigger)
        self._pending = trigger
        self._wake.set()
        return None

    # ------------------------------------------------------------ the job
    def run_job(self, trigger="schedule"):
        with self._job_lock:
            run_id = self.db.insert("scheduler_runs", {"job": "scan", "trigger": trigger, "started_at": clock.now(), "status": "running"})
            try:
                today = clock.today()
                new_alerts = watcher.scan_expiry(self.db, today, self.cfg.get("EXPIRY_WARN_DAYS", 14))
                digests = 0
                if today.weekday() == int(self.cfg.get("DIGEST_WEEKDAY", 0)):
                    digests = notifier.send_weekly_digests(self.db, self.cfg, today)
                res = notifier.process_queue(self.db, self.cfg)
                status = "partial" if res["failed"] else "ok"
                self.db.update("scheduler_runs", run_id, {"finished_at": clock.now(), "status": status, "new_alerts": new_alerts,
                                                          "delivered": res["delivered"], "failed": res["failed"],
                                                          "detail": jdump({"digests_queued": digests, "skipped": res["skipped"]})})
            except Exception as exc:                           # never let the thread die
                self.db.update("scheduler_runs", run_id, {"finished_at": clock.now(), "status": "error",
                                                          "detail": jdump({"error": f"{type(exc).__name__}: {exc}"})})
            audit.log(self.db, "system", "scheduler.run", "system", run_id, {"trigger": trigger})
            return self.db.one("SELECT * FROM scheduler_runs WHERE id=?", (run_id,))

    # ------------------------------------------------------------ the loop
    def due(self):
        last = self.db.one("SELECT started_at FROM scheduler_runs WHERE job='scan' AND trigger IN ('schedule','startup') "
                           "ORDER BY id DESC LIMIT 1")
        if not last:
            return True
        t = _parse(last["started_at"])
        hours = float(self.cfg.get("SCAN_INTERVAL_HOURS", 24))
        return not t or (_parse(clock.now()) - t) >= dt.timedelta(hours=hours)

    def _loop(self):
        first = True
        while not self._stop.is_set():
            try:
                if self._pending:
                    trig, self._pending = self._pending, None
                    self.run_job(trig)
                elif self.due():
                    self.run_job("startup" if first else "schedule")
                elif self.db.one("SELECT id FROM alert_queue WHERE status='pending' LIMIT 1"):
                    notifier.process_queue(self.db, self.cfg)          # retry failed sends quietly
            except Exception:
                pass
            first = False
            self._wake.wait(TICK_SECONDS)
            self._wake.clear()

    def status(self):
        runs = self.db.q("SELECT * FROM scheduler_runs ORDER BY id DESC LIMIT 10")
        pending = self.db.one("SELECT COUNT(*) n FROM alert_queue WHERE status='pending'")["n"]
        last = self.db.one("SELECT started_at FROM scheduler_runs WHERE job='scan' ORDER BY id DESC LIMIT 1")
        return {"enabled": bool(self.thread) or self.sync, "interval_hours": float(self.cfg.get("SCAN_INTERVAL_HOURS", 24)),
                "pending_alerts": pending, "last_run_at": last["started_at"] if last else None, "runs": runs}
