"""
Enquiry Doctor: one command, one enquiry file in, a structured diagnostic
report out.

Usage:
    python3 enquiry_doctor.py <file>.json

This is a better window onto the same information enquiry_validator.py and
confidence.py already compute — not a new source of truth. It exists
because reading a flat list of validator messages doesn't tell you *where*
a problem sits (structure? a parameter? the layout?) or how much of the
enquiry rests on confirmed vs. inferred schema — see docs/PROJECT_AUDIT.md
#9 item 4.

STATUS is PASS only when every check-list section is clean AND the schema
confidence is fully "confirmed". A "mixed" confidence enquiry (uses at
least one inferred/unconfirmed table, like several enquiries in this
library) is a WARN, not a FAIL — it can still be structurally correct,
it's just resting on an assumption someone should verify before trusting
the numbers. Any hard validator issue is a FAIL.
"""
import sys

from enquiry_parser import parse, ParseError
from enquiry_validator import (
    check_query_xml, check_prop_meta, check_layouts, check_permissions,
    check_permission_guid_format, check_source_references, check_param_references,
    check_layout_field_references, check_orphan_prop_meta, check_duplicate_names,
)
from confidence import assess_enquiry, format_report


SECTION_ORDER = ["STRUCTURE", "JOINS", "PARAMETERS", "METADATA", "LAYOUT", "PERMISSIONS"]


def diagnose(path):
    """Returns a dict: {"status": "PASS"|"WARN"|"FAIL", "sections": {name: [msgs]},
    "confidence": <report from confidence.assess_enquiry>, "parse_error": str|None}."""
    try:
        parsed = parse(path)
    except ParseError as e:
        return {"status": "FAIL", "sections": {}, "confidence": None, "parse_error": str(e)}
    except Exception as e:
        return {"status": "FAIL", "sections": {}, "confidence": None, "parse_error": f"Could not load/decode envelope: {e}"}

    ir = parsed["ir"]
    sections = {name: [] for name in SECTION_ORDER}

    # STRUCTURE: envelope shape + the parts of check_query_xml that aren't
    # parameter-filter-specific (union parity, unsafe base table).
    if parsed["env"].get("type") != "DbEnquiry":
        sections["STRUCTURE"].append(f"Envelope type is '{parsed['env'].get('type')}', expected 'DbEnquiry'")
    if not parsed["selects"]:
        sections["STRUCTURE"].append("No <Select> blocks found in QueryXml")
    structure_and_filters = []
    check_query_xml(parsed["selects"], structure_and_filters)
    for m in structure_and_filters:
        # check_query_xml currently interleaves union/base-table (structural)
        # messages with In/Between filter-safety messages (parameter-level);
        # split them post hoc by content rather than restructure that
        # function's signature mid-pass.
        if "FilterOperator=" in m:
            sections["PARAMETERS"].append(m)
        else:
            sections["STRUCTURE"].append(m)

    # JOINS: dangling Field->Source references.
    check_source_references(ir, sections["JOINS"])

    # PARAMETERS: cross-reference param checks, on top of the filter-safety
    # messages already routed above.
    check_param_references(ir, sections["PARAMETERS"])

    # Duplicate-name checks (adversarial) span three sections; route by
    # content rather than restructure check_duplicate_names' signature,
    # same approach as check_query_xml's PARAMETERS/STRUCTURE split above.
    dup_msgs = []
    check_duplicate_names(ir, dup_msgs)
    for m in dup_msgs:
        if m.startswith("Param '"):
            sections["PARAMETERS"].append(m)
        elif "Source name" in m:
            sections["JOINS"].append(m)
        else:
            sections["STRUCTURE"].append(m)

    # METADATA: PropMeta coverage both ways (missing + orphaned).
    check_prop_meta(parsed["selects"], parsed["prop_meta"], sections["METADATA"])
    check_orphan_prop_meta(ir, sections["METADATA"])

    # LAYOUT: hierarchy/groupRows conflict, amount/currencyMember, and
    # layout->output-field references.
    check_layouts(parsed["layouts"], parsed["prop_meta"], sections["LAYOUT"])
    check_layout_field_references(ir, sections["LAYOUT"])

    # PERMISSIONS
    check_permissions(parsed["permissions"], sections["PERMISSIONS"])
    check_permission_guid_format(parsed["permissions"], sections["PERMISSIONS"])

    confidence = assess_enquiry(ir)

    has_hard_issue = any(sections[name] for name in SECTION_ORDER)
    if has_hard_issue:
        status = "FAIL"
    elif confidence["overall"] != "confirmed":
        status = "WARN"
    else:
        status = "PASS"

    return {"status": status, "sections": sections, "confidence": confidence, "parse_error": None}


def format_diagnosis(path, diagnosis) -> str:
    lines = [f"STATUS: {diagnosis['status']}  ({path})"]
    if diagnosis["parse_error"]:
        lines.append(f"\nPARSE ERROR\n  {diagnosis['parse_error']}")
        return "\n".join(lines)

    for name in SECTION_ORDER:
        msgs = diagnosis["sections"][name]
        lines.append(f"\n{name}")
        if not msgs:
            lines.append("  clean")
        else:
            for m in msgs:
                lines.append(f"  - {m}")

    lines.append("\nCONFIDENCE")
    lines.append("  " + format_report(diagnosis["confidence"]).replace("\n", "\n  "))

    lines.append("\nRISKS")
    risky = [f for f in diagnosis["confidence"]["tables"] if f.status != "confirmed"]
    if not risky and diagnosis["status"] != "FAIL":
        lines.append("  none identified")
    else:
        for f in risky:
            lines.append(f"  - {f.name} is {f.status}: verify against a live tenant before trusting output built on it")
        if diagnosis["status"] == "FAIL":
            lines.append("  - structural/cross-reference issues above must be fixed before this enquiry is imported")

    return "\n".join(lines)


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 1
    exit_code = 0
    for path in argv[1:]:
        diagnosis = diagnose(path)
        print(format_diagnosis(path, diagnosis))
        print()
        if diagnosis["status"] == "FAIL":
            exit_code = 1
    return exit_code


if __name__ == "__main__":
    sys.exit(main(sys.argv))
