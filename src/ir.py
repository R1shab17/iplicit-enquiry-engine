"""
Formal intermediate representation (IR) of an iplicit enquiry.

Why this exists (docs/PROJECT_AUDIT.md #3, #9): enqgen.py and
enquiry_parser.py both moved plain dicts/ElementTree objects around by
convention. Nothing stopped a Field's `source` from naming a Source that
was never declared, or a filter from referencing a `@Param` that was never
declared as a `<Param>` — mistakes that produce well-formed XML which
fails silently in the real iplicit UI (no exception, just a broken
enquiry). This module gives those relationships names and a few
convenience accessors so enquiry_validator.py's cross-reference checks
(and any future tooling — enquiry_doctor.py, enquiry_diff.py,
confidence.py) can be built on typed data instead of re-parsing strings.

This is a read/represent layer, not a rewrite of the generator: enqgen.py
keeps building QueryXml directly (it's simpler and already battle-tested),
and enquiry_parser.parse() now also returns an Enquiry via
Enquiry.from_parsed(...). Nothing here talks to a live iplicit tenant.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field as dc_field
from typing import Optional


_PARAM_TOKEN_RE = re.compile(r"@(\w+)")
# A cascading Param's Setting XML references another Param by bare name in
# a <Binding Name="X" .../> child element — not by an "@X" token. Both are
# "this param is used" for unused-param purposes.
_BINDING_NAME_RE = re.compile(r'<Binding\s+Name="([^"]+)"')


@dataclass(frozen=True)
class Param:
    name: str
    caption: Optional[str] = None
    value_type: Optional[str] = None
    presenter: Optional[str] = None
    setting: Optional[str] = None
    default: Optional[str] = None
    mandatory: bool = False
    help: Optional[str] = None

    @classmethod
    def from_attrib(cls, attrib: dict) -> "Param":
        return cls(
            name=attrib.get("Name"),
            caption=attrib.get("Caption"),
            value_type=attrib.get("ValueType"),
            presenter=attrib.get("Presenter"),
            setting=attrib.get("Setting"),
            default=attrib.get("Default"),
            mandatory=attrib.get("Mandatory") == "True",
            help=attrib.get("Help"),
        )

    def referenced_param_names(self) -> set:
        """@Param tokens appearing inside this param's own Setting XML
        (rare — most Setting XML has none) plus any other Param named in a
        <Binding Name="X"> child (the cascading-picker mechanism)."""
        setting = self.setting or ""
        return set(_PARAM_TOKEN_RE.findall(setting)) | set(_BINDING_NAME_RE.findall(setting))


@dataclass(frozen=True)
class Source:
    name: str
    sql: Optional[str]
    type: Optional[str] = None
    join: Optional[str] = None
    on: Optional[str] = None

    @classmethod
    def from_element(cls, el) -> "Source":
        return cls(
            name=el.get("Name"),
            sql=el.get("Sql"),
            type=el.get("Type"),
            join=el.get("JoinType"),
            on=el.get("JoinCondition"),
        )

    def referenced_param_names(self) -> set:
        """@Param tokens embedded directly in this Source's Sql — used by a
        Type="Sql" source calling a parameterised TVF, e.g.
        "select * from dbo.GetAgedDebt('due_date', @AsOfDate) r"."""
        return set(_PARAM_TOKEN_RE.findall(self.sql or ""))


@dataclass(frozen=True)
class Field:
    name: str
    sql: Optional[str]
    source: Optional[str] = None
    type: Optional[str] = None
    op: Optional[str] = None
    arg: Optional[str] = None
    orr: Optional[str] = None
    output: bool = True
    filter: Optional[str] = None

    @classmethod
    def from_element(cls, el) -> "Field":
        return cls(
            name=el.get("Name"),
            sql=el.get("Sql"),
            source=el.get("Source"),
            type=el.get("Type"),
            op=el.get("FilterOperator"),
            arg=el.get("FilterArgument"),
            orr=el.get("FilterOr"),
            output=el.get("Output") != "False",
            filter=el.get("Filter"),
        )

    def referenced_param_names(self) -> set:
        """@Param tokens used anywhere this field could reference one:
        FilterArgument, FilterOr, or the raw Filter predicate."""
        names = set()
        for text in (self.arg, self.orr, self.filter):
            if text:
                names |= set(_PARAM_TOKEN_RE.findall(text))
        return names


@dataclass(frozen=True)
class Select:
    name: Optional[str]
    union: Optional[str]
    sources: tuple = ()
    fields: tuple = ()

    @classmethod
    def from_parsed(cls, parsed_select: dict) -> "Select":
        return cls(
            name=parsed_select.get("name"),
            union=parsed_select.get("union"),
            sources=tuple(Source.from_element(s) for s in parsed_select["sources"]),
            fields=tuple(Field.from_element(f) for f in parsed_select["fields"]),
        )

    def source_names(self) -> set:
        return {s.name for s in self.sources if s.name}

    def output_field_names(self) -> list:
        return [f.name for f in self.fields if f.output]

    def all_field_names(self) -> list:
        return [f.name for f in self.fields]

    def has_summary_field(self) -> bool:
        return any(f.type == "Summary" for f in self.fields)

    def referenced_param_names(self) -> set:
        names = set()
        for f in self.fields:
            names |= f.referenced_param_names()
        for s in self.sources:
            names |= s.referenced_param_names()
        return names

    def dangling_source_references(self) -> list:
        """Field.source values that don't match any declared Source.name.
        Returns a list of (field_name, source_name) pairs."""
        declared = self.source_names()
        return [(f.name, f.source) for f in self.fields if f.source and f.source not in declared]


@dataclass(frozen=True)
class Layout:
    description: str
    grid: dict = dc_field(default_factory=dict)

    @classmethod
    def from_parsed(cls, parsed_layout: dict) -> "Layout":
        return cls(description=parsed_layout["description"], grid=parsed_layout["grid"])

    @property
    def columns(self) -> list:
        return list(self.grid.get("columns") or [])

    @staticmethod
    def _field_names(entries) -> list:
        """groupRows/groupColumns/groupData entries appear in the wild as
        either a plain field-name string or an object like
        {"field": "X", "sticky": True} / {"field": "X", "aggregator": "sum"}
        — src/build_library.py uses the object form throughout; the master
        skill's grammar example shows the plain-string form. Accept both."""
        out = []
        for e in entries or []:
            if isinstance(e, dict):
                if e.get("field"):
                    out.append(e["field"])
            elif e:
                out.append(e)
        return out

    @property
    def group_rows(self) -> list:
        return self._field_names(self.grid.get("groupRows"))

    @property
    def group_columns(self) -> list:
        return self._field_names(self.grid.get("groupColumns"))

    @property
    def group_data(self) -> list:
        return self._field_names(self.grid.get("groupData"))

    @property
    def includes(self) -> list:
        return list(self.grid.get("includes") or [])

    @property
    def hierarchy(self) -> Optional[dict]:
        return self.grid.get("hierarchy")

    @property
    def detail_columns(self) -> list:
        return list((self.grid.get("detail") or {}).get("columns") or [])

    @property
    def detail_includes(self) -> list:
        return list((self.grid.get("detail") or {}).get("includes") or [])

    def all_referenced_field_names(self) -> set:
        """Every field name this layout references anywhere (columns,
        groupRows/Columns/Data, includes, detail's columns/includes) —
        used to check each one exists among the query's output fields."""
        names = set()
        names |= set(self.columns)
        names |= set(self.group_rows)
        names |= set(self.group_columns)
        names |= set(self.group_data)
        names |= set(self.includes)
        names |= set(self.detail_columns)
        names |= set(self.detail_includes)
        return names


