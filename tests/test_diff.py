"""Unit tests for src/enquiry_diff.py."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from enquiry_diff import diff, format_diff

REPO_ROOT = os.path.join(os.path.dirname(__file__), "..")
GENERATED = os.path.join(REPO_ROOT, "generated")


class TestDiff(unittest.TestCase):
    def test_identical_file_has_no_differences(self):
        path = os.path.join(GENERATED, "gl", "01_gl_trial_balance.json")
        d = diff(path, path)
        self.assertEqual(d["params"]["added"], [])
        self.assertEqual(d["params"]["removed"], [])
        self.assertEqual(d["params"]["changed"], [])
        self.assertEqual(d["layouts"]["added"], [])
        self.assertEqual(d["layouts"]["removed"], [])
        self.assertEqual(d["permissions"]["added"], [])
        self.assertEqual(d["permissions"]["removed"], [])
        self.assertEqual(format_diff(d), "No semantic differences found.")

    def test_mirror_enquiries_show_expected_differences(self):
        d = diff(os.path.join(GENERATED, "ar", "05_aged_debtors_by_customer.json"),
                 os.path.join(GENERATED, "ap", "07_aged_creditors_by_supplier.json"))
        self.assertEqual(d["description"], ("Aged debtors by customer", "Aged creditors by supplier"))
        self.assertEqual(d["group"], ("AR", "AP"))
        self.assertIn("Aged creditors", d["layouts"]["added"])
        self.assertIn("Aged debtors", d["layouts"]["removed"])
        self.assertTrue(d["permissions"]["added"])
        self.assertTrue(d["permissions"]["removed"])

    def test_field_added_and_removed_are_detected(self):
        d = diff(os.path.join(GENERATED, "ar", "05_aged_debtors_by_customer.json"),
                 os.path.join(GENERATED, "ap", "07_aged_creditors_by_supplier.json"))
        main_select = d["selects"][0]
        self.assertEqual(main_select["status"], "compared")
        self.assertIn("ContactAccountCode", main_select["fields"]["removed"])

    def test_source_sql_change_is_detected(self):
        d = diff(os.path.join(GENERATED, "ar", "05_aged_debtors_by_customer.json"),
                 os.path.join(GENERATED, "ap", "07_aged_creditors_by_supplier.json"))
        changed_names = [c[0] for c in d["selects"][0]["sources"]["changed"]]
        self.assertIn("r", changed_names)

    def test_format_diff_is_nonempty_for_real_difference(self):
        d = diff(os.path.join(GENERATED, "sales", "06_top_customers_by_revenue.json"),
                 os.path.join(GENERATED, "sales", "14_credit_notes_by_period.json"))
        text = format_diff(d)
        self.assertNotEqual(text, "No semantic differences found.")
        self.assertIn("Description:", text)


if __name__ == "__main__":
    unittest.main()
