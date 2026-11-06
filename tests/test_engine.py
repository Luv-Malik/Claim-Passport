import unittest

from tests.helpers import demo_db

from claimpassport.engine import claims, pipeline
from claimpassport.engine.checkers import contrast_ratio
from claimpassport.engine.text_utils import mask_html, sentences
from claimpassport.security import mask_pii


class ClaimExtraction(unittest.TestCase):
    def test_sentences_keep_rs_and_offsets(self):
        t = "Plans start at Rs. 499 per month. It is simple!"
        s = sentences(t)
        self.assertEqual(len(s), 2)
        self.assertEqual(t[s[0][0]:s[0][1]], "Plans start at Rs. 499 per month.")

    def test_numbers_dates_and_standards_are_not_claims(self):
        c = claims.extract_claims("We were founded in 2019. Offer ends 31 Dec 2026. ISO 27001 certified. See v2.1.")
        nums = [n["raw"] for cl in c for n in cl["numbers"]]
        self.assertEqual(nums, [])

    def test_money_percent_and_plus(self):
        c = claims.extract_claims("Plans cost Rs. 1,299 per month. Used by 10,000+ customers with 99.9% uptime.")
        raws = [n["raw"] for cl in c for n in cl["numbers"]]
        self.assertIn("Rs. 1,299", raws)
        self.assertIn("10,000+", raws)
        self.assertIn("99.9%", raws)

    def test_triggers(self):
        c = claims.extract_claims("The best app. It is 100% secure and 24x7. Cheaper than BillBee.")
        types = {t["type"] for cl in c for t in cl["triggers"]}
        self.assertTrue({"superlative", "absolute", "comparison"} <= types)


class Verification(unittest.TestCase):
    def setUp(self):
        self.db = demo_db()

    def analyze(self, text, fmt="text"):
        return pipeline.analyze(self.db, text, fmt)

    def codes(self, r):
        return [f["rule_code"] for f in r["findings"]]

    def test_matching_fact_is_not_flagged(self):
        r = self.analyze("The Starter plan costs Rs. 499 per month. Terms apply.")
        self.assertNotIn("C-2", self.codes(r))
        self.assertEqual(r["summary"]["claims_clean"], 1)

    def test_wrong_number_is_flagged_with_fix_that_keeps_sentence(self):
        r = self.analyze("The Starter plan costs Rs. 599 per month. Terms apply.")
        f = next(x for x in r["findings"] if x["rule_code"] == "C-2")
        self.assertEqual(f["excerpt"], "Rs. 599")
        self.assertEqual(f["suggestions"][0]["replacement"], "Rs. 499")
        self.assertIn("Pricing sheet v7", f["source_ref"])
        self.assertEqual(f["human_lock"], 1)          # pricing facts always need a person

    def test_unit_is_not_duplicated_in_fix(self):
        r = self.analyze("Every account gets a 30-day free trial.")
        f = next(x for x in r["findings"] if x["rule_code"] == "C-2")
        self.assertEqual(f["suggestions"][0]["replacement"], "14")

    def test_softened_understatement_is_ok(self):
        r = self.analyze("Used by over 5,000 customers.")
        self.assertNotIn("C-2", self.codes(r))

    def test_unsupported_superlative_and_absolute(self):
        r = self.analyze("We are the best and 100% secure.")
        c1 = [f for f in r["findings"] if f["rule_code"] == "C-1"]
        self.assertEqual(len(c1), 2)
        self.assertEqual(c1[0]["suggestions"][0]["replacement"], "a reliable")

    def test_unsupported_certificate_is_locked(self):
        r = self.analyze("We are SOC 2 compliant and ISO 27001 certified.")
        locked = [f for f in r["findings"] if f["rule_code"] == "C-1" and f["human_lock"]]
        self.assertTrue(any(f["excerpt"].lower().startswith("soc") for f in locked))
        self.assertFalse(any("ISO" in f["excerpt"] for f in r["findings"] if f["rule_code"] == "C-1"))

    def test_comparison_needs_legal(self):
        r = self.analyze("Lumio Invoice is cheaper than BillBee.")
        f = next(x for x in r["findings"] if x["rule_code"] == "C-5")
        self.assertEqual(f["human_lock"], 1)

    def test_number_without_source_is_low_confidence_and_needs_human(self):
        r = self.analyze("Our team has handled 4,500 support chats.")
        f = next(x for x in r["findings"] if x["rule_code"] == "C-4")
        self.assertEqual(f["confidence"], "low")
        self.assertEqual(f["needs_human"], 1)

    def test_confidential_fact_is_not_leaked_in_message(self):
        r = self.analyze("Customer data is stored in 3 data centres in Pune.")
        text = " ".join(f["message"] + str(f["suggestions"]) for f in r["findings"])
        self.assertNotIn("Mumbai", text)

    def test_expired_fact_gives_stale_warning(self):
        self.db.run("UPDATE facts SET expires_on='2026-10-01' WHERE key='free_trial'")
        r = self.analyze("Every new account gets a 14-day free trial.")
        self.assertIn("C-3", self.codes(r))


