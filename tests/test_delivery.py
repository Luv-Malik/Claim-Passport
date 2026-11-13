"""Alert delivery (local SMTP and HTTP servers, nothing leaves this machine), scheduler, logo check, judge validation."""
import hashlib
import hmac
import io
import json
import socketserver
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer

from claimpassport import notifier
from claimpassport.scheduler import Scheduler
from tests.helpers import demo_db, user


class Http(BaseHTTPRequestHandler):
    log, status = [], 200

    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0))
        Http.log.append((self.path, {k.lower(): v for k, v in self.headers.items()}, self.rfile.read(n)))
        self.send_response(Http.status)
        self.end_headers()

    def log_message(self, *a):
        pass


class Smtp(socketserver.StreamRequestHandler):
    mails = []

    def handle(self):
        w = lambda s: self.wfile.write((s + "\r\n").encode())
        w("220 test")
        data, buf = False, []
        for raw in self.rfile:
            line = raw.decode().rstrip("\r\n")
            if data:
                if line == ".":
                    data = False
                    Smtp.mails.append("\n".join(buf))
                    buf = []
                    w("250 ok")
                else:
                    buf.append(line)
                continue
            cmd = line.upper()
            if cmd.startswith("DATA"):
                data = True
                w("354 go")
            elif cmd.startswith("QUIT"):
                w("221 bye")
                return
            else:
                w("250 ok")


def serve(server):
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    return server


class DeliveryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.http = serve(HTTPServer(("127.0.0.1", 0), Http))
        cls.smtp = serve(socketserver.ThreadingTCPServer(("127.0.0.1", 0), Smtp))
        cls.base = f"http://127.0.0.1:{cls.http.server_address[1]}"

    @classmethod
    def tearDownClass(cls):
        cls.http.shutdown()
        cls.smtp.shutdown()

    def setUp(self):
        Http.log, Http.status, Smtp.mails = [], 200, []
        self.db = demo_db()
        self.cfg = {"SMTP_HOST": "127.0.0.1", "SMTP_PORT": self.smtp.server_address[1], "SMTP_TLS": "none", "SMTP_FROM": "cp@test",
                    "SLACK_WEBHOOK_URL": self.base + "/slack", "WEBHOOK_URL": self.base + "/hook", "WEBHOOK_SECRET": "s3cret",
                    "ENCRYPTION_KEY": "k" * 32, "PUBLIC_URL": "https://cp.example", "EXPIRY_WARN_DAYS": 14, "DIGEST_WEEKDAY": 0}
        self.priya, self.anil = user(self.db, "priya@demo.cp"), user(self.db, "anil@demo.cp")
        notifier.set_prefs(self.db, self.anil["id"], {"webhook_enabled": True})
        notifier.set_prefs(self.db, self.priya["id"], {"webhook_enabled": True})

    def test_email_slack_signed_webhook_and_org_dedupe(self):
        for u in (self.priya, self.anil):
            notifier.enqueue(self.db, u["id"], "Fact F-1 expires soon", "#/vault", ref="fact-1")
        res = notifier.process_queue(self.db, self.cfg)
        self.assertEqual(len(Smtp.mails), 2)                                    # one email each
        self.assertIn("expires soon", Smtp.mails[0])
        slack = [x for x in Http.log if x[0] == "/slack"]
        hook = [x for x in Http.log if x[0] == "/hook"]
        self.assertEqual((len(slack), len(hook)), (1, 1))                       # org-level: once, not per person
        self.assertGreaterEqual(res["skipped"], 2)
        path, headers, body = hook[0]
        want = "sha256=" + hmac.new(b"s3cret", body, hashlib.sha256).hexdigest()
        self.assertEqual(headers["x-cp-signature"], want)
        self.assertEqual(json.loads(body)["ref"], "fact-1")
        self.assertEqual(notifier.process_queue(self.db, self.cfg), {"delivered": 0, "failed": 0, "skipped": 0})   # nothing resent

    def test_failure_is_retried_then_given_up(self):
        Http.status = 500
        cfg = {**self.cfg, "SMTP_HOST": ""}
        notifier.enqueue(self.db, self.priya["id"], "Source changed", ref="x-1")
        for _ in range(3):
            notifier.process_queue(self.db, cfg)
        row = self.db.one("SELECT * FROM alert_queue WHERE ref='x-1'")
        self.assertEqual((row["status"], row["attempts"]), ("failed", 3))
        n = len(Http.log)
        notifier.process_queue(self.db, cfg)
        self.assertEqual(len(Http.log), n)                                      # gave up: no 4th try
        errs = self.db.q("SELECT error FROM alert_deliveries WHERE status='failed'")
        self.assertTrue(errs and "500" in errs[0]["error"])

    def test_channel_off_means_not_sent(self):
        notifier.set_prefs(self.db, self.priya["id"], {"email_enabled": False, "slack_enabled": False, "webhook_enabled": False})
        notifier.enqueue(self.db, self.priya["id"], "Quiet", ref="q-1")
        notifier.process_queue(self.db, self.cfg)
        self.assertEqual((len(Smtp.mails), len(Http.log)), (0, 0))
        self.assertEqual(self.db.one("SELECT status FROM alert_queue WHERE ref='q-1'")["status"], "no_channel")

    def test_secrets_not_leaked_by_status(self):
        st = notifier.channel_status(self.db, self.cfg)
        self.assertEqual(st, {"email": True, "slack": True, "webhook": True})

    def test_bad_url_rejected(self):
        with self.assertRaises(Exception):
            notifier.check_url("ftp://x")

    def test_scheduler_run_records_and_delivers(self):
        notifier.enqueue(self.db, self.priya["id"], "Hello", ref="s-1")
        run = Scheduler(self.db, self.cfg, sync=True).run_job("test")
        self.assertIn(run["status"], ("ok", "partial"))
        self.assertGreaterEqual(run["delivered"], 1)
        self.assertGreaterEqual(len(Smtp.mails), 1)

    def test_scheduler_survives_errors(self):
        bad = Scheduler(self.db, {**self.cfg, "SMTP_HOST": ""}, sync=True)
        Http.status = 500
        notifier.enqueue(self.db, self.priya["id"], "Hello", ref="s-2")
        self.assertIn(bad.run_job("test")["status"], ("partial", "ok"))


