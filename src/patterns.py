"""
A confirmed-pattern catalogue mined from the 14 real, validated enquiries in
generated/ — docs/ROADMAP.md item 11 ("Knowledge graph / pattern
catalogue"), done at the scope that's actually possible today.

Why 14 and not 640: this session has no live browser/tenant access right
now (see docs/ROADMAP.md item 1 and docs/ARCHITECTURE.md) — there's no
larger raw corpus sitting anywhere in this repo to mine. Everything below
is derived, programmatically, from the 14 enquiries already confirmed and
validated in generated/ — never hand-typed, so it can't drift from what's
actually there. Re-run build_catalogue() (or `python3 src/patterns.py`)
after adding or changing anything in generated/ to refresh it.

WHAT THIS IS: a browsable reference of every confirmed join, output field,
filter idiom, parameter shape, layout shape, and permission this repo has
actual evidence for — each entry carries `confirmed_via`, the exact
generated/ file(s) it was seen in, so nothing here is asserted without a
citation back to a real, validated example.

WHAT THIS IS NOT — read this before wiring it into anything that builds
enquiries: it is NOT a license to freely recombine patterns across
enquiries into new join graphs. A join pattern with one piece of evidence
(most of the AR/AP/Sales/Purchasing/Bank/Budgets ones — see the counts) is
that ONE enquiry's bespoke, hand-verified shape, not a proven general
mechanism the way crv_gl's dimension columns are for GL (docs/ROADMAP.md
item 10's compile_spec()). Assembling two confirmed-in-isolation joins into
a combination nobody has actually run would be exactly the kind of guess
CLAUDE.md's "one rule that matters most" forbids — the fact that each half
is individually confirmed doesn't make the combination confirmed. This
catalogue is meant for two honest uses:
  1. Reference — so a human (or Claude) writing a NEW build script by hand
     can reuse a confirmed alias convention, filter idiom, or join
     condition with confidence instead of re-deriving or guessing it.
  2. Safe, narrow reuse within a single already-confirmed enquiry's own
     shape (src/compiler.py's compile_request() uses it this way — see
     that module's docstring for the exact boundary).
It is not, and should not become, a second flexible query compiler for
modules that don't have one.
"""
from __future__ import annotations

import glob
import os
import re
from collections import OrderedDict
from dataclasses import dataclass, field as dc_field
from typing import Optional

import enquiry_parser
from permissions import PERM

_GENERATED_GLOB = os.path.join(os.path.dirname(__file__), "..", "generated", "*", "*.json")

_ATTRIBUTE_RE = re.compile(r'Attribute="([^"]+)"')
_VALUE_MEMBER_RE = re.compile(r'ValueMember="([^"]+)"')
_CATALOG_RE = re.compile(r'Catalog="([^"]+)"')

_GUID_TO_PERM_NAME = {v.lower(): k for k, v in PERM.items()}


def _module_of(path: str) -> str:
    """generated/gl/01_....json -> "gl". Relies on CLAUDE.md's own module
    folder convention, not on the enquiry's own (differently-named) Group
    field — see src/templates.py's Template.module for the same choice."""
    return os.path.basename(os.path.dirname(path))


def _rel(path: str) -> str:
    """generated/gl/01_....json -> "gl/01_....json" — what confirmed_via
    entries store, short enough to read in a table."""
    parts = path.split(os.sep)
    idx = parts.index("generated") if "generated" in parts else 0
    return "/".join(parts[idx + 1:])


def _table_name_from_sql(sql: Optional[str]) -> Optional[str]:
    """[dbo].[dac_gl] -> dac_gl. Returns None for a Type="Sql" source
    calling a function/subquery — there's no single table name to key on."""
    if not sql:
        return None
    m = re.search(r"\[(?:\w+)\]\.\[(\w+)\]\s*$", sql.strip())
    return m.group(1) if m else None


