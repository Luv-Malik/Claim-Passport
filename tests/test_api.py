import io
import unittest
import zipfile
from pathlib import Path

from tests.helpers import login, temp_app

SAMPLE = Path(__file__).resolve().parent.parent / "data" / "sample" / "content"


def make_pptx():
    slide = ('<p:sld xmlns:a="a" xmlns:p="p"><a:t>We are the best</a:t><p:pic><p:nvPicPr>'
             '<p:cNvPr id="4" name="Logo"/></p:nvPicPr></p:pic></p:sld>')
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("ppt/slides/slide1.xml", slide)
    return buf.getvalue()


def make_docx():
    from docx import Document
    d = Document()
    d.add_paragraph("Lumio Invoice is used by 15,000+ customers.")
    buf = io.BytesIO()
    d.save(buf)
    return buf.getvalue()


class ApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = temp_app()
        cls.c = cls.app.test_client()
        cls.priya = login(cls.c, "priya@demo.cp")
        cls.rohan = login(cls.c, "rohan@demo.cp")
        cls.meera = login(cls.c, "meera@demo.cp")
        cls.anil = login(cls.c, "anil@demo.cp")
        cls.admin = login(cls.c, "admin@demo.cp")

    def test_login_failures_and_token_required(self):
        self.assertEqual(self.c.post("/api/login", json={"email": "priya@demo.cp", "password": "nope"}).status_code, 401)
        self.assertEqual(self.c.get("/api/contents").status_code, 401)
        self.assertEqual(self.c.get("/api/contents", headers={"Authorization": "Bearer junk"}).status_code, 401)

    def test_security_headers_and_json_404(self):
        r = self.c.get("/api/health")
        self.assertEqual(r.headers["X-Content-Type-Options"], "nosniff")
        self.assertIn("default-src 'self'", r.headers["Content-Security-Policy"])
        self.assertEqual(self.c.get("/api/nope").status_code, 404)

    def test_public_feed_needs_no_login_and_hides_confidential(self):
        r = self.c.get("/.well-known/claims.json")
        self.assertEqual(r.status_code, 200)
        keys = {f["key"] for f in r.get_json()["facts"]}
        self.assertNotIn("data_centres", keys)

    def test_creator_sees_only_own_content(self):
        mine = self.c.get("/api/contents", headers=self.priya).get_json()["contents"]
        self.assertTrue(mine)
        self.assertTrue(all(c["owner_name"] == "Priya Sharma" for c in mine))
        other = next(c for c in self.c.get("/api/contents", headers=self.admin).get_json()["contents"] if c["owner_name"] == "Rohan Mehta")
        self.assertEqual(self.c.get(f"/api/contents/{other['id']}", headers=self.priya).status_code, 404)

    def test_roles_are_enforced(self):
        self.assertEqual(self.c.get("/api/audit", headers=self.priya).status_code, 403)
        self.assertEqual(self.c.get("/api/audit", headers=self.anil).status_code, 200)
        self.assertEqual(self.c.post("/api/vault/facts", headers=self.priya, json={"key": "x", "statement": "y"}).status_code, 403)
        self.assertEqual(self.c.get("/api/insights/guideline-gaps", headers=self.priya).status_code, 403)
        self.assertEqual(self.c.get("/api/insights/guideline-gaps", headers=self.meera).status_code, 200)

    def test_confidential_fact_is_masked_for_creators_only(self):
        mine = {f["key"]: f for f in self.c.get("/api/vault/facts", headers=self.priya).get_json()["facts"]}
        full = {f["key"]: f for f in self.c.get("/api/vault/facts", headers=self.admin).get_json()["facts"]}
        self.assertEqual(mine["data_centres"]["statement"], "(confidential fact)")
        self.assertIn("Mumbai", full["data_centres"]["statement"])

    def test_paste_review_decide_apply_flow(self):
        r = self.c.post("/api/contents", headers=self.priya, json={"title": "API test", "text": "Plans start at Rs. 599 per month!!"})
        self.assertEqual(r.status_code, 201)
        cid = r.get_json()["id"]
        d = self.c.get(f"/api/contents/{cid}", headers=self.priya).get_json()
        f = next(x for x in d["findings"] if x["rule_code"] == "C-2")
        self.assertTrue(f["message"] and f["source_ref"] and f["suggestions"])
        res = self.c.post(f"/api/findings/{f['id']}/decision", headers=self.priya, json={"decision": "accepted", "suggestion_index": 0})
        self.assertEqual(res.get_json()["finding"]["decision"], "accepted")
        bad = self.c.post(f"/api/findings/{f['id']}/decision", headers=self.priya, json={"decision": "rejected"})
        self.assertEqual(bad.status_code, 400)
        ap = self.c.post(f"/api/contents/{cid}/apply", headers=self.priya)
        self.assertEqual(ap.get_json()["version"], 2)
        diff = self.c.get(f"/api/contents/{cid}/diff", headers=self.priya).get_json()
        self.assertTrue(diff["changed"])
        self.assertIn("Rs. 499", self.c.get(f"/api/contents/{cid}/text", headers=self.priya).get_data(as_text=True))
        t = self.c.get(f"/api/contents/{cid}/transparency", headers=self.priya).get_json()
        self.assertEqual(t["events"][0]["engine"], "rules-engine")

    def test_uploads_for_each_format(self):
        cases = [("a.txt", b"We are the best.", "text/plain"), ("a.md", b"# Hi\nGuys!!!", "text/markdown"),
                 ("a.html", b"<img src=x.png><p>Hello</p>", "text/html"),
                 ("deck.pptx", make_pptx(), "application/octet-stream"), ("n.docx", make_docx(), "application/octet-stream"),
                 ("product_brief.pdf", (SAMPLE / "product_brief.pdf").read_bytes(), "application/pdf"),
                 ("banner.png", (SAMPLE / "banner.png").read_bytes(), "image/png")]
        for name, data, mime in cases:
            r = self.c.post("/api/contents", headers=self.priya, data={"file": (io.BytesIO(data), name), "title": name},
                            content_type="multipart/form-data")
            self.assertEqual(r.status_code, 201, name + str(r.get_json()))
            d = self.c.get(f"/api/contents/{r.get_json()['id']}", headers=self.priya).get_json()
            self.assertGreater(len(d["findings"]), 0, name)
            if name == "deck.pptx":
                self.assertIn("A-2", [f["rule_code"] for f in d["findings"]])
            if name == "product_brief.pdf":
                self.assertIn("C-2", [f["rule_code"] for f in d["findings"]])      # 15,000+ vs 10,000+
            if name == "banner.png":
                self.assertEqual(d["content"]["editable"], False)
                self.assertIn("V-3", [f["rule_code"] for f in d["findings"]])

    def test_unsupported_and_oversized_uploads(self):
        r = self.c.post("/api/contents", headers=self.priya, data={"file": (io.BytesIO(b"x"), "a.exe")}, content_type="multipart/form-data")
        self.assertEqual(r.status_code, 415)
        r = self.c.post("/api/contents", headers=self.priya, json={"title": "", "text": "x"})
        self.assertEqual(r.status_code, 400)

    def test_vault_fact_update_creates_proposals_via_api(self):
        facts = {f["key"]: f for f in self.c.get("/api/vault/facts", headers=self.admin).get_json()["facts"]}
        r = self.c.put(f"/api/vault/facts/{facts['price_pro']['id']}", headers=self.admin,
                       json={"statement": "The Pro plan costs Rs. 1,399 per month.", "value": "Rs. 1,399"})
        self.assertTrue(r.get_json()["version_changed"])
        deb = self.c.get("/api/insights/overview", headers=self.admin).get_json()["truth_debt"]
        self.assertGreaterEqual(deb["counts"]["source_changed"], 1)

    def test_guideline_import_and_new_rule_is_used(self):
        md = '## Tone\n- [T-9] No filler words. avoid: "basically" use: "in short" severity: low\n'
        r = self.c.post("/api/vault/guidelines/import", headers=self.admin, json={"markdown": md, "title": "Extra", "version": "1"})
        self.assertEqual(r.get_json()["created"], 1)
        cid = self.c.post("/api/contents", headers=self.priya, json={"title": "t9", "text": "Basically it works."}).get_json()["id"]
        codes = [f["rule_code"] for f in self.c.get(f"/api/contents/{cid}", headers=self.priya).get_json()["findings"]]
        self.assertIn("T-9", codes)

    def test_proof_endpoint(self):
        cid = next(c["id"] for c in self.c.get("/api/contents?status=published", headers=self.admin).get_json()["contents"])
        r = self.c.get(f"/api/proof?content_id={cid}&at=2026-11-02", headers=self.admin).get_json()
        self.assertTrue(r["found"])


if __name__ == "__main__":
    unittest.main()