class LogoTests(unittest.TestCase):
    def _png(self, im):
        b = io.BytesIO()
        im.save(b, "PNG")
        return b.getvalue()

    def _logo(self):
        from PIL import Image, ImageDraw
        im = Image.new("RGBA", (120, 120), (255, 255, 255, 0))
        d = ImageDraw.Draw(im)
        d.ellipse((5, 5, 115, 115), fill=(199, 91, 11, 255))
        d.polygon([(30, 90), (60, 20), (90, 90)], fill=(18, 124, 122, 255))
        d.rectangle((50, 55, 70, 75), fill=(255, 255, 255, 255))
        return im

    def test_found_missing_and_edge(self):
        try:
            import cv2  # noqa: F401
        except ImportError:
            self.skipTest("OpenCV not installed")
        from PIL import Image
        from claimpassport import logo
        logo_im = self._logo()
        asset = logo.make_asset(self._png(logo_im), "l.png")
        lp = logo.logo_bytes(asset)

        def canvas(pos, size):
            bg = Image.new("RGB", (900, 600), (240, 240, 235))
            small = logo_im.resize((size, size))
            bg.paste(small, pos, small)
            return self._png(bg)
        r = logo.check(canvas((400, 250), 90), lp)
        self.assertEqual(r["status"], "found", r)
        r = logo.check(self._png(Image.new("RGB", (900, 600), (240, 240, 235))), lp)
        self.assertEqual(r["status"], "missing", r)
        r = logo.check(canvas((300, 200), 30), lp)
        self.assertEqual(r["status"], "found", r)                              # scale changed, still found


class JudgeTests(unittest.TestCase):
    def test_uncited_answer_is_not_trusted(self):
        from claimpassport.engine import judge
        cands = [{"id": 1, "statement": "Lumio has 10,000+ customers."}]
        good = judge.validate({"verdict": "supports", "fact_id": 1, "quote": "10,000+ customers"}, cands)
        bad_id = judge.validate({"verdict": "supports", "fact_id": 99, "quote": "10,000+ customers"}, cands)
        bad_quote = judge.validate({"verdict": "supports", "fact_id": 1, "quote": "invented words"}, cands)
        self.assertTrue(good["cited"])
        self.assertFalse(bad_id["cited"])
        self.assertFalse(bad_quote["cited"])
        self.assertIsNone(judge.validate({"verdict": "nonsense"}, cands))
        self.assertIsNone(judge.validate("text", cands))


if __name__ == "__main__":
    unittest.main()