@dataclass(frozen=True)
class Enquiry:
    description: str
    group: Optional[str]
    params: tuple = ()
    selects: tuple = ()
    prop_meta: dict = dc_field(default_factory=dict)
    layouts: tuple = ()
    permissions: tuple = ()

    @classmethod
    def from_parsed(cls, parsed: dict) -> "Enquiry":
        """Build an Enquiry from enquiry_parser.parse()'s return value."""
        model = parsed["model"]
        return cls(
            description=model.get("Description"),
            group=model.get("Group"),
            params=tuple(Param.from_attrib(p) for p in parsed["params"]),
            selects=tuple(Select.from_parsed(s) for s in parsed["selects"]),
            prop_meta=parsed["prop_meta"],
            layouts=tuple(Layout.from_parsed(l) for l in parsed["layouts"]),
            permissions=tuple(parsed["permissions"]),
        )

    def declared_param_names(self) -> set:
        return {p.name for p in self.params if p.name}

    def referenced_param_names(self) -> set:
        names = set()
        for s in self.selects:
            names |= s.referenced_param_names()
        for p in self.params:
            names |= p.referenced_param_names()
        return names

    def unused_params(self) -> set:
        """Params declared but never referenced by any filter/setting."""
        return self.declared_param_names() - self.referenced_param_names()

    def undeclared_param_references(self) -> set:
        """@Param tokens used in a filter but never declared as a <Param>."""
        return self.referenced_param_names() - self.declared_param_names()

    def first_select_output_fields(self) -> list:
        return self.selects[0].output_field_names() if self.selects else []

    def all_output_field_names_across_selects(self) -> set:
        """Union of every Select's output field names — a looser set than
        first_select_output_fields(), useful for layouts that might
        legitimately reference a union member's field."""
        names = set()
        for s in self.selects:
            names |= set(s.output_field_names())
        return names