def classify_filter_idiom(f) -> Optional[str]:
    """Bucket a Field's filter shape into a named idiom, from the actual
    shapes observed across generated/ (see this module's own catalogue
    output for the evidence). Returns None for a field with no filter."""
    if not f.op:
        return None
    arg = f.arg or ""
    orr = f.orr or ""
    if f.op == "In" and orr.rstrip().endswith("is null"):
        return "multi_select_in_or_null"
    if f.op == "Between" and "ISNULL(" in arg:
        return "between_isnull_date_range"
    if f.op == "Equal" and arg.startswith("@"):
        return "equal_param"
    if f.op == "Equal":
        return "equal_literal"
    if f.op in ("Less", "LessOrEqual", "Greater", "GreaterOrEqual") and arg.startswith("@"):
        return "comparison_against_param"
    if f.op == "NotEqual":
        return "not_equal_literal" if not arg.startswith("@") else "not_equal_param"
    return f"other:{f.op}"


def classify_layout(l) -> str:
    """Bucket a Layout's grid shape into a named pattern, from the actual
    shapes observed in generated/ — mirrors the categories
    enquiry_validator.py's hierarchy/groupRows checks already reason about
    (docs/FAILURE_MODES.md #1, docs/DISCOVERED_FAILURE_MODES.md #8)."""
    if l.hierarchy:
        return "hierarchy_pivot"
    if l.group_rows and l.group_columns:
        return "grouped_rows_and_column_pivot"
    if l.group_columns:
        return "column_pivot_no_row_grouping"
    if l.group_rows and l.grid.get("detail"):
        return "grouped_rows_with_drilldown"
    if l.group_rows:
        return "grouped_rows"
    return "flat_list"


@dataclass(frozen=True)
class JoinPattern:
    table: str
    alias: str
    join_type: Optional[str]
    source_type: Optional[str]
    on: Optional[str]
    sql: str
    confirmed_via: tuple = ()

    def key(self):
        return (self.table, self.alias, self.join_type, self.on, self.sql)


@dataclass(frozen=True)
class FieldPattern:
    field_type: Optional[str]
    table: Optional[str]
    source_alias: Optional[str]
    sql: str
    confirmed_via: tuple = ()

    def key(self):
        return (self.field_type, self.table, self.source_alias, self.sql)


@dataclass(frozen=True)
class FilterIdiomPattern:
    shape: str
    op: Optional[str]
    example_arg: Optional[str]
    example_orr: Optional[str]
    confirmed_via: tuple = ()

    def key(self):
        return self.shape


@dataclass(frozen=True)
class ParamPattern:
    attribute: Optional[str]
    value_type: Optional[str]
    presenter: Optional[str]
    value_member: Optional[str]
    catalog: Optional[str]
    confirmed_via: tuple = ()

    def key(self):
        return (self.attribute, self.value_type, self.presenter, self.value_member, self.catalog)


@dataclass(frozen=True)
class LayoutPattern:
    shape: str
    confirmed_via: tuple = ()

    def key(self):
        return self.shape


@dataclass(frozen=True)
class PermissionPattern:
    name: Optional[str]
    guid: str
    confirmed_via: tuple = ()

    def key(self):
        return self.guid


@dataclass
class Catalogue:
    joins: "OrderedDict" = dc_field(default_factory=OrderedDict)
    fields: "OrderedDict" = dc_field(default_factory=OrderedDict)
    filter_idioms: "OrderedDict" = dc_field(default_factory=OrderedDict)
    params: "OrderedDict" = dc_field(default_factory=OrderedDict)
    layouts: "OrderedDict" = dc_field(default_factory=OrderedDict)
    permissions: "OrderedDict" = dc_field(default_factory=OrderedDict)
    files_scanned: tuple = ()

    def evidence_count(self, pattern) -> int:
        return len(pattern.confirmed_via)


