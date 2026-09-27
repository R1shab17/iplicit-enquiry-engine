"""
Builds the fixture files in this folder. Run from the repo root:

    python3 tests/fixtures/build_fixtures.py

Fixtures are checked-in JSON files (not rebuilt at test time) so tests stay
fast and don't depend on the generator being bug-free — test_generator.py
separately covers enqgen.py itself. Re-run this script and commit the
result whenever a fixture needs to change.

Each "broken_*" fixture starts from a valid build() and then deliberately
corrupts exactly one thing, so it's clear from this file alone which
enquiry_validator.py check each one is meant to trip.
"""
import os
import sys
import json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))

from enqgen import param, src, fld, multi_filter, query_xml, meta, m_amount, m_decimal, m_text, layout, build, PERM

HERE = os.path.dirname(__file__)


def write(name, env_json_str):
    with open(os.path.join(HERE, name), "w", encoding="utf-8") as f:
        f.write(env_json_str)


def _base():
    """A minimal, otherwise-valid single-Select GL enquiry: one optional
    multi-select filter, one plain output column, one amount column with
    its currency member included. Passes every enquiry_validator.py check
    as-is."""
    P = [param("LegalEntityId", "Legal entity")]
    S = [{"name": "Main", "sources": [
            src("g", "[dbo].[dac_gl]", "View"),
         ], "fields": [
            fld("LegalEntityId", "legal_entity_id", "g", op="In", arg="@LegalEntityId",
                orr="@LegalEntityId is null", output=False),
            fld("Description", "description", "g"),
            fld("Amount", "amount", "g"),
            fld("BaseCurrency", "base_currency", "g"),
         ]}]
    M = {"Description": meta("Description", "Description"),
         "Amount": m_amount("Amount", "Amount"),
         "BaseCurrency": m_text("BaseCurrency", "Base currency", 60)}
    L = [layout("Main", ["Description", "Amount"], includes=["BaseCurrency"])]
    return P, S, M, L


# ---------------------------------------------------------------- valid_minimal.json
P, S, M, L = _base()
env, model = build("Fixture: minimal valid enquiry", "Test", query_xml(P, S), M, L,
                    permissions=[PERM["GeneralLedger.Enquiry"]])
write("valid_minimal.json", env)


# ---------------------------------------------------------------- broken_missing_permission.json
P, S, M, L = _base()
env, model = build("Fixture: missing RequiredPermissions", "Test", query_xml(P, S), M, L,
                    permissions=())  # <-- empty: should trip check_permissions
write("broken_missing_permission.json", env)


# ---------------------------------------------------------------- broken_filter_in_no_null.json
P = [param("LegalEntityId", "Legal entity")]
S = [{"name": "Main", "sources": [
        src("g", "[dbo].[dac_gl]", "View"),
     ], "fields": [
        # Deliberately bad: FilterOperator=In with no "@X is null" FilterOr.
        fld("LegalEntityId", "legal_entity_id", "g", op="In", arg="@LegalEntityId", output=False),
        fld("Description", "description", "g"),
     ]}]
M = {"Description": meta("Description", "Description")}
L = [layout("Main", ["Description"])]
env, model = build("Fixture: In filter without is-null OR", "Test", query_xml(P, S), M, L,
                    permissions=[PERM["GeneralLedger.Enquiry"]])
write("broken_filter_in_no_null.json", env)


# ---------------------------------------------------------------- broken_hierarchy_grouprows.json
P = []
S = [{"name": "Main", "sources": [
        src("g", "[dbo].[dac_gl]", "View"),
        src("a", "[dbo].[account]", join="InnerJoin", on="[a].[id] = [g].[account_id]"),
     ], "fields": [
        fld("AccountId", "account_id", "g"),
        fld("Department", "department_code", "g"),
        fld("Total", "SUM([g].[amount])", type="Summary"),
     ]}]
M = {"AccountId": meta("AccountId", "Account"), "Department": meta("Department", "Department"),
     "Total": m_decimal("Total", "Total")}
# Deliberately bad: a saved hierarchy combined with a 2-level groupRows —
# docs/FAILURE_MODES.md #1 (silently returns no data in the real UI).
L = [layout("Balance sheet", ["AccountId", "Department", "Total"],
            group_rows=["Department", "AccountId"],
            extra={"hierarchy": {"treeId": "00000000-0000-0000-0000-000000000000",
                                  "name": "Standard Balance Sheet tree", "other": "Other"}})]
env, model = build("Fixture: hierarchy + multi-level groupRows", "Test", query_xml(P, S), M, L,
                    permissions=[PERM["GeneralLedger.BalanceSheet"]])
write("broken_hierarchy_grouprows.json", env)


# ---------------------------------------------------------------- broken_amount_missing_currency.json
P = []
S = [{"name": "Main", "sources": [
        src("g", "[dbo].[dac_gl]", "View"),
     ], "fields": [
        fld("Description", "description", "g"),
        fld("Amount", "amount", "g"),
        # Note: no BaseCurrency field at all.
     ]}]
M = {"Description": meta("Description", "Description"), "Amount": m_amount("Amount", "Amount")}
# Deliberately bad: Amount is viewType=amount with currencyMember=BaseCurrency,
# but BaseCurrency isn't anywhere in includes/columns — docs/FAILURE_MODES.md #6.
L = [layout("Main", ["Description", "Amount"])]
env, model = build("Fixture: amount column missing currencyMember", "Test", query_xml(P, S), M, L,
                    permissions=[PERM["GeneralLedger.Enquiry"]])
