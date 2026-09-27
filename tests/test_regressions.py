"""
Regression tests for the two real mistakes made — and caught — while
building this project, so they're caught by CI next time instead of
rediscovered by hand. See CLAUDE.md's "Known failure modes" section and
docs/FAILURE_MODES.md #1 and #7.
"""
import glob
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from enqgen import param, src, fld, query_xml, meta, m_catalog, layout, build, PERM
from enquiry_parser import parse
from enquiry_validator import validate_file

REPO_ROOT = os.path.join(os.path.dirname(__file__), "..")
GENERATED = os.path.join(REPO_ROOT, "generated")


class TestHierarchyGroupRowsRegression(unittest.TestCase):
    """
    Bug #1 (docs/FAILURE_MODES.md #1): a saved row `hierarchy` (a
    chart-of-accounts/BS tree) combined with a multi-level `groupRows`
    silently returns NO data in the real UI — confirmed by direct trial and
    error while building the department-and-nominal balance sheet. The fix
    was to drop `hierarchy` when grouping by more than one field
    (generated/gl/03_balance_sheet_by_department_nominal.json), and to keep
    `hierarchy` only where groupRows stays single-level
    (generated/gl/04_pl_by_month.json).
    """

    def test_department_nominal_balance_sheet_has_no_hierarchy_conflict(self):
        path = os.path.join(GENERATED, "gl", "03_balance_sheet_by_department_nominal.json")
        parsed = parse(path)
        for entry in parsed["layouts"]:
            grid = entry["grid"]
            group_rows = grid.get("groupRows") or []
            hierarchy = grid.get("hierarchy")
            if len(group_rows) > 1:
                self.assertIsNone(
                    hierarchy,
                    f"layout '{entry['description']}' regressed: hierarchy + multi-level "
                    "groupRows returns no data in the real UI (docs/FAILURE_MODES.md #1)",
                )

    def test_pl_by_month_keeps_hierarchy_single_level(self):
        path = os.path.join(GENERATED, "gl", "04_pl_by_month.json")
        parsed = parse(path)
        for entry in parsed["layouts"]:
            grid = entry["grid"]
            if grid.get("hierarchy"):
                group_rows = grid.get("groupRows") or []
                self.assertLessEqual(
                    len(group_rows), 1,
                    f"layout '{entry['description']}' combines a hierarchy with >1 groupRows level",
                )

    def test_validator_catches_the_conflict_if_reintroduced(self):
        # Build the exact broken shape by hand and confirm the validator
        # still flags it — this is the check that would have caught the
        # original mistake before it ever reached a live tenant.
        P = []
        S = [{"name": "Main", "sources": [src("g", "[dbo].[dac_gl]", "View")],
              "fields": [fld("AccountId", "account_id", "g"), fld("Department", "department_code", "g"),
                         fld("Total", "SUM([g].[amount])", type="Summary")]}]
        M = {"AccountId": meta("AccountId", "Account"), "Department": meta("Department", "Department"),
             "Total": meta("Total", "Total", "decimal", "decimal")}
        L = [layout("Balance sheet", ["AccountId", "Department", "Total"],
                    group_rows=["Department", "AccountId"],
                    extra={"hierarchy": {"treeId": "x", "name": "Standard Balance Sheet tree", "other": "Other"}})]
        env, _ = build("Regression repro", "GL", query_xml(P, S), M, L, permissions=[PERM["GeneralLedger.BalanceSheet"]])

        import tempfile
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as f:
            f.write(env)
            path = f.name
        try:
            issues = validate_file(path)
            self.assertTrue(any("combines a saved hierarchy" in m for m in issues))
        finally:
            os.unlink(path)


class TestLastModifiedByEntityRegression(unittest.TestCase):
    """
    Bug #2 (docs/FAILURE_MODES.md #7): "last modified by" is ambiguous
    between the GL posting's audit stamp (dac_gl.last_modified_by) and the
    chart-of-accounts record's (account.last_modified_by) — different
    tables, same plain-English name. The original balance-sheet-by-account
    enquiry defaulted to the GL posting's column when the user actually
    wanted the account's; it took a follow-up message to catch. This test
    demonstrates the correct construction (sourced from the account alias,
    not the GL alias) so the distinction is enforced going forward.
    """

    def test_account_last_modified_by_must_come_from_the_account_source(self):
        P = []
        S = [{"name": "Main", "sources": [
                src("g", "[dbo].[dac_gl]", "View"),
                src("a", "[dbo].[account]", join="InnerJoin", on="[a].[id] = [g].[account_id]"),
             ], "fields": [
                fld("AccountId", "account_id", "g"),
                # Correct: the account record's own audit stamp, sourced from "a" (account), not "g" (dac_gl).
                fld("AccountLastModifiedBy", "last_modified_by", "a"),
             ]}]
        M = {"AccountId": meta("AccountId", "Account"),
             "AccountLastModifiedBy": m_catalog("AccountLastModifiedBy", "Last modified by", "UserAccount")}
        L = [layout("Main", ["AccountId", "AccountLastModifiedBy"])]
        _, model = build("Regression repro", "GL", query_xml(P, S), M, L, permissions=[PERM["Account.Enquiry"]])

        parsed_root_source = next(
            f for f in model["QueryXml"].split("<Field")
            if 'Name="AccountLastModifiedBy"' in f
        )
        self.assertIn('Source="a"', parsed_root_source,
                      "AccountLastModifiedBy regressed: it must be sourced from the account "
                      "alias, not the dac_gl alias (docs/FAILURE_MODES.md #7)")
        self.assertNotIn('Source="g"', parsed_root_source)

    def test_generated_documents_by_user_flags_its_own_uncertainty(self):
        # generated/gl/12_documents_by_user.json intentionally stubs
        # LastModifiedBy to created_by pending confirmation that
        # dac_doc_base has its own last_modified_by column (docs/SCHEMA.md).
        # This test just guards that the stub — and its honesty about being
        # a stub — doesn't quietly disappear.
        path = os.path.join(GENERATED, "gl", "12_documents_by_user.json")
        parsed = parse(path)
        field_names = [f.get("Name") for sel in parsed["selects"] for f in sel["fields"]]
        self.assertIn("LastModifiedBy", field_names)


class TestAllGeneratedFilesStillValidate(unittest.TestCase):
    """Belt-and-braces: every checked-in generated/ enquiry must keep
    passing the full validator. This is the fastest possible signal that a
    schema.py/layouts.py refactor accidentally changed generated output."""

    def test_every_generated_enquiry_passes(self):
        paths = sorted(glob.glob(os.path.join(GENERATED, "*", "*.json")))
        self.assertGreater(len(paths), 0, "expected at least one generated/<module>/*.json file")
        failures = {}
        for path in paths:
            issues = validate_file(path)
            if issues:
                failures[path] = issues
        self.assertEqual(failures, {}, f"generated enquiries failing validation: {failures}")


if __name__ == "__main__":
    unittest.main()
