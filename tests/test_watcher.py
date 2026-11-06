import unittest

from tests.helpers import demo_db, user

from claimpassport import insights, passports, vault, watcher, workflow
from claimpassport.errors import AppError


class SourceChange(unittest.TestCase):
    def setUp(self):
        self.db = demo_db()
        self.admin = user(self.db, "admin@demo.cp")

    def test_demo_has_a_stale_page_and_a_ready_fix(self):
        debt = passports.truth_debt(self.db)
        self.assertEqual(debt["counts"]["source_changed"], 1)
        self.assertGreater(debt["score"], 0)
        p = watcher.list_proposals(self.db)[0]
        self.assertIn("Rs. 499", p["new_text"])
        self.assertIn("Rs. 449", p["old_text"])

    def test_changing_a_fact_flags_every_page_that_uses_it(self):
        fid = self.db.one("SELECT id FROM facts WHERE key='price_starter'")["id"]
        before, after = vault.update_fact(self.db, fid, {"statement": "The Starter plan costs Rs. 549 per month.", "value": "Rs. 549"}, self.admin)
        created = watcher.on_fact_changed(self.db, before, after, self.admin)
        self.assertGreaterEqual(len(created), 1)      # the newsletter now says Rs. 499 -> stale
        statuses = {p["content_title"]: p["status"] for p in passports.list_passports(self.db) if p["fact_key"] == "price_starter"}
        self.assertEqual(set(statuses.values()), {"source_changed"})
        self.assertTrue(self.db.q("SELECT * FROM notifications WHERE message LIKE '%outdated%'"))
        self.assertEqual(self.db.one("SELECT needs_refresh FROM contents WHERE title='November newsletter'")["needs_refresh"], 1)

    def test_apply_proposal_makes_a_draft_version_and_needs_review_again(self):
        p = watcher.list_proposals(self.db)[0]
        rohan = user(self.db, "rohan@demo.cp")
        nv = watcher.apply_proposal(self.db, {}, rohan, p["id"])
        c = workflow.get_content(self.db, p["content_id"])
        self.assertEqual((c["current_version"], c["status"]), (nv, "draft"))
        self.assertIn("Rs. 499", workflow.current_version(self.db, c)["text"])
        with self.assertRaises(AppError):                       # cannot apply twice
            watcher.apply_proposal(self.db, {}, rohan, p["id"])

    def test_another_creator_cannot_apply_someone_elses_proposal(self):
        p = watcher.list_proposals(self.db)[0]
        with self.assertRaises(AppError):
            watcher.apply_proposal(self.db, {}, user(self.db, "kabir@demo.cp"), p["id"])

    def test_republishing_replaces_old_passports(self):
        p = watcher.list_proposals(self.db)[0]
        rohan, meera, anil = (user(self.db, e) for e in ("rohan@demo.cp", "meera@demo.cp", "anil@demo.cp"))
        watcher.apply_proposal(self.db, {}, rohan, p["id"])
        cid = p["content_id"]
        for f in workflow.findings_for(self.db, cid, 2):
            workflow.decide(self.db, rohan, f["id"], "accepted")
        workflow.submit(self.db, rohan, cid)
        workflow.approve(self.db, meera, cid)
        workflow.publish(self.db, {}, anil, cid)
        self.assertEqual(passports.truth_debt(self.db)["counts"]["source_changed"], 0)
        self.assertEqual(len(self.db.q("SELECT * FROM publications WHERE content_id=?", (cid,))), 2)

    def test_expiry_scan_notifies_once(self):
        first = watcher.scan_expiry(self.db)
        again = watcher.scan_expiry(self.db)
        self.assertGreaterEqual(first, 1)
        self.assertEqual(again, 0)

    def test_expired_fact_turns_passport_red(self):
        self.db.run("UPDATE facts SET expires_on='2026-10-30' WHERE key='uptime'")
        st = [p["status"] for p in passports.list_passports(self.db) if p["fact_key"] == "uptime"]
        self.assertEqual(set(st), {"expired"})


class FeedAndProof(unittest.TestCase):
    def setUp(self):
        self.db = demo_db()

    def test_truth_feed_hides_confidential_and_expired_facts(self):
        keys = {f["key"] for f in passports.truth_feed(self.db)["facts"]}
        self.assertNotIn("data_centres", keys)
        self.assertIn("iso_27001", keys)
        self.db.run("UPDATE facts SET expires_on='2026-10-01' WHERE key='iso_27001'")
        self.assertNotIn("iso_27001", {f["key"] for f in passports.truth_feed(self.db)["facts"]})

    def test_proof_time_machine(self):
        cid = self.db.one("SELECT id FROM contents WHERE title='Pricing page'")["id"]
        res = passports.proof_at(self.db, cid, "2026-11-02")
        self.assertTrue(res["found"])
        self.assertTrue(any("449" in c["claim"] for c in res["claims"]))
        self.assertFalse(passports.proof_at(self.db, cid, "2020-01-01")["found"])
        self.assertIsNone(passports.proof_at(self.db, cid, "not-a-date"))

    def test_timeline_shows_publication_and_source_change(self):
        cid = self.db.one("SELECT id FROM contents WHERE title='Pricing page'")["id"]
        types = [e["type"] for e in passports.timeline(self.db, cid)]
        self.assertIn("published", types)
        self.assertIn("source_changed", types)

    def test_half_life_sorted_by_urgency(self):
        items = passports.half_life(self.db)
        self.assertEqual(items[0]["key"], "customers")             # expires in 6 days in the demo data
        self.assertEqual([i["days_left"] for i in items], sorted(i["days_left"] for i in items))
        self.assertNotIn("Mumbai", str(items))


class InsightTests(unittest.TestCase):
    def setUp(self):
        self.db = demo_db()

    def test_unclear_rule_is_detected_with_evidence(self):
        gaps = {g["rule_code"]: g for g in insights.guideline_gaps(self.db)}
        self.assertIn("T-2", gaps)
        self.assertTrue(gaps["T-2"]["evidence"]["sample_reasons"])
        self.assertIn("examples", gaps["T-2"]["suggestion"])

    def test_overview_has_open_findings_by_severity(self):
        o = insights.overview(self.db, user(self.db, "admin@demo.cp"))
        self.assertEqual(sum(o["open_by_severity"].values()), o["open_findings"])

    def test_mistakes_by_team(self):
        m = insights.mistakes(self.db)
        self.assertTrue(m["top_rules"])
        self.assertIn("Social Media", {t["team"] for t in m["teams"]})

    def test_overview_for_creator_is_limited_to_own_content(self):
        rohan = user(self.db, "rohan@demo.cp")
        own = insights.overview(self.db, rohan)
        admin = insights.overview(self.db, user(self.db, "admin@demo.cp"))
        self.assertLess(sum(own["content_status"].values()), sum(admin["content_status"].values()))


if __name__ == "__main__":
    unittest.main()
