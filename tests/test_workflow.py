import unittest

from tests.helpers import demo_db, user

from claimpassport import vault, workflow
from claimpassport.errors import AppError


class Lifecycle(unittest.TestCase):
    def setUp(self):
        self.db = demo_db()
        self.priya, self.rohan = user(self.db, "priya@demo.cp"), user(self.db, "rohan@demo.cp")
        self.meera, self.anil = user(self.db, "meera@demo.cp"), user(self.db, "anil@demo.cp")
        self.admin = user(self.db, "admin@demo.cp")

    def new(self, text, owner=None, fmt="text"):
        return workflow.create_content(self.db, {}, owner or self.priya, "Test", fmt, text, {}, "website")

    def test_full_happy_path_with_human_decisions(self):
        cid = self.new("Guys, we are the best. The Starter plan costs Rs. 599 per month.")
        findings = workflow.findings_for(self.db, cid, 1)
        # the creator accepts the first suggestion on every finding that has a text fix
        for f in findings:
            idx = next((i for i, s in enumerate(f["suggestions"]) if s["kind"] == "replace"), None)
            if idx is not None:
                workflow.decide(self.db, self.priya, f["id"], "accepted", "", idx)
            else:
                workflow.decide(self.db, self.priya, f["id"], "accepted")
        nv, skipped = workflow.apply_decisions(self.db, {}, self.priya, cid)
        self.assertEqual(nv, 2)
        v2 = workflow.current_version(self.db, workflow.get_content(self.db, cid))
        self.assertIn("Rs. 499", v2["text"])
        self.assertNotIn("the best", v2["text"])
        self.assertEqual(workflow.diff(self.db, cid, 1, 2)["changed"], True)
        # the new version has no blocking findings left except ones needing Terms apply etc.
        for f in workflow.findings_for(self.db, cid, 2):
            workflow.decide(self.db, self.priya, f["id"], "accepted")
        workflow.submit(self.db, self.priya, cid)
        with self.assertRaises(AppError):                       # cannot approve own content
            workflow.approve(self.db, self.priya, cid)
        workflow.approve(self.db, self.meera, cid, "ok")
        with self.assertRaises(AppError):                       # a reviewer cannot publish
            workflow.publish(self.db, {}, self.meera, cid)
        workflow.publish(self.db, {}, self.anil, cid)
        self.assertEqual(workflow.get_content(self.db, cid)["status"], "published")
        self.assertTrue(self.db.q("SELECT * FROM passports WHERE content_id=? AND active=1", (cid,)))

    def test_reject_needs_a_reason(self):
        cid = self.new("Welcome!!")
        f = workflow.findings_for(self.db, cid, 1)[0]
        with self.assertRaises(AppError):
            workflow.decide(self.db, self.priya, f["id"], "rejected", "")
        workflow.decide(self.db, self.priya, f["id"], "rejected", "Brand campaign style")

    def test_creator_cannot_override_a_locked_or_high_risk_finding(self):
        cid = self.new("Lumio Invoice is cheaper than BillBee.")
        f = next(x for x in workflow.findings_for(self.db, cid, 1) if x["rule_code"] == "C-5")
        with self.assertRaises(AppError) as cm:
            workflow.decide(self.db, self.priya, f["id"], "rejected", "Legal said fine")
        self.assertEqual(cm.exception.status, 403)
        workflow.submit(self.db, self.priya, cid)
        workflow.decide(self.db, self.meera, f["id"], "rejected", "Legal checked the published comparison")

    def test_approval_is_blocked_while_human_findings_are_open(self):
        cid = self.new("The Starter plan costs Rs. 599 per month. Terms apply.")
        workflow.submit(self.db, self.priya, cid)
        with self.assertRaises(AppError) as cm:
            workflow.approve(self.db, self.meera, cid)
        self.assertEqual(cm.exception.status, 409)
        self.assertTrue(cm.exception.extra["open_findings"])

    def test_locked_content_needs_a_reviewer_not_just_a_manager(self):
        cid = self.new("The Starter plan costs Rs. 599 per month. Terms apply.")
        for f in workflow.findings_for(self.db, cid, 1):
            workflow.decide(self.db, self.priya, f["id"], "accepted")
        workflow.submit(self.db, self.priya, cid)
        with self.assertRaises(AppError) as cm:
            workflow.approve(self.db, self.anil, cid)
        self.assertEqual(cm.exception.status, 403)
        workflow.approve(self.db, self.meera, cid)

    def test_request_changes_and_edit_cycle(self):
        cid = self.new("Hello from Lumio Invoice.")
        workflow.submit(self.db, self.priya, cid)
        with self.assertRaises(AppError):                       # cannot edit while in review
            workflow.add_version(self.db, {}, self.priya, cid, "Changed text")
        workflow.request_changes(self.db, self.meera, cid, "Please add the offer details")
        self.assertEqual(workflow.get_content(self.db, cid)["status"], "changes_requested")
        workflow.add_version(self.db, {}, self.priya, cid, "Hello from Lumio Invoice. New line.")
        self.assertEqual(workflow.get_content(self.db, cid)["status"], "draft")

    def test_creators_cannot_see_other_creators_content(self):
        cid = self.new("Private draft", owner=self.rohan)
        c = workflow.get_content(self.db, cid)
        self.assertFalse(workflow.visible_to(c, self.priya))
        self.assertTrue(workflow.visible_to(c, self.meera))

    def test_decisions_survive_reanalysis(self):
        cid = self.new("Welcome!!")
        f = workflow.findings_for(self.db, cid, 1)[0]
        workflow.decide(self.db, self.priya, f["id"], "rejected", "On purpose")
        workflow.run_analysis(self.db, {}, cid, 1)
        again = workflow.findings_for(self.db, cid, 1)[0]
        self.assertEqual(again["decision"], "rejected")

    def test_overlapping_changes_are_skipped_not_corrupting(self):
        cid = self.new("We are the best.")
        for f in workflow.findings_for(self.db, cid, 1):
            workflow.decide(self.db, self.priya, f["id"], "edited", "", None, "great")
        nv, skipped = workflow.apply_decisions(self.db, {}, self.priya, cid)
        self.assertIn("great", workflow.current_version(self.db, workflow.get_content(self.db, cid))["text"])

    def test_comments(self):
        cid = self.new("Hello")
        workflow.add_comment(self.db, self.meera, cid, "Please check the tone", [0, 5])
        self.assertEqual(workflow.list_comments(self.db, cid)[0]["author"], "Meera Iyer")


