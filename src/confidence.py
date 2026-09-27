"""
Confidence/evidence reporting: one place that answers "how much of this
enquiry's schema knowledge is actually confirmed?" — instead of that
judgment being scattered across docs/SCHEMA.md prose, src/schema.py's
`status` field, and generated/INDEX.md's free-text notes
(docs/PROJECT_AUDIT.md #6, #9 item 6).

This module does not add new facts — it reads src/schema.py's existing
CONFIRMED / INFERRED vocabulary and applies it to the tables an actual
enquiry uses, so that judgment is computed once and consumed by
src/enquiry_doctor.py (and anything else that wants it) instead of
re-derived by hand each time.
"""
import re
from dataclasses import dataclass

import schema as schema_module

_BRACKET_TABLE_RE = re.compile(r"\[(?:\w+)\]\.\[(\w+)\]\s*$")
_BARE_TABLE_RE = re.compile(r"^\s*(\w+)\s*$")


def table_name_from_sql(sql):
    """Extract a bare table/view name from a Source's Sql attribute, e.g.
    "[dbo].[dac_gl]" -> "dac_gl", "[generated].[crv_gl]" -> "crv_gl".
    Returns None for anything that isn't a simple bracketed table reference
    (a Type="Sql" source calling a function, for instance) — those aren't
    scored, since there's no single table name to look up."""
    if not sql:
        return None
    m = _BRACKET_TABLE_RE.search(sql.strip())
    if m:
        return m.group(1)
    m = _BARE_TABLE_RE.match(sql)
    return m.group(1) if m else None


@dataclass(frozen=True)
class TableFinding:
    name: str
    status: str  # "confirmed" | "inferred" | "unknown"
    notes: str = ""


def assess_table(name):
    """Look up one bare table/view name's confidence status via schema.py."""
    status = schema_module.table_status(name)
    if status is None:
        return TableFinding(name=name, status="unknown", notes="not present in src/schema.py at all")
    entry = schema_module.TABLES.get(name) or schema_module.PRINCIPAL_VIEWS.get(name) or {}
    return TableFinding(name=name, status=status, notes=entry.get("notes", ""))


def assess_enquiry(ir):
    """Given an src/ir.py Enquiry, return a confidence report:
        {"tables": [TableFinding, ...] (one per distinct table used, sorted),
         "confirmed_count": int, "inferred_count": int, "unknown_count": int,
         "overall": "confirmed" | "mixed" | "unconfirmed"}
    "unknown" means the table isn't in src/schema.py at all (a bigger gap
    than "inferred", which at least has been thought about)."""
    names = set()
    for sel in ir.selects:
        for s in sel.sources:
            n = table_name_from_sql(s.sql)
            if n:
                names.add(n)

    findings = sorted((assess_table(n) for n in names), key=lambda f: f.name)
    confirmed = [f for f in findings if f.status == "confirmed"]
    inferred = [f for f in findings if f.status == "inferred"]
    unknown = [f for f in findings if f.status == "unknown"]

    if not inferred and not unknown:
        overall = "confirmed"
    elif confirmed and (inferred or unknown):
        overall = "mixed"
    else:
        overall = "unconfirmed"

    return {
        "tables": findings,
        "confirmed_count": len(confirmed),
        "inferred_count": len(inferred),
        "unknown_count": len(unknown),
        "overall": overall,
    }


def format_report(report) -> str:
    lines = [f"Overall: {report['overall'].upper()} "
             f"({report['confirmed_count']} confirmed, {report['inferred_count']} inferred, "
             f"{report['unknown_count']} unknown table(s))"]
    for f in report["tables"]:
        marker = {"confirmed": "OK", "inferred": "?!", "unknown": "??"}[f.status]
        line = f"  [{marker}] {f.name}: {f.status}"
        if f.notes:
            line += f" — {f.notes}"
        lines.append(line)
    return "\n".join(lines)