write("broken_amount_missing_currency.json", env)


# ---------------------------------------------------------------- broken_union_mismatch.json
P = []
S = [
    {"name": "Main", "sources": [src("g", "[dbo].[dac_gl]", "View")],
     "fields": [fld("Description", "description", "g"), fld("Amount", "amount", "g")]},
    # Deliberately bad: second Select in the union outputs a different field
    # name ("Notes" instead of "Description") — docs/FAILURE_MODES.md #8.
    {"name": "Other", "union": "UnionAll", "sources": [src("db", "[dbo].[dac_doc_base]", "View")],
     "fields": [fld("Notes", "description", "db"), fld("Amount", "net_amount", "db")]},
]
M = {"Description": meta("Description", "Description"), "Amount": m_decimal("Amount", "Amount")}
L = [layout("Main", ["Description", "Amount"])]
env, model = build("Fixture: mismatched union field lists", "Test", query_xml(P, S), M, L,
                    permissions=[PERM["GeneralLedger.Enquiry"]])
write("broken_union_mismatch.json", env)


# ---------------------------------------------------------------- broken_not_json.json
# Deliberately not a valid DbEnquiry envelope at all — tests the top-level
# load/decode failure path.
write("broken_not_json.json", "{this is not valid json")


# ---------------------------------------------------------------- broken_dangling_source.json
# Deliberately bad: Field "Amount"'s Source="x" names a Source that was
# never declared in this Select (only "g" was) — docs/DISCOVERED_FAILURE_MODES.md #3.
P = []
S = [{"name": "Main", "sources": [src("g", "[dbo].[dac_gl]", "View")],
      "fields": [fld("Description", "description", "g"), fld("Amount", "amount", "x")]}]
M = {"Description": meta("Description", "Description"), "Amount": m_decimal("Amount", "Amount")}
L = [layout("Main", ["Description", "Amount"])]
env, model = build("Fixture: dangling Source reference", "Test", query_xml(P, S), M, L,
                    permissions=[PERM["GeneralLedger.Enquiry"]])
write("broken_dangling_source.json", env)


# ---------------------------------------------------------------- broken_undeclared_param.json
# Deliberately bad: the filter references @LegalEntityId, but no matching
# <Param Name="LegalEntityId"> was declared — docs/DISCOVERED_FAILURE_MODES.md #2.
P = []
S = [{"name": "Main", "sources": [src("g", "[dbo].[dac_gl]", "View")],
      "fields": [fld("LegalEntityId", "legal_entity_id", "g", op="In", arg="@LegalEntityId",
                      orr="@LegalEntityId is null", output=False),
                 fld("Description", "description", "g")]}]
M = {"Description": meta("Description", "Description")}
L = [layout("Main", ["Description"])]
env, model = build("Fixture: undeclared param reference", "Test", query_xml(P, S), M, L,
                    permissions=[PERM["GeneralLedger.Enquiry"]])
write("broken_undeclared_param.json", env)


# ---------------------------------------------------------------- broken_unused_param.json
# Deliberately bad: LegalEntityId is declared but never used in any filter,
# Source Sql, or Binding — docs/DISCOVERED_FAILURE_MODES.md #1.
P = [param("LegalEntityId", "Legal entity")]
S = [{"name": "Main", "sources": [src("g", "[dbo].[dac_gl]", "View")],
      "fields": [fld("Description", "description", "g")]}]
M = {"Description": meta("Description", "Description")}
L = [layout("Main", ["Description"])]
env, model = build("Fixture: unused declared param", "Test", query_xml(P, S), M, L,
                    permissions=[PERM["GeneralLedger.Enquiry"]])
write("broken_unused_param.json", env)


# ---------------------------------------------------------------- broken_layout_missing_field.json
# Deliberately bad: the layout's columns list references "Notes", which the
# query never outputs (only "Description" is an output field).
P = []
S = [{"name": "Main", "sources": [src("g", "[dbo].[dac_gl]", "View")],
      "fields": [fld("Description", "description", "g")]}]
M = {"Description": meta("Description", "Description")}
L = [layout("Main", ["Description", "Notes"])]
env, model = build("Fixture: layout references missing field", "Test", query_xml(P, S), M, L,
                    permissions=[PERM["GeneralLedger.Enquiry"]])
write("broken_layout_missing_field.json", env)


# ---------------------------------------------------------------- broken_orphan_propmeta.json
# Deliberately bad: PropMetaJson has a "Notes" entry, but the query only
# outputs "Description" — stale/dead metadata.
P = []
S = [{"name": "Main", "sources": [src("g", "[dbo].[dac_gl]", "View")],
      "fields": [fld("Description", "description", "g")]}]
M = {"Description": meta("Description", "Description"), "Notes": meta("Notes", "Notes")}
L = [layout("Main", ["Description"])]
env, model = build("Fixture: orphan PropMeta entry", "Test", query_xml(P, S), M, L,
                    permissions=[PERM["GeneralLedger.Enquiry"]])
write("broken_orphan_propmeta.json", env)


print("Wrote fixtures to", HERE)
