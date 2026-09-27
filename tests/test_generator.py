"""Unit tests for src/enqgen.py's QueryXml/envelope assembly."""
import base64
import json
import os
import sys
import unittest
import xml.etree.ElementTree as ET

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from enqgen import (
    setting, param, src, fld, multi_filter, query_xml, meta, m_amount,
    layout, build, PERM,
)


class TestSetting(unittest.TestCase):
    def test_basic_attributes(self):
        s = setting(attribute="Customer", value_member="Code")
        self.assertIn('Attribute="Customer"', s)
        self.assertIn('ValueMember="Code"', s)
        self.assertIn('AllowClosed="True"', s)

    def test_bindings_produce_child_elements(self):
        s = setting(attribute="Period", catalog="PeriodsForFYG_FY_LE",
                    bindings=[("LegalEntityId", "Text", "LegalEntity")])
        self.assertIn("<Binding", s)
        self.assertIn('Name="LegalEntityId"', s)

    def test_filter_is_escaped(self):
        s = setting(attribute="Account", filter='Extra.ar_flag=1 and x="y"')
        self.assertIn("&quot;", s)


class TestFldAndMultiFilter(unittest.TestCase):
    def test_column_type_defaults_when_source_given(self):
        f = fld("AccountId", "account_id", "g")
        self.assertEqual(f["type"], "Column")

    def test_expression_type_defaults_when_no_source(self):
        f = fld("Month", "FORMAT([g].[period_date],'yyyy-MM')")
        self.assertEqual(f["type"], "Expression")

    def test_explicit_type_is_respected(self):
        f = fld("Total", "SUM([g].[amount])", type="Summary")
        self.assertEqual(f["type"], "Summary")

    def test_multi_filter_produces_in_and_is_null_or(self):
        f = multi_filter("LegalEntityId", "legal_entity_id", "g", "LegalEntityId")
        self.assertEqual(f["op"], "In")
        self.assertEqual(f["arg"], "@LegalEntityId")
        self.assertEqual(f["orr"], "@LegalEntityId is null")


class TestQueryXml(unittest.TestCase):
    def _build_xml(self):
        P = [param("LegalEntityId", "Legal entity")]
        S = [{"name": "Main", "sources": [src("g", "[dbo].[dac_gl]", "View")],
              "fields": [multi_filter("LegalEntityId", "legal_entity_id", "g", "LegalEntityId"),
                         fld("Description", "description", "g")]}]
        return query_xml(P, S)

    def test_produces_well_formed_xml(self):
        xml = self._build_xml()
        root = ET.fromstring(xml)  # raises if malformed
        self.assertEqual(root.tag, "Query")

    def test_param_and_field_round_trip(self):
        root = ET.fromstring(self._build_xml())
        params = root.findall("Param")
        self.assertEqual(len(params), 1)
        self.assertEqual(params[0].get("Name"), "LegalEntityId")

        fields = root.find("Select").findall("Field")
        names = [f.get("Name") for f in fields]
        self.assertIn("LegalEntityId", names)
        self.assertIn("Description", names)

    def test_output_false_is_rendered_for_filter_only_fields(self):
        # multi_filter() itself defaults to output=True (it only sets the
        # In/is-null filter idiom) — Output="False" must be requested
        # explicitly via fld(..., output=False), matching how
        # src/build_library.py marks a filter-only field so it doesn't
        # widen an aggregate's implicit GROUP BY (docs/FAILURE_MODES.md #5).
        f = fld("LegalEntityId", "legal_entity_id", "g", op="In", arg="@LegalEntityId",
                orr="@LegalEntityId is null", output=False)
        S = [{"name": "Main", "sources": [src("g", "[dbo].[dac_gl]", "View")], "fields": [f]}]
        root = ET.fromstring(query_xml([], S))
        le_field = root.find("Select").find("Field")
        self.assertEqual(le_field.get("Output"), "False")

    def test_multi_filter_output_defaults_to_true(self):
        f = multi_filter("LegalEntityId", "legal_entity_id", "g", "LegalEntityId")
        S = [{"name": "Main", "sources": [src("g", "[dbo].[dac_gl]", "View")], "fields": [f]}]
        root = ET.fromstring(query_xml([], S))
        le_field = root.find("Select").find("Field")
        self.assertIsNone(le_field.get("Output"))

    def test_special_characters_are_escaped(self):
        P = []
        S = [{"name": "Main", "sources": [src("g", "[dbo].[dac_gl]", "View")],
              "fields": [fld("Weird", 'x = "y" and a < b', "g")]}]
        xml = query_xml(P, S)
        root = ET.fromstring(xml)  # would raise ParseError if unescaped
        field = root.find("Select").find("Field")
        self.assertEqual(field.get("Sql"), 'x = "y" and a < b')

    def test_union_select_carries_union_attribute(self):
        S = [
            {"name": "Main", "sources": [src("g", "[dbo].[dac_gl]", "View")],
             "fields": [fld("Amount", "amount", "g")]},
            {"name": "Other", "union": "UnionAll", "sources": [src("db", "[dbo].[dac_doc_base]", "View")],
             "fields": [fld("Amount", "net_amount", "db")]},
        ]
        root = ET.fromstring(query_xml([], S))
        selects = root.findall("Select")
        self.assertEqual(len(selects), 2)
        self.assertEqual(selects[1].get("Union"), "UnionAll")


class TestBuild(unittest.TestCase):
    def test_envelope_shape(self):
        P = []
        S = [{"name": "Main", "sources": [src("g", "[dbo].[dac_gl]", "View")],
              "fields": [fld("Amount", "amount", "g"), fld("BaseCurrency", "base_currency", "g")]}]
        M = {"Amount": m_amount("Amount", "Amount"), "BaseCurrency": meta("BaseCurrency", "Base currency")}
        L = [layout("Main", ["Amount"], includes=["BaseCurrency"])]
        env_json, model = build("Test enquiry", "Test", query_xml(P, S), M, L,
                                 permissions=[PERM["GeneralLedger.Enquiry"]])

        env = json.loads(env_json)
        self.assertEqual(env["type"], "DbEnquiry")
        self.assertEqual(env["description"], "Test enquiry")
        self.assertIn("data", env)

        decoded_model = json.loads(base64.b64decode(env["data"]).decode("utf-8"))
        self.assertEqual(decoded_model, model)
        self.assertEqual(model["Description"], "Test enquiry")
        self.assertEqual(len(model["RequiredPermissions"]), 1)
        self.assertEqual(model["RequiredPermissions"][0]["AttributeOperationId"], PERM["GeneralLedger.Enquiry"].lower())

    def test_permission_ids_are_lowercased(self):
        P, S = [], [{"name": "Main", "sources": [src("g", "[dbo].[dac_gl]", "View")], "fields": [fld("X", "1", "g")]}]
        _, model = build("T", "Test", query_xml(P, S), {"X": meta("X", "X")},
                          [layout("Main", ["X"])], permissions=["ABCDEF00-0000-0000-0000-000000000000"])
        self.assertEqual(model["RequiredPermissions"][0]["AttributeOperationId"], "abcdef00-0000-0000-0000-000000000000")

    def test_no_permissions_gives_empty_list(self):
        P, S = [], [{"name": "Main", "sources": [src("g", "[dbo].[dac_gl]", "View")], "fields": [fld("X", "1", "g")]}]
        _, model = build("T", "Test", query_xml(P, S), {"X": meta("X", "X")}, [layout("Main", ["X"])])
        self.assertEqual(model["RequiredPermissions"], [])


if __name__ == "__main__":
    unittest.main()
