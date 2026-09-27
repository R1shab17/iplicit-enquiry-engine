"""
Programmatic checklist validator for iplicit DbEnquiry export JSON files.

Usage:
    python3 enquiry_validator.py file1.json [file2.json ...]

Checks (mirrors docs/FAILURE_MODES.md and docs/DISCOVERED_FAILURE_MODES.md):

Structural (envelope/XML/JSON shape):
 - envelope/base64/JSON/XML structural integrity (via enquiry_parser.py)
 - principal source is a dac_* view where GL/doc data is involved
 - every FilterOperator="In" has a matching FilterOr="@X is null"-style clause
 - every FilterOperator="Between" uses an ISNULL(...) idiom (not a bare @From/@To)
 - at least one RequiredPermissions entry is present
 - amount-typed PropMetaJson columns have their currencyMember present in every layout's includes
 - hierarchy is not combined with a multi-level groupRows in the same layout
 - every unioned <Select> outputs the same field names, in the same order, as the first
 - PropMetaJson has an entry for every field the first Select outputs (Output != False)

Cross-reference (via src/ir.py — added in the engine-hardening pass after
these exact mistakes were found in this repo's own generated/ output; see
docs/DISCOVERED_FAILURE_MODES.md):
 - every Field's Source attribute names a Source actually declared in that Select
 - every "@Param" used in a filter/Source-Sql, and every cascading <Binding
   Name="..."> target, names a Param actually declared
 - every declared Param is referenced somewhere (else it's a dead picker)
 - every layout column/groupRows/groupColumns/groupData/includes/detail
   field names a field the query actually outputs
 - every PropMetaJson entry names a field the query actually outputs
 - no Select declares the same Source name or Field name twice, and no
   enquiry declares the same Param name twice (adversarial pass — see
   docs/DISCOVERED_FAILURE_MODES.md #4-6; not observed live, kept as a
   permanent check per operating principle #6)

Adversarial (added attacking enqgen.py's own output rather than from a
discovered live bug — docs/DISCOVERED_FAILURE_MODES.md #7-8):
 - hierarchy requires exactly one groupRows level, not merely "not more
   than one" — zero groupRows leaves the tree with nothing to bucket
 - every RequiredPermissions entry is GUID-shaped

This validator checks *shape*, not your live schema — it cannot confirm a
column or table actually exists. See CLAUDE.md's "one rule that matters most".
"""
import sys
import re

from enquiry_parser import parse, ParseError, output_field_names, principal_source
from schema import is_unsafe_principal


_GUID_RE = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")


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
        if hierarchy:
            n = len(group_rows)
            if n > 1:
                # Confirmed-live: docs/FAILURE_MODES.md #1.
                warn(msgs, f"Layout '{desc}': combines a saved hierarchy ({hierarchy.get('name')}) "
                           f"with a multi-level groupRows {group_rows} — known to return no data unless "
                           "the extra level truly is nested inside that tree")
            elif n == 0:
                # Logically derived, not live-confirmed: every hierarchy
                # layout actually built in this repo (generated/gl/
                # 04_pl_by_month.json) pairs the tree with exactly one
                # groupRows entry naming the field whose values map onto
                # tree nodes — see docs/DISCOVERED_FAILURE_MODES.md #8.
                warn(msgs, f"Layout '{desc}': combines a saved hierarchy ({hierarchy.get('name')}) "
                           "with no groupRows at all — a hierarchy needs exactly one groupRows entry "
                           "naming the field whose values map onto tree nodes (see "
                           "generated/gl/04_pl_by_month.json for the confirmed-working pattern)")

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


def check_permission_guid_format(permissions, msgs):
    """Every RequiredPermissions entry (AttributeOperationId) should be a
    GUID. Adversarial check — attacking enqgen.py's own output rather than
    a bug found live; no generated/ enquiry currently fails it (they all
    come from src/permissions.py's PERM table), but src/enqgen.py's build()
    happily accepts and lowercases any string, so a typo'd permission id
    passed by hand would otherwise ship silently. See
    docs/DISCOVERED_FAILURE_MODES.md #7."""
    for pid in permissions:
        if not pid or not _GUID_RE.match(pid):
            warn(msgs, f"RequiredPermissions entry {pid!r} doesn't look like a GUID "
                       "(AttributeOperationId) — likely a typo'd or hand-written permission id; "
                       "use src/permissions.py's PERM table instead of a literal string")


