"""Unit tests for src/ir.py's typed intermediate representation."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from ir import Param, Source, Field, Select, Layout, Enquiry


class TestParam(unittest.TestCase):
    def test_from_attrib_basic(self):
        p = Param.from_attrib({"Name": "LegalEntityId", "Caption": "Legal entity", "Mandatory": "True"})
        self.assertEqual(p.name, "LegalEntityId")
        self.assertTrue(p.mandatory)

    def test_from_attrib_defaults_mandatory_false(self):
        p = Param.from_attrib({"Name": "X"})
        self.assertFalse(p.mandatory)

    def test_referenced_param_names_finds_binding(self):
        setting = '<Setting Attribute="Period"><Binding Name="LegalEntityId" ValueType="Text" PropertyName="LegalEntity"/></Setting>'
        p = Param.from_attrib({"Name": "PeriodId", "Setting": setting})
        self.assertEqual(p.referenced_param_names(), {"LegalEntityId"})

    def test_referenced_param_names_empty_when_no_setting(self):
        p = Param.from_attrib({"Name": "X"})
        self.assertEqual(p.referenced_param_names(), set())


class TestSource(unittest.TestCase):
    def test_from_element_like_dict(self):
        class FakeEl:
            def get(self, k):
                return {"Name": "g", "Sql": "[dbo].[dac_gl]", "Type": "View", "JoinType": "Principal"}.get(k)
        s = Source.from_element(FakeEl())
        self.assertEqual(s.name, "g")
        self.assertEqual(s.sql, "[dbo].[dac_gl]")

    def test_referenced_param_names_from_sql(self):
        s = Source(name="r", sql="select * from dbo.GetAgedDebt('due_date', @AsOfDate) r")
        self.assertEqual(s.referenced_param_names(), {"AsOfDate"})

    def test_referenced_param_names_empty(self):
        s = Source(name="g", sql="[dbo].[dac_gl]")
        self.assertEqual(s.referenced_param_names(), set())


class TestField(unittest.TestCase):
    def _field(self, **overrides):
        attrs = {"Name": "X", "Sql": "x", "Source": "g", "Type": "Column", "Output": None}
        attrs.update(overrides)

        class FakeEl:
            def get(self, k):
                return attrs.get(k)
        return Field.from_element(FakeEl())

    def test_output_defaults_true(self):
        f = self._field()
        self.assertTrue(f.output)

    def test_output_false_when_marked(self):
        f = self._field(Output="False")
        self.assertFalse(f.output)

    def test_referenced_param_names_collects_arg_orr_filter(self):
        f = self._field(FilterArgument="@A", FilterOr="@B is null", Filter="@C = 1")
        self.assertEqual(f.referenced_param_names(), {"A", "B", "C"})

    def test_referenced_param_names_empty_when_no_filter(self):
        f = self._field()
        self.assertEqual(f.referenced_param_names(), set())


class TestSelect(unittest.TestCase):
    def _select(self, sources, fields):
        return {"name": "Main", "union": None, "sources": sources, "fields": fields}

    def _el(self, attrs):
        class FakeEl:
            def get(self, k):
                return attrs.get(k)
        return FakeEl()

    def test_source_names(self):
        sel = Select.from_parsed(self._select(
            [self._el({"Name": "g", "Sql": "[dbo].[dac_gl]"})],
            []))
        self.assertEqual(sel.source_names(), {"g"})

    def test_dangling_source_references(self):
        sel = Select.from_parsed(self._select(
            [self._el({"Name": "g", "Sql": "[dbo].[dac_gl]"})],
            [self._el({"Name": "Amount", "Sql": "amount", "Source": "x", "Type": "Column"})]))
        self.assertEqual(sel.dangling_source_references(), [("Amount", "x")])

    def test_no_dangling_references_when_source_declared(self):
        sel = Select.from_parsed(self._select(
            [self._el({"Name": "g", "Sql": "[dbo].[dac_gl]"})],
            [self._el({"Name": "Amount", "Sql": "amount", "Source": "g", "Type": "Column"})]))
        self.assertEqual(sel.dangling_source_references(), [])

    def test_output_field_names_excludes_output_false(self):
        sel = Select.from_parsed(self._select(
            [self._el({"Name": "g"})],
            [self._el({"Name": "A", "Source": "g", "Output": None}),
             self._el({"Name": "B", "Source": "g", "Output": "False"})]))
        self.assertEqual(sel.output_field_names(), ["A"])

    def test_has_summary_field(self):
        sel = Select.from_parsed(self._select(
            [self._el({"Name": "g"})],
            [self._el({"Name": "Total", "Type": "Summary"})]))
        self.assertTrue(sel.has_summary_field())

    def test_referenced_param_names_includes_source_sql(self):
        sel = Select.from_parsed(self._select(
            [self._el({"Name": "r", "Sql": "select * from f(@X) r"})],
            [self._el({"Name": "A", "Source": "r", "FilterArgument": "@Y"})]))
        self.assertEqual(sel.referenced_param_names(), {"X", "Y"})


class TestLayout(unittest.TestCase):
    def test_accepts_plain_string_group_rows(self):
        l = Layout.from_parsed({"description": "X", "grid": {"groupRows": ["Department", "AccountId"]}})
        self.assertEqual(l.group_rows, ["Department", "AccountId"])

    def test_accepts_object_group_rows(self):
        # This is the shape src/build_library.py actually uses in the wild.
        l = Layout.from_parsed({"description": "X", "grid": {
            "groupRows": [{"field": "Department", "sticky": True}, {"field": "AccountId", "sticky": True}]}})
        self.assertEqual(l.group_rows, ["Department", "AccountId"])

    def test_group_columns_and_group_data_extract_field_key(self):
        l = Layout.from_parsed({"description": "X", "grid": {
            "groupColumns": [{"field": "Month", "total": True}],
            "groupData": [{"field": "Amount", "aggregator": "sum"}]}})
        self.assertEqual(l.group_columns, ["Month"])
        self.assertEqual(l.group_data, ["Amount"])

    def test_all_referenced_field_names_union(self):
        l = Layout.from_parsed({"description": "X", "grid": {
            "columns": ["A"], "groupRows": ["B"], "includes": ["C"],
            "detail": {"columns": ["D"], "includes": ["E"]}}})
        self.assertEqual(l.all_referenced_field_names(), {"A", "B", "C", "D", "E"})

    def test_hierarchy_property(self):
        tree = {"treeId": "x", "name": "Standard Balance Sheet tree"}
        l = Layout.from_parsed({"description": "X", "grid": {"hierarchy": tree}})
        self.assertEqual(l.hierarchy, tree)


class TestEnquiry(unittest.TestCase):
    def _el(self, attrs):
        class FakeEl:
            def get(self, k):
                return attrs.get(k)
        return FakeEl()

    def _parsed(self, params, selects, prop_meta=None, layouts=None, permissions=None):
        return {
            "model": {"Description": "Test", "Group": "GL"},
            "params": params,
            "selects": selects,
            "prop_meta": prop_meta or {},
            "layouts": layouts or [],
            "permissions": permissions or [],
        }

    def test_unused_params(self):
        params = [{"Name": "LegalEntityId"}]
        selects = [{"name": "Main", "union": None,
                    "sources": [self._el({"Name": "g"})],
                    "fields": [self._el({"Name": "Description", "Source": "g"})]}]
        ir = Enquiry.from_parsed(self._parsed(params, selects))
        self.assertEqual(ir.unused_params(), {"LegalEntityId"})

    def test_param_used_via_filter_is_not_unused(self):
        params = [{"Name": "LegalEntityId"}]
        selects = [{"name": "Main", "union": None,
                    "sources": [self._el({"Name": "g"})],
                    "fields": [self._el({"Name": "LegalEntityId", "Source": "g",
                                          "FilterArgument": "@LegalEntityId", "Output": "False"})]}]
        ir = Enquiry.from_parsed(self._parsed(params, selects))
        self.assertEqual(ir.unused_params(), set())

    def test_param_used_via_binding_is_not_unused(self):
        params = [
            {"Name": "LegalEntityId"},
            {"Name": "FinancialYearGroupId",
             "Setting": '<Setting><Binding Name="LegalEntityId" ValueType="Text" PropertyName="LegalEntity"/></Setting>'},
        ]
        ir = Enquiry.from_parsed(self._parsed(params, []))
        self.assertEqual(ir.unused_params(), {"FinancialYearGroupId"})  # nothing binds to THIS one

    def test_undeclared_param_references(self):
        params = []
        selects = [{"name": "Main", "union": None,
                    "sources": [self._el({"Name": "g"})],
                    "fields": [self._el({"Name": "X", "Source": "g", "FilterArgument": "@Ghost"})]}]
        ir = Enquiry.from_parsed(self._parsed(params, selects))
        self.assertEqual(ir.undeclared_param_references(), {"Ghost"})

    def test_first_select_output_fields(self):
        selects = [{"name": "Main", "union": None,
                    "sources": [self._el({"Name": "g"})],
                    "fields": [self._el({"Name": "A", "Source": "g", "Output": None}),
                               self._el({"Name": "B", "Source": "g", "Output": "False"})]}]
        ir = Enquiry.from_parsed(self._parsed([], selects))
        self.assertEqual(ir.first_select_output_fields(), ["A"])


if __name__ == "__main__":
    unittest.main()
