"""
Unit tests for src/enquiry_validator.py, driven by the fixtures in
tests/fixtures/ (see tests/fixtures/build_fixtures.py for how each one was
built and which check it's meant to trip).
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from enquiry_validator import validate_file

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")


def fixture(name):
    return os.path.join(FIXTURES, name)


class TestValidatorAgainstFixtures(unittest.TestCase):
    def test_valid_minimal_passes_clean(self):
        issues = validate_file(fixture("valid_minimal.json"))
        self.assertEqual(issues, [])

    def test_missing_permission_is_flagged(self):
        issues = validate_file(fixture("broken_missing_permission.json"))
        self.assertTrue(any("RequiredPermissions is empty" in m for m in issues))

    def test_in_filter_without_is_null_is_flagged(self):
        issues = validate_file(fixture("broken_filter_in_no_null.json"))
        self.assertTrue(any("FilterOperator=In without" in m for m in issues))

    def test_hierarchy_with_multilevel_grouprows_is_flagged(self):
        issues = validate_file(fixture("broken_hierarchy_grouprows.json"))
        self.assertTrue(any("combines a saved hierarchy" in m for m in issues))

    def test_amount_missing_currency_member_is_flagged(self):
        issues = validate_file(fixture("broken_amount_missing_currency.json"))
        self.assertTrue(any("needing currencyMember" in m for m in issues))

    def test_union_field_mismatch_is_flagged(self):
        issues = validate_file(fixture("broken_union_mismatch.json"))
        self.assertTrue(any("does not match first Select's field list" in m for m in issues))

    def test_unparseable_envelope_reports_a_single_clear_message(self):
        issues = validate_file(fixture("broken_not_json.json"))
        self.assertEqual(len(issues), 1)
        self.assertIn("Could not load/decode envelope", issues[0])

    # -- cross-reference checks (src/ir.py), added after these exact
    # mistakes were found in this repo's own generated/ output — see
    # docs/DISCOVERED_FAILURE_MODES.md.

    def test_dangling_source_reference_is_flagged(self):
        issues = validate_file(fixture("broken_dangling_source.json"))
        self.assertTrue(any("isn't declared as a <Source>" in m for m in issues))

    def test_undeclared_param_reference_is_flagged(self):
        issues = validate_file(fixture("broken_undeclared_param.json"))
        self.assertTrue(any("no <Param Name=\"LegalEntityId\"> is declared" in m for m in issues))

    def test_unused_param_is_flagged(self):
        issues = validate_file(fixture("broken_unused_param.json"))
        self.assertTrue(any("is declared but never used" in m for m in issues))

    def test_layout_referencing_missing_field_is_flagged(self):
        issues = validate_file(fixture("broken_layout_missing_field.json"))
        self.assertTrue(any("isn't one of the query's output fields" in m and "Layout" in m for m in issues))

    def test_orphan_prop_meta_is_flagged(self):
        issues = validate_file(fixture("broken_orphan_propmeta.json"))
        self.assertTrue(any("dead metadata" in m for m in issues))


class TestValidatorHelpers(unittest.TestCase):
    def test_between_without_isnull_is_flagged(self):
        # Exercised via enqgen directly rather than a checked-in fixture,
        # since it's a one-field variation on the In/is-null case above.
        from enqgen import param, src, fld, query_xml, meta, layout, build, PERM
        from enquiry_parser import decode_model
        import json
        import base64

        P = [param("DateFrom", "From", "Date", presenter="Date"), param("DateTo", "To", "Date", presenter="Date")]
        S = [{"name": "Main", "sources": [src("g", "[dbo].[dac_gl]", "View")],
              "fields": [fld("PeriodDate", "period_date", "g", op="Between", arg="@DateFrom AND @DateTo"),
                         fld("Description", "description", "g")]}]
        env, _ = build("T", "Test", query_xml(P, S), {"PeriodDate": meta("PeriodDate", "Date"),
                                                        "Description": meta("Description", "Description")},
                        [layout("Main", ["PeriodDate", "Description"])], permissions=[PERM["GeneralLedger.Enquiry"]])

        import tempfile
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as f:
            f.write(env)
            path = f.name
        try:
            issues = validate_file(path)
            self.assertTrue(any("FilterOperator=Between without ISNULL" in m for m in issues))
        finally:
            os.unlink(path)


if __name__ == "__main__":
    unittest.main()
