"""
Unit tests for src/patterns.py — the confirmed-pattern catalogue mined from
generated/'s 14 real enquiries (docs/ROADMAP.md item 11).

These tests check the catalogue is derived correctly (evidence counts and
confirmed_via citations trace back to real files) and that the classifiers
(classify_filter_idiom, classify_layout) bucket the actual shapes seen in
generated/ the way the catalogue's own docs/PATTERNS.md output claims.
"""
import glob
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import patterns
from ir import Field, Layout

GENERATED_COUNT = len(glob.glob(os.path.join(os.path.dirname(__file__), "..", "generated", "*", "*.json")))


class TestBuildCatalogue(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cat = patterns.build_catalogue()

    def test_scans_every_generated_file(self):
        self.assertEqual(len(self.cat.files_scanned), GENERATED_COUNT)
        self.assertEqual(len(self.cat.files_scanned), 14)

    def test_confirmed_via_entries_are_real_files(self):
        generated_dir = os.path.join(os.path.dirname(__file__), "..", "generated")
        for pattern_obj, _modules in self.cat.joins.values():
            for rel in pattern_obj.confirmed_via:
                self.assertTrue(os.path.isfile(os.path.join(generated_dir, rel)),
                                 f"{rel} (cited by a join pattern) isn't a real file")

    def test_every_store_is_nonempty(self):
        self.assertTrue(self.cat.joins)
        self.assertTrue(self.cat.fields)
        self.assertTrue(self.cat.filter_idioms)
        self.assertTrue(self.cat.params)
        self.assertTrue(self.cat.layouts)
        self.assertTrue(self.cat.permissions)

    def test_dac_doc_base_principal_join_evidence_matches_manual_count(self):
        # Cross-check against the manual grep done while designing this
        # catalogue: dac_doc_base as a bare Principal source (no On clause)
        # appears in exactly 6 of the 14 files.
        principal_doc_base = [
            p for (p, _m) in self.cat.joins.values()
            if p.table == "dac_doc_base" and p.join_type == "Principal"
        ]
        self.assertEqual(len(principal_doc_base), 1)
        self.assertEqual(len(principal_doc_base[0].confirmed_via), 6)

    def test_legal_entity_filter_idiom_confirmed_in_all_14(self):
        multi_select = [p for (p, _m) in self.cat.filter_idioms.values()
                         if p.shape == "multi_select_in_or_null"]
        self.assertEqual(len(multi_select), 1)
        self.assertEqual(len(multi_select[0].confirmed_via), 14)

    def test_contact_account_code_confirmed_once(self):
        code_fields = [p for (p, _m) in self.cat.fields.values()
                        if p.table == "contact_account" and p.sql == "code"]
        self.assertEqual(len(code_fields), 1)
        self.assertEqual(code_fields[0].confirmed_via, ("ar/05_aged_debtors_by_customer.json",))

    def test_permission_guids_resolve_to_known_names_where_expected(self):
        named = [p for (p, _m) in self.cat.permissions.values() if p.name == "AR.Enquiry"]
        self.assertEqual(len(named), 1)


class TestClassifyFilterIdiom(unittest.TestCase):
    def _field(self, **kwargs):
        return Field(name="X", sql="x", **kwargs)

    def test_multi_select_in_or_null(self):
        f = self._field(op="In", arg="@LegalEntityId", orr="@LegalEntityId is null")
        self.assertEqual(patterns.classify_filter_idiom(f), "multi_select_in_or_null")

    def test_between_isnull_date_range(self):
        f = self._field(op="Between", arg="ISNULL(@DateFrom,{0}) AND ISNULL(@DateTo,{0})")
        self.assertEqual(patterns.classify_filter_idiom(f), "between_isnull_date_range")

    def test_equal_param(self):
        f = self._field(op="Equal", arg="@Currency")
        self.assertEqual(patterns.classify_filter_idiom(f), "equal_param")

    def test_equal_literal(self):
        f = self._field(op="Equal", arg="'BS'")
        self.assertEqual(patterns.classify_filter_idiom(f), "equal_literal")

    def test_no_op_is_none(self):
        f = self._field()
        self.assertIsNone(patterns.classify_filter_idiom(f))


class TestClassifyLayout(unittest.TestCase):
    def _layout(self, grid):
        return Layout(description="x", grid=grid)

    def test_flat_list(self):
        self.assertEqual(patterns.classify_layout(self._layout({"columns": ["A"]})), "flat_list")

    def test_grouped_rows(self):
        grid = {"columns": ["A"], "groupRows": [{"field": "A"}]}
        self.assertEqual(patterns.classify_layout(self._layout(grid)), "grouped_rows")

    def test_grouped_rows_with_drilldown(self):
        grid = {"columns": ["A"], "groupRows": [{"field": "A"}], "detail": {"columns": ["B"]}}
        self.assertEqual(patterns.classify_layout(self._layout(grid)), "grouped_rows_with_drilldown")

    def test_hierarchy_pivot(self):
        grid = {"columns": ["A"], "groupRows": [{"field": "A"}], "hierarchy": {"treeId": "x"}}
        self.assertEqual(patterns.classify_layout(self._layout(grid)), "hierarchy_pivot")

    def test_grouped_rows_and_column_pivot(self):
        grid = {"columns": ["A"], "groupRows": [{"field": "A"}], "groupColumns": [{"field": "Month"}]}
        self.assertEqual(patterns.classify_layout(self._layout(grid)), "grouped_rows_and_column_pivot")


class TestRenderMarkdown(unittest.TestCase):
    def test_renders_without_error_and_mentions_every_section(self):
        cat = patterns.build_catalogue()
        md = patterns.render_markdown(cat)
        for heading in ("## Joins", "## Fields", "## Filter idioms", "## Parameters",
                        "## Layout shapes", "## Permissions"):
            self.assertIn(heading, md)


if __name__ == "__main__":
    unittest.main()
