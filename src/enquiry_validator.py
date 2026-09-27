"""
Programmatic checklist validator for iplicit DbEnquiry export JSON files.

Usage:
    python3 enquiry_validator.py file1.json [file2.json ...]

Checks (mirrors docs/FAILURE_MODES.md):
 - envelope/base64/JSON/XML structural integrity (via enquiry_parser.py)
 - principal source is a dac_* view where GL/doc data is involved
 - every FilterOperator="In" has a matching FilterOr="@X is null"-style clause
 - every FilterOperator="Between" uses an ISNULL(...) idiom (not a bare @From/@To)
 - at least one RequiredPermissions entry is present
 - amount-typed PropMetaJson columns have their currencyMember present in every layout's includes
 - hierarchy is not combined with a multi-level groupRows in the same layout
 - every unioned <Select> outputs the same field names, in the same order, as the first
 - PropMetaJson has an entry for every field the first Select outputs (Output != False)

This validator checks *shape*, not your live schema — it cannot confirm a
column or table actually exists. See CLAUDE.md's "one rule that matters most".
"""
import sys
import re

from enquiry_parser import parse, ParseError, output_field_names, principal_source
from schema import is_unsafe_principal


def warn(msgs, msg):
    msgs.append(msg)


def check_query_xml(selects, msgs):
    first_field_names = None
    for si, sel in enumerate(selects):
        field_names = [f.get("Name") for f in sel["fields"]]

        # union field-set check
        if sel["union"]:
            if first_field_names is not None and field_names != first_field_names:
                warn(msgs, f"Select[{si}] (Union={sel['union']}) field list {field_names} "
                           f"does not match first Select's field list {first_field_names}")
        else:
            first_field_names = field_names

        # principal source dac_* check (only flag when it looks like a GL/doc-grain query)
        principal = principal_source(sel)
        if principal is not None and is_unsafe_principal(principal.get("Sql")):
            warn(msgs, f"Select[{si}] principal source '{principal.get('Sql')}' looks like a raw base table "
                       "where a dac_* view (dac_gl/dac_doc_base) exists — legal-entity security may leak rows")

        # In / In-or-null pairing
        for f in sel["fields"]:
            op = f.get("FilterOperator")
            arg = f.get("FilterArgument") or ""
            orr = f.get("FilterOr") or ""
            if op == "In":
                pname_match = re.search(r"@(\w+)", arg)
                pname = pname_match.group(1) if pname_match else None
                if not (pname and re.search(rf"@{pname}\s+is\s+null", orr, re.I)):
                    warn(msgs, f"Field '{f.get('Name')}' uses FilterOperator=In without an "
                               f"'@{pname or '?'} is null' FilterOr — will exclude all rows when the param is empty")
            if op == "Between":
                if "isnull(" not in arg.lower():
                    warn(msgs, f"Field '{f.get('Name')}' uses FilterOperator=Between without ISNULL(...) — "
                               "an empty From/To bound will exclude all rows")


def check_prop_meta(selects, prop_meta, msgs):
    if not selects:
        return
    for name in output_field_names(selects[0]):
        if name not in prop_meta:
            warn(msgs, f"Output field '{name}' has no PropMetaJson entry (won't render/label properly)")


def check_layouts(layouts, prop_meta, msgs):
    for entry in layouts:
        desc = entry["description"]
        grid = entry["grid"]
        group_rows = grid.get("groupRows") or []
        hierarchy = grid.get("hierarchy")
        if hierarchy and len(group_rows) > 1:
            warn(msgs, f"Layout '{desc}': combines a saved hierarchy ({hierarchy.get('name')}) "
                       f"with a multi-level groupRows {group_rows} — known to return no data unless "
                       "the extra level truly is nested inside that tree")

        includes = set(grid.get("includes") or [])
        detail_includes = set((grid.get("detail") or {}).get("includes") or [])
        all_cols = set(grid.get("columns") or []) | set((grid.get("detail") or {}).get("columns") or [])
        for col in all_cols:
            meta = prop_meta.get(col)
            if not meta:
                continue
            if meta.get("viewType") == "amount":
                cm = (meta.get("settings") or {}).get("currencyMember")
                if cm and cm not in includes and cm not in detail_includes and cm not in all_cols:
                    warn(msgs, f"Layout '{desc}': column '{col}' is an amount column needing "
                               f"currencyMember '{cm}', which isn't in includes/columns anywhere in this layout")


def check_permissions(permissions, msgs):
    if not permissions:
        warn(msgs, "RequiredPermissions is empty — the Create button will stay disabled in the UI with no visible error")


def validate_file(path):
    msgs = []
    try:
        parsed = parse(path)
    except ParseError as e:
        return [str(e)]
    except Exception as e:
        return [f"Could not load/decode envelope: {e}"]

    if parsed["env"].get("type") != "DbEnquiry":
        warn(msgs, f"Envelope type is '{parsed['env'].get('type')}', expected 'DbEnquiry'")
    if not parsed["selects"]:
        warn(msgs, "No <Select> blocks found in QueryXml")

    check_query_xml(parsed["selects"], msgs)
    check_prop_meta(parsed["selects"], parsed["prop_meta"], msgs)
    check_layouts(parsed["layouts"], parsed["prop_meta"], msgs)
    check_permissions(parsed["permissions"], msgs)
    return msgs


def main(argv):
    files = argv[1:]
    if not files:
        print(__doc__)
        return 1
    any_issues = False
    for path in files:
        issues = validate_file(path)
        if issues:
            any_issues = True
            print(f"\n[FAIL] {path}")
            for m in issues:
                print(f"   - {m}")
        else:
            print(f"[OK]   {path}")
    return 1 if any_issues else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
