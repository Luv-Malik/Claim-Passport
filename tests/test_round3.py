"""Round 3 features: hybrid checking, accuracy runner, encrypted uploads, PDF page view, corrected export,
logo check, settings, notifier and scheduler."""
import io
import json
import os
import unittest
from pathlib import Path

from tests.helpers import demo_db, login, temp_app
from tests.test_api import SAMPLE, make_docx, make_pptx


def upload(c, hdr, name, data, title=None):
    r = c.post("/api/contents", headers=hdr, data={"file": (io.BytesIO(data), name), "title": title or name},
               content_type="multipart/form-data")
    assert r.status_code == 201, r.get_json()
    return r.get_json()["id"]


class Round3Api(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = temp_app()
        cls.c = cls.app.test_client()
        cls.priya = login(cls.c, "priya@demo.cp")
        cls.admin = login(cls.c, "admin@demo.cp")
        cls.meera = login(cls.c, "anil@demo.cp")      # a manager

    def test_uploads_are_encrypted_on_disk(self):
        cid = upload(self.c, self.priya, "n.docx", make_docx())
        files = [p for p in Path(self.app.cp_cfg["UPLOAD_DIR"]).rglob("*") if p.is_file()]
        self.assertGreater(len(files), 0)
        d = self.c.get(f"/api/contents/{cid}/original", headers=self.priya)
        self.assertEqual(d.status_code, 200)
        self.assertTrue(d.data.startswith(b"PK"))                      # decrypted copy is a real docx
        for p in files:
            self.assertFalse(p.read_bytes().startswith(b"PK"), p)      # nothing stored as a readable docx

    def test_settings_roles_and_secrets(self):
        r = self.c.put("/api/settings", headers=self.priya, json={"hybrid": False})
        self.assertEqual(r.status_code, 403)
        r = self.c.put("/api/settings", headers=self.meera, json={"hybrid": False})
        self.assertEqual(r.status_code, 200)
        self.assertFalse(r.get_json()["hybrid"]["enabled"])
        self.c.put("/api/settings", headers=self.meera, json={"hybrid": True})
        self.assertEqual(self.c.put("/api/settings", headers=self.meera, json={"slack_webhook_url": "https://hooks.slack.com/x"}).status_code, 403)
        r = self.c.put("/api/settings", headers=self.admin, json={"slack_webhook_url": "https://hooks.slack.com/services/T/B/secret"})
        self.assertEqual(r.status_code, 200, r.get_json())
        self.assertTrue(r.get_json()["channels"]["slack"])
        self.assertNotIn("secret", json.dumps(r.get_json()))           # the address is never sent back
        self.assertEqual(self.c.put("/api/settings", headers=self.admin, json={"webhook_url": "file:///etc/passwd"}).status_code, 400)
        self.c.put("/api/settings", headers=self.admin, json={"slack_webhook_url": ""})

    def test_prefs(self):
        r = self.c.put("/api/notification-prefs", headers=self.priya, json={"email_enabled": False, "slack_enabled": False})
        self.assertEqual(r.status_code, 200, r.get_json())
        self.assertFalse(self.c.get("/api/settings", headers=self.priya).get_json()["prefs"]["email_enabled"])

    def test_scheduler_run_and_accuracy_permissions(self):
        self.assertEqual(self.c.post("/api/scheduler/run", headers=self.priya).status_code, 403)
        r = self.c.post("/api/scheduler/run", headers=self.meera)
        self.assertEqual(r.status_code, 200, r.get_json())
        st = self.c.get("/api/scheduler", headers=self.meera).get_json()
        self.assertGreaterEqual(len(st["runs"]), 1)
        self.assertIn("pending_alerts", st)
        self.assertEqual(self.c.post("/api/accuracy/run", headers=self.priya).status_code, 403)

    def test_accuracy_run_saves_and_loads(self):
        r = self.c.post("/api/accuracy/run", headers=self.meera)
        self.assertEqual(r.status_code, 200, r.get_json())
        run = self.c.get("/api/accuracy/latest", headers=self.meera).get_json()["run"]
        self.assertGreaterEqual(run["dataset"]["size"], 150)
        self.assertIn("hybrid", run["modes"])
        self.assertIn("skipped", run["modes"]["hybrid+ai"])            # no AI key in tests

    def test_pdf_page_view(self):
        cid = upload(self.c, self.priya, "product_brief.pdf", (SAMPLE / "product_brief.pdf").read_bytes())
        d = self.c.get(f"/api/contents/{cid}", headers=self.priya).get_json()
        self.assertTrue(d["files"]["original"])
        info = self.c.get(f"/api/contents/{cid}/pages", headers=self.priya)
        if info.status_code != 200 or not info.get_json()["tools"]["poppler"]:
            self.skipTest("poppler not installed")
        self.assertGreaterEqual(info.get_json()["pages"], 1)
        pg = self.c.get(f"/api/contents/{cid}/pages/1", headers=self.priya).get_json()
        self.assertTrue(pg["image"].startswith("data:image/png;base64,"))
        self.assertGreater(len(pg["outlines"]), 0)
        self.assertEqual(self.c.get(f"/api/contents/{cid}/pages/99", headers=self.priya).status_code, 404)

    def test_export_docx_and_pptx(self):
        for name, data in (("n.docx", make_docx()), ("deck.pptx", make_pptx())):
            cid = upload(self.c, self.priya, name, data)
            r = self.c.get(f"/api/contents/{cid}/export", headers=self.priya)
            self.assertEqual(r.status_code, 409, name)                 # nothing changed yet
            d = self.c.get(f"/api/contents/{cid}", headers=self.priya).get_json()
            text = d["text"]
            new = text.replace("15,000+", "10,000+").replace("best", "strong")
            if new == text:
                continue
            r = self.c.post(f"/api/contents/{cid}/versions", headers=self.priya, json={"text": new, "note": "fix"})
            self.assertIn(r.status_code, (200, 201), r.get_json())
            r = self.c.get(f"/api/contents/{cid}/export", headers=self.priya)
            self.assertEqual(r.status_code, 200, name)
            self.assertTrue(r.data.startswith(b"PK"))
            if name == "n.docx":
                from docx import Document
                out = "\n".join(p.text for p in Document(io.BytesIO(r.data)).paragraphs)
                self.assertIn("10,000+", out)
                self.assertNotIn("15,000+", out)
        r = self.c.get(f"/api/contents/{upload(self.c, self.priya, 'a.txt', b'hi there')}/export", headers=self.priya)
        self.assertEqual(r.status_code, 415)

    def test_logo_upload_and_hidden_from_list(self):
        png = (SAMPLE / "banner.png").read_bytes()
        r = self.c.post("/api/vault/logo", headers=self.meera, data={"file": (io.BytesIO(png), "logo.png")}, content_type="multipart/form-data")
        self.assertEqual(r.status_code, 200, r.get_json())
        self.assertEqual(self.c.get("/api/vault/logo", headers=self.priya).data[:4], b"\x89PNG")
        listing = json.dumps(self.c.get("/api/vault/assets", headers=self.priya).get_json())
        self.assertNotIn("png_b64\": \"", listing)
        bad = self.c.post("/api/vault/logo", headers=self.meera, data={"file": (io.BytesIO(b"nope"), "x.png")}, content_type="multipart/form-data")
        self.assertIn(bad.status_code, (400, 422))


if __name__ == "__main__":
    unittest.main()