class Checkers(unittest.TestCase):
    def setUp(self):
        self.db = demo_db()

    def codes(self, text, fmt="text", meta=None):
        return [f["rule_code"] for f in pipeline.analyze(self.db, text, fmt, meta)["findings"]]

    def test_tone_and_terms(self):
        c = self.codes("Guys!!! LumioInvoice is AMAZING and awesome.")
        for code in ("A-5", "T-2", "TERM-1", "T-3", "T-1"):
            self.assertIn(code, c)

    def test_correct_product_name_is_not_flagged(self):
        self.assertNotIn("TERM-1", self.codes("Lumio Invoice is simple to use."))

    def test_one_exclamation_is_allowed(self):
        self.assertNotIn("T-2", self.codes("Welcome to Lumio Invoice!"))

    def test_long_sentence_gets_split_option(self):
        long = ("Lumio Invoice helps small teams send invoices quickly and it also reminds customers about due dates "
                "so that nobody has to chase payments by hand every single week of the month.")
        r = pipeline.analyze(self.db, long, "text")
        f = next(x for x in r["findings"] if x["rule_code"] == "A-1")
        self.assertEqual(f["suggestions"][0]["label"], "Split into two sentences")
        self.assertIn(". ", f["suggestions"][0]["replacement"])

    def test_requires_terms_apply(self):
        c = self.codes("Plans start at Rs. 499 per month.")
        self.assertIn("M-1", c)
        self.assertNotIn("M-1", self.codes("Plans start at Rs. 499 per month. Terms apply."))

    def test_html_visual_and_accessibility(self):
        html = ('<style>.a{font-family:"Comic Sans MS",cursive;color:#cccccc;background:#ffffff}.b{background:#ff00aa}</style>'
                '<img src="x.png"><a href="/d">click here</a>')
        c = self.codes(html, "html")
        for code in ("V-2", "A-4", "V-1", "A-2", "A-3"):
            self.assertIn(code, c)

    def test_contrast_math(self):
        self.assertEqual(contrast_ratio("#000000", "#ffffff"), 21.0)
        self.assertLess(contrast_ratio("#cccccc", "#ffffff"), 4.5)

    def test_html_tags_do_not_create_text_findings(self):
        self.assertEqual(len(mask_html('<p class="BEST">Hi</p>')), len('<p class="BEST">Hi</p>'))
        self.assertNotIn("T-3", self.codes('<p class="BEST">Hello there</p>', "html"))

    def test_image_checks(self):
        meta = {"width": 640, "height": 300, "colors": [{"hex": "#E91E8C", "share": 0.9}], "alt_text": ""}
        c = self.codes("", "image", meta)
        self.assertIn("V-3", c)
        self.assertIn("A-2", c)

    def test_findings_are_sorted_and_have_required_fields(self):
        r = pipeline.analyze(self.db, "Guys!!! The best app, 12,000+ customers.", "text")
        starts = [f["span_start"] for f in r["findings"]]
        self.assertEqual(starts, sorted(starts))
        for f in r["findings"]:
            for k in ("message", "source_ref", "confidence", "suggestions", "severity"):
                self.assertTrue(f[k] not in (None, ""), k)


class LLMIntegration(unittest.TestCase):
    class Fake:
        available = True
        model = "fake-model"

        def __init__(self):
            self.calls = []

        def rewrite(self, sentence, issue, statement):
            self.calls.append((sentence, issue, statement))
            return ["Lumio Invoice is trusted by 10,000+ customers."], 0

    def test_llm_suggestions_are_added_and_logged_and_never_see_confidential_statement(self):
        db = demo_db()
        fake = self.Fake()
        r = pipeline.analyze(db, "Lumio Invoice is used by 12,000+ customers.", "text", llm=fake)
        f = next(x for x in r["findings"] if x["rule_code"] == "C-2")
        self.assertEqual(f["suggestions"][-1]["label"], "AI rewrite (please check)")
        self.assertEqual(f["produced_by"], "rules+llm")
        self.assertTrue(any(e["engine"] == "anthropic" for e in r["ai_events"]))
        fake2 = self.Fake()
        pipeline.analyze(db, "Customer data is stored in 3 data centres.", "text", llm=fake2)
        for _, _, st in fake2.calls:
            self.assertIsNone(st)

    def test_no_llm_means_nothing_leaves(self):
        r = pipeline.analyze(demo_db(), "The best app.", "text")
        self.assertEqual([e["engine"] for e in r["ai_events"]], ["rules-engine"])


class Privacy(unittest.TestCase):
    def test_masking(self):
        t, n = mask_pii("Call 9876543210 or mail a.b@x.com, PAN ABCDE1234F, card 4111 1111 1111 1111")
        self.assertEqual(n, 4)
        self.assertNotIn("9876543210", t)
        self.assertNotIn("4111", t)


if __name__ == "__main__":
    unittest.main()
