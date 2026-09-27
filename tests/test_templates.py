"""
Unit tests for src/templates.py — the keyword-matching catalog over
src/build_library.py's 14 confirmed report shapes that src/compiler.py's
compile_request() uses to decide *which* fixed report a free-text request
wants (see src/templates.py's own docstring for why this is a thin
selection layer, not a second copy of the query logic).

These tests exist to catch exactly the kind of thing found by hand while
building this file: two templates' keyword lists overlapping on a phrase
(e.g. "purchase invoice" being a substring of both a supplier-spend request
and an overdue-invoice request), which would otherwise surface as a silent
"ambiguous" result a customer sees for a perfectly ordinary phrasing.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import templates


class TestCatalogShape(unittest.TestCase):
    def test_all_14_templates_registered(self):
        self.assertEqual(len(templates.TEMPLATES), 14)

    def test_keys_are_unique(self):
        keys = [t.key for t in templates.TEMPLATES]
        self.assertEqual(len(keys), len(set(keys)))

    def test_by_key_covers_every_template(self):
        self.assertEqual(set(templates.BY_KEY), {t.key for t in templates.TEMPLATES})

    def test_every_template_has_at_least_one_keyword(self):
        for t in templates.TEMPLATES:
            self.assertTrue(t.keywords, f"{t.key} has no keyword phrases")

    def test_every_build_fn_is_callable_and_returns_a_spec_dict(self):
        # Note: t.module (this file's own module tag, matching CLAUDE.md's
        # generated/<module>/ folder names) intentionally does NOT need to
        # equal spec["group"] (iplicit's own enquiry Group field, which uses
        # its own legacy names like "Sale"/"Purchase"/"DocBase" — see
        # src/build_library.py) — the two are different vocabularies for
        # different purposes.
        for t in templates.TEMPLATES:
            spec = t.build_fn()
            self.assertIn("filename", spec)
            self.assertIn("group", spec)
            self.assertTrue(spec["group"])


class TestNoKeywordCollisionsBetweenTemplates(unittest.TestCase):
    """Each keyword phrase, tried alone, should identify exactly its own
    template as the (sole) top match — once a template's anti_keywords are
    applied. A regression here means a newly-added phrase silently turned
    an unambiguous request into an "ambiguous, please clarify" one."""

    def test_each_keyword_in_isolation_matches_only_its_own_template(self):
        for tpl in templates.TEMPLATES:
            for kw in tpl.keywords:
                matches = templates.match(kw)
                self.assertTrue(matches, f"keyword {kw!r} (from {tpl.key}) matched nothing")
                top_score = matches[0][1]
                top_keys = sorted(t.key for t, s in matches if s == top_score)
                self.assertEqual(top_keys, [tpl.key],
                                  f"keyword {kw!r} (from {tpl.key}) also top-matches {top_keys}")


class TestRepresentativePhrasingsMatchExpectedTemplate(unittest.TestCase):
    CASES = [
        ("Show me the trial balance", "gl_trial_balance"),
        ("I need GL detail by nominal for this month", "gl_detail_by_nominal"),
        ("balance sheet by department", "gl_balance_sheet_by_department"),
        ("profit and loss by month please", "gl_pl_by_month"),
        ("aged debtors report, who owes us", "ar_aged_debtors"),
        ("top customers by revenue", "sales_top_customers"),
        ("aged creditors by supplier, who do we owe", "ap_aged_creditors"),
        ("purchase invoices by supplier by month", "purchasing_by_supplier_month"),
        ("overdue purchase invoices", "ap_overdue_invoices"),
        ("show me all unpaid supplier invoices", "ap_overdue_invoices"),
        ("bank transactions by account", "bank_transactions"),
        ("manual journals posted last week", "gl_manual_journals"),
        ("documents created by user", "gl_documents_by_user"),
        ("budget vs actual by cost centre", "budgets_vs_actual"),
        ("credit notes issued this quarter", "sales_credit_notes"),
    ]

    def test_representative_phrasings(self):
        for text, expected_key in self.CASES:
            with self.subTest(text=text):
                matches = templates.match(text)
                self.assertTrue(matches, f"{text!r} matched nothing")
                top_score = matches[0][1]
                tied = [t.key for t, s in matches if s == top_score]
                self.assertEqual(tied, [expected_key],
                                  f"{text!r} -> {tied}, expected [{expected_key!r}]")


class TestUnrelatedTextMatchesNothing(unittest.TestCase):
    def test_gibberish_and_unrelated_requests_score_zero(self):
        for text in ["what is the weather today", "hello",
                     "employee headcount by department"]:
            self.assertEqual(templates.match(text), [], f"{text!r} unexpectedly matched something")


class TestAntiKeywords(unittest.TestCase):
    def test_anti_keyword_suppresses_score_even_with_a_matching_keyword(self):
        tpl = templates.BY_KEY["purchasing_by_supplier_month"]
        self.assertGreater(templates.score("show me purchase invoice history", tpl), 0)
        self.assertEqual(templates.score("show me overdue purchase invoices", tpl), 0)


if __name__ == "__main__":
    unittest.main()
