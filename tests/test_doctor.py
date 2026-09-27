"""Unit tests for src/enquiry_doctor.py."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from enquiry_doctor import diagnose, format_diagnosis, SECTION_ORDER

REPO_ROOT = os.path.join(os.path.dirname(__file__), "..")
GENERATED = os.path.join(REPO_ROOT, "generated")
FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")


class TestDiagnose(unittest.TestCase):
    def test_confirmed_clean_enquiry_is_pass(self):
        d = diagnose(os.path.join(GENERATED, "ar", "05_aged_debtors_by_customer.json"))
        self.assertEqual(d["status"], "PASS")
        for name in SECTION_ORDER:
            self.assertEqual(d["sections"][name], [])
        self.assertEqual(d["confidence"]["overall"], "confirmed")

    def test_mixed_confidence_clean_enquiry_is_warn_not_fail(self):
        d = diagnose(os.path.join(GENERATED, "bank", "10_bank_transactions_by_account.json"))
        self.assertEqual(d["status"], "WARN")
        for name in SECTION_ORDER:
            self.assertEqual(d["sections"][name], [])
        self.assertEqual(d["confidence"]["overall"], "mixed")

    def test_structural_issue_is_fail_regardless_of_confidence(self):
        d = diagnose(os.path.join(FIXTURES, "broken_hierarchy_grouprows.json"))
        self.assertEqual(d["status"], "FAIL")
        self.assertTrue(d["sections"]["LAYOUT"])

    def test_permission_issue_lands_in_permissions_section(self):
        d = diagnose(os.path.join(FIXTURES, "broken_missing_permission.json"))
        self.assertEqual(d["status"], "FAIL")
        self.assertTrue(d["sections"]["PERMISSIONS"])

    def test_filter_safety_issue_lands_in_parameters_section(self):
        d = diagnose(os.path.join(FIXTURES, "broken_filter_in_no_null.json"))
        self.assertEqual(d["status"], "FAIL")
        self.assertTrue(d["sections"]["PARAMETERS"])
        self.assertEqual(d["sections"]["STRUCTURE"], [])

    def test_dangling_source_lands_in_joins_section(self):
        d = diagnose(os.path.join(FIXTURES, "broken_dangling_source.json"))
        self.assertEqual(d["status"], "FAIL")
        self.assertTrue(d["sections"]["JOINS"])

    def test_orphan_metadata_lands_in_metadata_section(self):
        d = diagnose(os.path.join(FIXTURES, "broken_orphan_propmeta.json"))
        self.assertEqual(d["status"], "FAIL")
        self.assertTrue(d["sections"]["METADATA"])

    def test_unparseable_file_is_fail_with_parse_error(self):
        d = diagnose(os.path.join(FIXTURES, "broken_not_json.json"))
        self.assertEqual(d["status"], "FAIL")
        self.assertIsNotNone(d["parse_error"])

    def test_duplicate_field_name_lands_in_structure_section(self):
        d = diagnose(os.path.join(FIXTURES, "broken_duplicate_field_name.json"))
        self.assertEqual(d["status"], "FAIL")
        self.assertTrue(d["sections"]["STRUCTURE"])

    def test_duplicate_source_name_lands_in_joins_section(self):
        d = diagnose(os.path.join(FIXTURES, "broken_duplicate_source_name.json"))
        self.assertEqual(d["status"], "FAIL")
        self.assertTrue(d["sections"]["JOINS"])

    def test_duplicate_param_name_lands_in_parameters_section(self):
        d = diagnose(os.path.join(FIXTURES, "broken_duplicate_param_name.json"))
        self.assertEqual(d["status"], "FAIL")
        self.assertTrue(d["sections"]["PARAMETERS"])

    def test_malformed_permission_guid_lands_in_permissions_section(self):
        d = diagnose(os.path.join(FIXTURES, "broken_permission_guid_format.json"))
        self.assertEqual(d["status"], "FAIL")
        self.assertTrue(d["sections"]["PERMISSIONS"])

    def test_hierarchy_no_grouprows_lands_in_layout_section(self):
        d = diagnose(os.path.join(FIXTURES, "broken_hierarchy_no_grouprows.json"))
        self.assertEqual(d["status"], "FAIL")
        self.assertTrue(d["sections"]["LAYOUT"])

    def test_every_generated_enquiry_is_pass_or_warn_never_fail(self):
        import glob
        for path in sorted(glob.glob(os.path.join(GENERATED, "*", "*.json"))):
            d = diagnose(path)
            self.assertIn(d["status"], ("PASS", "WARN"), f"{path} unexpectedly FAILed the doctor")


class TestFormatDiagnosis(unittest.TestCase):
    def test_includes_status_line_and_all_sections(self):
        d = diagnose(os.path.join(GENERATED, "ar", "05_aged_debtors_by_customer.json"))
        text = format_diagnosis("some/path.json", d)
        self.assertIn("STATUS: PASS", text)
        for name in SECTION_ORDER:
            self.assertIn(name, text)
        self.assertIn("CONFIDENCE", text)
        self.assertIn("RISKS", text)

    def test_parse_error_short_circuits_sections(self):
        d = diagnose(os.path.join(FIXTURES, "broken_not_json.json"))
        text = format_diagnosis("some/path.json", d)
        self.assertIn("PARSE ERROR", text)
        self.assertNotIn("STRUCTURE", text)


if __name__ == "__main__":
    unittest.main()
