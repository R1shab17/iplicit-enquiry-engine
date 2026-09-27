"""Unit tests for src/confidence.py."""
import os
import sys
import unittest
import glob

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from confidence import table_name_from_sql, assess_table, assess_enquiry
from enquiry_parser import parse

REPO_ROOT = os.path.join(os.path.dirname(__file__), "..")
GENERATED = os.path.join(REPO_ROOT, "generated")


class TestTableNameFromSql(unittest.TestCase):
    def test_bracketed_two_part_name(self):
        self.assertEqual(table_name_from_sql("[dbo].[dac_gl]"), "dac_gl")

    def test_bracketed_generated_schema(self):
        self.assertEqual(table_name_from_sql("[generated].[crv_gl]"), "crv_gl")

    def test_bare_name(self):
        self.assertEqual(table_name_from_sql("dac_gl"), "dac_gl")

    def test_function_call_sql_is_not_scored(self):
        # A Type="Sql" source calling a TVF isn't a single table reference.
        self.assertIsNone(table_name_from_sql("select * from [dbo].[GetAgedDebt]('due_date', @AsOfDate) r"))

    def test_none_input(self):
        self.assertIsNone(table_name_from_sql(None))


class TestAssessTable(unittest.TestCase):
    def test_confirmed_table(self):
        f = assess_table("dac_gl")
        self.assertEqual(f.status, "confirmed")

    def test_inferred_table(self):
        f = assess_table("bank_transaction")
        self.assertEqual(f.status, "inferred")

    def test_crv_gl_is_confirmed(self):
        # Regression: crv_gl was missing from src/schema.py's TABLES dict
        # and scored "unknown" for every GL-grain enquiry that (correctly)
        # joins it — see docs/SCHEMA.md's "Analytic-dimension views" note.
        f = assess_table("crv_gl")
        self.assertEqual(f.status, "confirmed")

    def test_unknown_table(self):
        f = assess_table("some_table_never_documented")
        self.assertEqual(f.status, "unknown")


class TestAssessEnquiry(unittest.TestCase):
    def test_bank_transactions_is_mixed(self):
        parsed = parse(os.path.join(GENERATED, "bank", "10_bank_transactions_by_account.json"))
        report = assess_enquiry(parsed["ir"])
        self.assertEqual(report["overall"], "mixed")
        names = {f.name for f in report["tables"]}
        self.assertIn("bank_transaction", names)

    def test_no_generated_enquiry_scores_fully_unconfirmed(self):
        # Every enquiry in the library joins at least one confirmed table
        # (dac_gl/dac_doc_base/account/...), so none should be 100% guesswork.
        for path in sorted(glob.glob(os.path.join(GENERATED, "*", "*.json"))):
            parsed = parse(path)
            report = assess_enquiry(parsed["ir"])
            self.assertNotEqual(report["overall"], "unconfirmed", f"{path} scored fully unconfirmed")

    def test_no_generated_enquiry_has_unknown_tables(self):
        # After the crv_gl fix, every table referenced anywhere in the
        # library should at least be a known (confirmed or inferred) entry
        # in src/schema.py — "unknown" means schema.py itself has a gap.
        for path in sorted(glob.glob(os.path.join(GENERATED, "*", "*.json"))):
            parsed = parse(path)
            report = assess_enquiry(parsed["ir"])
            self.assertEqual(report["unknown_count"], 0,
                              f"{path} references a table missing from src/schema.py entirely: "
                              f"{[f.name for f in report['tables'] if f.status == 'unknown']}")


if __name__ == "__main__":
    unittest.main()
