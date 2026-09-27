"""
Unit tests for src/nl_parser.py (the rule-based keyword-matching prototype)
and src/spec.py's EnquirySpec.

These tests are about the parser's actual, narrow contract — fixed
vocabulary, case-insensitive substring matching — not about "does it
understand English." See src/nl_parser.py's own docstring.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from nl_parser import parse


class TestParseDimensions(unittest.TestCase):
    def test_single_dimension(self):
        spec = parse("Show me GL balance by department")
        self.assertEqual(spec.dimensions, ["Department"])

    def test_multiple_dimensions_in_order_seen(self):
        spec = parse("Balance by department and cost centre")
        self.assertEqual(spec.dimensions, ["Department", "CostCentre"])

    def test_case_insensitive(self):
        spec = parse("BALANCE BY DEPARTMENT")
        self.assertEqual(spec.dimensions, ["Department"])

    def test_cost_center_and_cost_centre_both_map_to_same_column(self):
        self.assertEqual(parse("by cost centre").dimensions, ["CostCentre"])
        self.assertEqual(parse("by cost center").dimensions, ["CostCentre"])

    def test_unrecognized_dimension_is_silently_dropped(self):
        spec = parse("Show me balance by widget type")
        self.assertEqual(spec.dimensions, [])


class TestParseMeasures(unittest.TestCase):
    def test_balance_measure(self):
        self.assertIn("balance", parse("Show balance by department").measures)

    def test_debit_credit_recognized_but_flagged_downstream(self):
        # nl_parser.py recognizes the phrase; it's compiler.py's job to flag
        # that it isn't a confirmed dac_gl column.
        spec = parse("Show debit and credit by department")
        self.assertIn("debit", spec.measures)
        self.assertIn("credit", spec.measures)


class TestParseFilters(unittest.TestCase):
    def test_legal_entity_filter(self):
        self.assertIn("LegalEntityId", parse("GL balance by department, filtered by legal entity").filters)

    def test_period_filter(self):
        self.assertIn("PeriodId", parse("balance by department for a given period").filters)

    def test_no_filters_when_not_mentioned(self):
        self.assertEqual(parse("balance by department").filters, [])


class TestParseGroupByAndPivot(unittest.TestCase):
    def test_group_by_defaults_to_dimensions(self):
        spec = parse("balance by department and cost centre")
        self.assertEqual(spec.group_by, spec.dimensions)

    def test_monthly_pivot_recognized(self):
        self.assertTrue(parse("balance by department, monthly").pivot_by_month)
        self.assertTrue(parse("balance by department by month").pivot_by_month)
        self.assertTrue(parse("balance by department per month").pivot_by_month)

    def test_no_pivot_when_not_mentioned(self):
        self.assertFalse(parse("balance by department").pivot_by_month)


class TestOutOfScopeDetection(unittest.TestCase):
    def test_aged_debtors_request_is_flagged_out_of_scope(self):
        spec = parse("Show me aged debtors by customer")
        self.assertNotEqual(spec.module, "GL")
        self.assertTrue(any("not General Ledger" in n for n in spec.notes))

    def test_bank_request_is_flagged_out_of_scope(self):
        spec = parse("Bank transactions by account")
        self.assertNotEqual(spec.module, "GL")

    def test_out_of_scope_keyword_alongside_a_gl_dimension_still_compiles_as_gl(self):
        # The dimension is the stronger signal — "for our biggest customer"
        # tacked onto a real GL request shouldn't derail it.
        spec = parse("GL balance by department for our biggest customer")
        self.assertEqual(spec.module, "GL")

    def test_plain_gl_request_is_not_flagged(self):
        spec = parse("balance by department and cost centre")
        self.assertEqual(spec.module, "GL")


class TestParseNotes(unittest.TestCase):
    def test_thin_request_gets_a_note(self):
        spec = parse("give me a report")
        self.assertTrue(spec.notes)

    def test_recognized_request_has_no_notes(self):
        spec = parse("balance by department")
        self.assertEqual(spec.notes, [])

    def test_module_is_always_gl(self):
        # The only module src/compiler.py currently supports.
        self.assertEqual(parse("anything at all").module, "GL")

    def test_empty_string_does_not_raise(self):
        spec = parse("")
        self.assertEqual(spec.dimensions, [])
        self.assertTrue(spec.notes)


if __name__ == "__main__":
    unittest.main()