def check_source_references(ir, msgs):
    """Every Field.Source must name a Source declared in the same Select
    (docs/DISCOVERED_FAILURE_MODES.md #3)."""
    for si, sel in enumerate(ir.selects):
        for field_name, source_name in sel.dangling_source_references():
            warn(msgs, f"Select[{si}]: Field '{field_name}' has Source=\"{source_name}\", which isn't "
                       f"declared as a <Source> in this Select — the generated SQL will reference an "
                       f"undefined alias")


def check_param_references(ir, msgs):
    """Every '@Param'/Binding reference must resolve to a declared Param,
    and every declared Param must be used somewhere
    (docs/DISCOVERED_FAILURE_MODES.md #1, #2)."""
    undeclared = ir.undeclared_param_references()
    for pname in sorted(undeclared):
        warn(msgs, f"'@{pname}' (or a <Binding Name=\"{pname}\">) is referenced, but no <Param Name=\"{pname}\"> "
                   f"is declared — likely a typo'd or renamed parameter")

    unused = ir.unused_params()
    for pname in sorted(unused):
        warn(msgs, f"Param '{pname}' is declared but never used in any filter, Source Sql, or cascading "
                   f"Binding — it will show as a picker in the UI that has no effect")


def check_layout_field_references(ir, msgs):
    """Every layout column/groupRows/groupColumns/groupData/includes/detail
    entry must name a field the query actually outputs."""
    all_out = set(ir.first_select_output_fields())
    for l in ir.layouts:
        missing = l.all_referenced_field_names() - all_out
        for name in sorted(missing):
            warn(msgs, f"Layout '{l.description}' references field '{name}', which isn't one of the "
                       f"query's output fields")


def check_orphan_prop_meta(ir, msgs):
    """Every PropMetaJson entry must name a field the query actually outputs."""
    all_out = set(ir.first_select_output_fields())
    orphan = set(ir.prop_meta.keys()) - all_out
    for name in sorted(orphan):
        warn(msgs, f"PropMetaJson has an entry for '{name}', which isn't one of the query's output "
                   f"fields (dead metadata — harmless, but likely stale)")


def check_duplicate_names(ir, msgs):
    """No Select should declare the same Source name or Field name twice,
    and no enquiry should declare the same Param name twice — all three are
    well-formed XML/JSON that the iplicit builder cannot disambiguate.
    Adversarial: not observed in this repo's own (clean) generated/ output,
    added by attacking enqgen.py's own output rather than from a discovered
    live bug — see docs/DISCOVERED_FAILURE_MODES.md #4-6."""
    for si, sel in enumerate(ir.selects):
        for name in sel.duplicate_source_names():
            warn(msgs, f"Select[{si}]: Source name '{name}' is declared more than once — "
                       "any Field referencing it is ambiguous about which JOIN it means")
        for name in sel.duplicate_field_names():
            warn(msgs, f"Select[{si}]: Field name '{name}' is declared more than once — "
                       "PropMetaJson/layout references to it are ambiguous about which one they mean")
    for name in ir.duplicate_param_names():
        warn(msgs, f"Param '{name}' is declared more than once — the parameter panel would show "
                   "duplicate pickers with unpredictable which-one-wins behaviour")


def check_cross_references(ir, msgs):
    """All five IR-based cross-reference/adversarial checks together — the
    checks that need src/ir.py rather than raw XML/JSON: do the names
    different parts of the enquiry use to refer to each other actually
    resolve, and are they unique? None of this needs live-schema knowledge
    — it's pure internal consistency, and the first four already caught
    three real bugs in this repo's own generated/ output (a dangling
    Binding reference and two dead parameters) — see
    docs/DISCOVERED_FAILURE_MODES.md. Split into the functions above so
    tooling (src/enquiry_doctor.py) can report them under separate
    headings; validate_file() below still runs all of them as one pass."""
    check_source_references(ir, msgs)
    check_param_references(ir, msgs)
    check_layout_field_references(ir, msgs)
    check_orphan_prop_meta(ir, msgs)
    check_duplicate_names(ir, msgs)


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
    check_permission_guid_format(parsed["permissions"], msgs)
    check_cross_references(parsed["ir"], msgs)
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
