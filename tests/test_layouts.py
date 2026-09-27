"""Unit tests for src/layouts.py's PropMetaJson and layout helpers."""
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from layouts import (
    meta, m_catalog, m_amount, m_decimal, m_date, m_text, m_link, m_status,
    m_int, m_bit, layout,
)


class TestMetaHelpers(unittest.TestCase):
    def test_meta_basic_shape(self):
        m = meta("Description", "Description")
        self.assertEqual(m["name"], "Description")
        self.assertEqual(m["label"], "Description")
        self.assertTrue(m["visible"])
        self.assertNotIn("settings", m)  # no kwargs => no settings key

    def test_meta_with_settings(self):
        m = meta("X", "X", foo="bar")
        self.assertEqual(m["settings"], {"foo": "bar"})

    def test_m_catalog_sets_attribute(self):
        m = m_catalog("ContactAccountId", "Customer", "Customer")
        self.assertEqual(m["viewType"], "catalog")
        self.assertEqual(m["dataType"], "guid")
        self.assertEqual(m["settings"]["attribute"], "Customer")

    def test_m_amount_sets_currency_member(self):
        m = m_amount("Amount", "Amount")
        self.assertEqual(m["viewType"], "amount")
        self.assertEqual(m["settings"]["currencyMember"], "BaseCurrency")

    def test_m_amount_custom_currency_member(self):
        m = m_amount("Amount", "Amount", currency_member="Currency")
        self.assertEqual(m["settings"]["currencyMember"], "Currency")

    def test_m_decimal_has_no_currency_member(self):
        m = m_decimal("Outstanding", "Outstanding")
        self.assertEqual(m["viewType"], "decimal")
        self.assertNotIn("settings", m)

    def test_m_date(self):
        m = m_date("DocDate", "Document date")
        self.assertEqual(m["viewType"], "date")
        self.assertEqual(m["dataType"], "date")

    def test_m_link_sets_id_and_attribute_members(self):
        m = m_link("DocNo", "Document")
        self.assertEqual(m["viewType"], "link")
        self.assertEqual(m["settings"]["idMember"], "DocId")
        self.assertEqual(m["settings"]["attributeMember"], "Attribute")

    def test_m_status_defaults(self):
        m = m_status()
        self.assertEqual(m["name"], "Status")
        self.assertEqual(m["viewType"], "status")
        self.assertEqual(m["dataType"], "int64")

    def test_m_int_and_m_bit(self):
        self.assertEqual(m_int("Qty", "Quantity")["viewType"], "integer")
        self.assertEqual(m_bit("IsHold", "On hold")["viewType"], "checkbox")

    def test_m_text(self):
        m = m_text("Notes", "Notes", 200)
        self.assertEqual(m["viewType"], "text")
        self.assertEqual(m["defaultWidth"], 200)


class TestLayout(unittest.TestCase):
    def _grid(self, l):
        return json.loads(l["def"])["layout"]["grid"]

    def test_flat_list_has_no_group_keys(self):
        l = layout("Flat", ["A", "B"])
        grid = self._grid(l)
        self.assertEqual(grid["columns"], ["A", "B"])
        self.assertNotIn("groupRows", grid)
        self.assertNotIn("groupColumns", grid)

    def test_pivot_sets_group_rows_and_columns(self):
        l = layout("Pivot", ["A"], group_rows=["Dept"], group_columns=[{"field": "Month", "total": True}],
                   group_data=[{"field": "Amount", "aggregator": "sum"}])
        grid = self._grid(l)
        self.assertEqual(grid["groupRows"], ["Dept"])
        self.assertEqual(grid["groupColumns"], [{"field": "Month", "total": True}])
        self.assertEqual(grid["groupData"], [{"field": "Amount", "aggregator": "sum"}])

    def test_includes_and_widths(self):
        l = layout("X", ["A"], includes=["BaseCurrency"], widths={"A": 150})
        grid = self._grid(l)
        self.assertEqual(grid["includes"], ["BaseCurrency"])
        self.assertEqual(grid["widths"], {"A": 150})

    def test_extra_merges_hierarchy(self):
        tree = {"treeId": "abc", "name": "Standard Balance Sheet tree", "other": "Other"}
        l = layout("X", ["A"], group_rows=["AccountId"], extra={"hierarchy": tree})
        grid = self._grid(l)
        self.assertEqual(grid["hierarchy"], tree)
        self.assertEqual(grid["groupRows"], ["AccountId"])

    def test_detail_is_preserved(self):
        detail = {"columns": ["X"], "includes": [], "sortBy": []}
        l = layout("X", ["A"], group_rows=["Dept"], detail=detail)
        grid = self._grid(l)
        self.assertEqual(grid["detail"], detail)

    def test_description_is_top_level(self):
        l = layout("My description", ["A"])
        self.assertEqual(l["description"], "My description")


if __name__ == "__main__":
    unittest.main()