class VaultTests(unittest.TestCase):
    def test_version_only_bumps_when_statement_or_value_changes(self):
        db = demo_db()
        admin = user(db, "admin@demo.cp")
        fid = db.one("SELECT id FROM facts WHERE key='customers'")["id"]
        b, a = vault.update_fact(db, fid, {"verified_on": "2026-11-02"}, admin)
        self.assertEqual(a["version"], b["version"])
        self.assertEqual(a["expires_on"], "2027-01-31")          # re-verifying extends expiry by the review interval
        b, a = vault.update_fact(db, fid, {"value": "11,000+", "statement": "Lumio Invoice is used by 11,000+ customers."}, admin)
        self.assertEqual(a["version"], b["version"] + 1)

    def test_guideline_import_keeps_builtin_severity_unless_given(self):
        db = demo_db()
        self.assertEqual(db.one("SELECT severity FROM rules WHERE code='C-1'")["severity"], "high")
        r = vault.parse_guidelines('## Tone\n- [T-9] No slang. avoid: "cool", "dude" use: "great", "friend" severity: low\n')
        self.assertEqual(r[0]["config"]["pairs"], {"cool": ["great"], "dude": ["friend"]})

    def test_empty_import_is_rejected(self):
        with self.assertRaises(AppError):
            vault.import_guidelines(demo_db(), "just text", "x", "1", {"name": "t"})


if __name__ == "__main__":
    unittest.main()