def _merge(store: "OrderedDict", pattern, module: str, source_file: str):
    key = pattern.key()
    existing = store.get(key)
    entry = source_file
    if existing is None:
        store[key] = (pattern.__class__(**{**pattern.__dict__, "confirmed_via": (entry,)}), {module})
    else:
        existing_pattern, existing_modules = existing
        if entry not in existing_pattern.confirmed_via:
            merged = existing_pattern.__class__(
                **{**existing_pattern.__dict__, "confirmed_via": existing_pattern.confirmed_via + (entry,)}
            )
            existing_modules.add(module)
            store[key] = (merged, existing_modules)


def build_catalogue(generated_glob: str = _GENERATED_GLOB) -> Catalogue:
    """Parse every generated/<module>/*.json (via enquiry_parser.py + ir.py
    — never hand-typed) and merge every join/field/filter-idiom/param/
    layout/permission it contains into a deduplicated, evidence-counted
    catalogue. Deterministic and read-only: never touches generated/."""
    joins: "OrderedDict" = OrderedDict()
    fields: "OrderedDict" = OrderedDict()
    filter_idioms: "OrderedDict" = OrderedDict()
    params: "OrderedDict" = OrderedDict()
    layouts: "OrderedDict" = OrderedDict()
    permissions: "OrderedDict" = OrderedDict()
    files_scanned = []

    for path in sorted(glob.glob(generated_glob)):
        module = _module_of(path)
        rel = _rel(path)
        files_scanned.append(rel)
        parsed = enquiry_parser.parse(path)
        ir = parsed["ir"]

        for sel in ir.selects:
            source_by_alias = {s.name: s for s in sel.sources}
            for s in sel.sources:
                table = _table_name_from_sql(s.sql) or s.sql
                jp = JoinPattern(table=table, alias=s.name, join_type=s.join,
                                  source_type=s.type, on=s.on, sql=s.sql)
                _merge(joins, jp, module, rel)

            for f in sel.fields:
                src = source_by_alias.get(f.source)
                table = _table_name_from_sql(src.sql) if src else None
                fp = FieldPattern(field_type=f.type, table=table, source_alias=f.source, sql=f.sql or "")
                _merge(fields, fp, module, rel)

                shape = classify_filter_idiom(f)
                if shape:
                    fip = FilterIdiomPattern(shape=shape, op=f.op, example_arg=f.arg, example_orr=f.orr)
                    _merge(filter_idioms, fip, module, rel)

        for p in ir.params:
            setting = p.setting or ""
            attr_m = _ATTRIBUTE_RE.search(setting)
            vm_m = _VALUE_MEMBER_RE.search(setting)
            cat_m = _CATALOG_RE.search(setting)
            pp = ParamPattern(
                attribute=attr_m.group(1) if attr_m else None,
                value_type=p.value_type,
                presenter=p.presenter,
                value_member=vm_m.group(1) if vm_m else None,
                catalog=cat_m.group(1) if cat_m else None,
            )
            _merge(params, pp, module, rel)

        for l in ir.layouts:
            lp = LayoutPattern(shape=classify_layout(l))
            _merge(layouts, lp, module, rel)

        for guid in ir.permissions:
            name = _GUID_TO_PERM_NAME.get((guid or "").lower())
            perm_p = PermissionPattern(name=name, guid=guid)
            _merge(permissions, perm_p, module, rel)

    return Catalogue(
        joins=joins, fields=fields, filter_idioms=filter_idioms, params=params,
        layouts=layouts, permissions=permissions, files_scanned=tuple(files_scanned),
    )


def _fmt_modules(modules) -> str:
    return ", ".join(sorted(modules))


def render_markdown(cat: Catalogue) -> str:
    """A human-readable rollup of the catalogue — the "packages" of
    reusable, cited knowledge this module exists to produce. Regenerated by
    build_docs.py alongside patterns/*.json; never hand-edited."""
    lines = []
    lines.append("# Confirmed pattern catalogue")
    lines.append("")
    lines.append(f"Mined from {len(cat.files_scanned)} real, validated enquiries in `generated/`. "
                  "Regenerate with `python3 src/build_docs.py` after changing anything there. "
                  "See `src/patterns.py`'s module docstring for what this catalogue is — and, "
                  "importantly, is not — a license to do.")
    lines.append("")

    lines.append("## Joins")
    lines.append("")
    lines.append("| Table | Alias | Join type | On | Evidence | Modules | Confirmed via |")
    lines.append("|---|---|---|---|---|---|---|")
    for pattern, modules in sorted(cat.joins.values(), key=lambda pm: (-len(pm[0].confirmed_via), pm[0].table)):
        on = f"`{pattern.on}`" if pattern.on else "*(principal)*"
        lines.append(f"| `{pattern.table}` | `{pattern.alias}` | {pattern.join_type or '-'} | {on} | "
                      f"{len(pattern.confirmed_via)} | {_fmt_modules(modules)} | {', '.join(pattern.confirmed_via)} |")
    lines.append("")

    lines.append("## Fields (columns/expressions/summaries confirmed available per table)")
    lines.append("")
    lines.append("| Type | Table | Alias | SQL | Evidence | Modules |")
    lines.append("|---|---|---|---|---|---|")
    for pattern, modules in sorted(cat.fields.values(),
                                     key=lambda pm: (-len(pm[0].confirmed_via), pm[0].table or "")):
        lines.append(f"| {pattern.field_type} | {pattern.table or '-'} | {pattern.source_alias or '-'} | "
                      f"`{pattern.sql}` | {len(pattern.confirmed_via)} | {_fmt_modules(modules)} |")
    lines.append("")

    lines.append("## Filter idioms")
    lines.append("")
    lines.append("| Shape | Operator | Example argument | Example OR clause | Evidence | Modules |")
    lines.append("|---|---|---|---|---|---|")
    for pattern, modules in sorted(cat.filter_idioms.values(), key=lambda pm: -len(pm[0].confirmed_via)):
        lines.append(f"| `{pattern.shape}` | {pattern.op} | `{pattern.example_arg}` | "
                      f"`{pattern.example_orr}` | {len(pattern.confirmed_via)} | {_fmt_modules(modules)} |")
    lines.append("")

    lines.append("## Parameters")
    lines.append("")
    lines.append("| Attribute | Value type | Presenter | Value member | Catalog | Evidence | Modules |")
    lines.append("|---|---|---|---|---|---|---|")
    for pattern, modules in sorted(cat.params.values(), key=lambda pm: -len(pm[0].confirmed_via)):
        lines.append(f"| {pattern.attribute or '*(none — plain value)*'} | {pattern.value_type} | "
                      f"{pattern.presenter} | {pattern.value_member or '-'} | {pattern.catalog or '-'} | "
                      f"{len(pattern.confirmed_via)} | {_fmt_modules(modules)} |")
    lines.append("")

    lines.append("## Layout shapes")
    lines.append("")
    lines.append("| Shape | Evidence | Modules | Confirmed via |")
    lines.append("|---|---|---|---|")
    for pattern, modules in sorted(cat.layouts.values(), key=lambda pm: -len(pm[0].confirmed_via)):
        lines.append(f"| `{pattern.shape}` | {len(pattern.confirmed_via)} | {_fmt_modules(modules)} | "
                      f"{', '.join(pattern.confirmed_via)} |")
    lines.append("")

    lines.append("## Permissions")
    lines.append("")
    lines.append("| Name | GUID | Evidence | Modules |")
    lines.append("|---|---|---|---|")
    for pattern, modules in sorted(cat.permissions.values(), key=lambda pm: -len(pm[0].confirmed_via)):
        lines.append(f"| {pattern.name or '*(unrecognized — not in src/permissions.py)*'} | `{pattern.guid}` | "
                      f"{len(pattern.confirmed_via)} | {_fmt_modules(modules)} |")
    lines.append("")

    return "\n".join(lines)


if __name__ == "__main__":
    catalogue = build_catalogue()
    print(render_markdown(catalogue))
