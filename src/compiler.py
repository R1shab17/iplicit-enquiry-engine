"""
Compiles an EnquirySpec (src/spec.py, typically produced by src/nl_parser.py)
into the same (params, selects, propmeta, layouts, permissions) shape
src/build_library.py hand-writes, ready for enqgen.build().

Scope, stated plainly rather than oversold (docs/ROADMAP.md item 10):

  - Only module="GL" is supported. Anything else raises NotImplementedError
    with a pointer to write a build script by hand, the same as every
    document/AR/AP enquiry in generated/ today.
  - Only a flat or single-select, one-or-more-dimension GL enquiry is
    built: the standard join fan-out (src/joins.py's gl_standard_joins),
    optional crv_gl dimension columns, and a Balance (SUM(g.amount))
    measure. No unions, hierarchies, table-valued-function sources, or
    document joins — those need a hand-written script.
  - A measure phrase that isn't confirmed as its own dac_gl column (e.g.
    "debit"/"credit" — dac_gl only has one signed `amount` column, per
    docs/SCHEMA.md) is NOT fabricated as a separate field. It's recorded as
    a warning instead, and the compiled query falls back to Balance.

This module never talks to a live iplicit tenant, and it does NOT replace
enquiry_validator.py/enquiry_doctor.py — compiled output still needs both
before it's trusted, exactly like a hand-written build script. See
CLAUDE.md's "one rule that matters most": this pipeline can get the *shape*
right; it cannot confirm dac_gl/crv_gl's columns actually exist beyond what
docs/SCHEMA.md already documents.
"""
from enqgen import param, fld, multi_filter, query_xml, meta, m_amount, m_decimal, m_text, layout, build, PERM
from joins import gl_standard_joins
from spec import EnquirySpec

# crv_gl's join alias in gl_standard_joins()'s output (src/joins.py).
_DIMENSION_SOURCE = "cg"

# Measure phrases that compile to Balance = SUM(g.amount) — the only
# aggregate confirmed available on dac_gl (a single signed `amount` column).
_BALANCE_MEASURE_PHRASES = {"balance", "net balance", "net", "amount"}


def compile_spec(spec: EnquirySpec):
    """Returns (params, selects, propmeta, layouts, permissions, warnings).
    `warnings` includes spec.notes (the parser's own honesty trail) plus
    anything this function itself couldn't confirm against known schema."""
    if spec.module != "GL":
        hint = spec.module.split(":", 1)[1] if spec.module.startswith("OTHER:") else spec.module
        raise NotImplementedError(
            f"compiler.py only supports module='GL' right now (got a request that looks like {hint!r}) — "
            "see docs/ROADMAP.md item 10. Write a build script by hand using src/enqgen.py "
            "the way src/build_library.py does for other modules."
        )

    warnings = list(spec.notes)

    # gl_standard_joins() always includes p/fy (period/financial_year)
    # regardless of this flag, so a monthly pivot's Month expression always
    # has something to key off; cg (crv_gl) is only joined when a dimension
    # was actually requested, to avoid an unused LEFT JOIN in the compiled SQL.
    sources = gl_standard_joins(include_dimensions=bool(spec.dimensions))

    legal_entity_filter = multi_filter("LegalEntityId", "legal_entity_id", "g", "LegalEntityId")
    legal_entity_filter["output"] = False
    params = [param("LegalEntityId", "Legal entity")]
    fields = [legal_entity_filter]

    propmeta = {}
    layout_columns = []
    layout_includes = []
    group_rows = []

    for dim in spec.dimensions:
        fields.append(fld(dim, dim, _DIMENSION_SOURCE))
        propmeta[dim] = m_text(dim, dim, 120)
        layout_columns.append(dim)
        if dim in spec.group_by:
            group_rows.append({"field": dim, "sticky": True})

    if spec.pivot_by_month:
        fields.append(fld("Month", "FORMAT([p].[date_from],'yyyy-MM')", type="Expression"))
        propmeta["Month"] = m_text("Month", "Month", 80)

    recognized_balance_measure = any(m in _BALANCE_MEASURE_PHRASES for m in spec.measures)
    unrecognized_measures = [m for m in spec.measures if m not in _BALANCE_MEASURE_PHRASES]
    for m in unrecognized_measures:
        warnings.append(
            f"Measure {m!r} isn't confirmed as its own column on dac_gl (only a single signed "
            "`amount` column exists — docs/SCHEMA.md) — not fabricating a debit/credit split; "
            "compiling a Balance (SUM(amount)) measure instead. Verify a real debit/credit "
            "source before trusting a breakdown beyond net balance."
        )

    if recognized_balance_measure or not spec.measures:
        fields.append(fld("Balance", "SUM([g].[amount])", type="Summary"))
        propmeta["Balance"] = m_amount("Balance", "Balance")
        layout_columns.append("Balance")
        fields.append(fld("BaseCurrency", "base_currency", "g"))
        propmeta["BaseCurrency"] = m_text("BaseCurrency", "Base currency", 60)
        layout_includes.append("BaseCurrency")
        if not spec.measures:
            warnings.append("No recognized measure keyword found in the request — defaulted to a "
                             "Balance (SUM(amount)) measure.")
    else:
        # Every requested measure was unrecognized (e.g. only "debit" was
        # asked for, with no "balance"/"net"/"amount" fallback phrase) —
        # still emit a plain, non-aggregated Amount column rather than a
        # query with no measure at all, and say so.
        fields.append(fld("Amount", "amount", "g"))
        propmeta["Amount"] = m_decimal("Amount", "Amount")
        layout_columns.append("Amount")
        warnings.append("None of the requested measures compile to a confirmed dac_gl column — "
                         "defaulted to a plain (non-aggregated) Amount column instead of a Summary.")

    if "FinancialYear" in spec.filters:
        warnings.append("'FinancialYear' filter recognized but not yet wired by compiler.py — "
                         "add it to a build script by hand if needed (see src/build_library.py's "
                         "FinancialYearGroupId examples for the cascading-picker pattern).")
    if "DateRange" in spec.filters:
        warnings.append("'DateRange' filter recognized but not yet wired by compiler.py — "
                         "add a Between/ISNULL date filter by hand if needed (docs/FAILURE_MODES.md #3).")
    if "PeriodId" in spec.filters:
        warnings.append("'PeriodId' filter recognized but not yet wired by compiler.py — "
                         "add it to a build script by hand if needed.")

    selects = [{"name": "Main", "sources": sources, "fields": fields}]
    layouts = [layout(spec.description, layout_columns,
                       group_rows=group_rows or None,
                       group_columns=[{"field": "Month", "total": True}] if spec.pivot_by_month else None,
                       includes=layout_includes or None)]
    permissions = [PERM["GeneralLedger.Enquiry"]]

    return params, selects, propmeta, layouts, permissions, warnings


def compile_and_build(spec: EnquirySpec):
    """Convenience wrapper: compile_spec() then enqgen.build() in one call.
    Returns (export_json_str, model_dict, warnings). Still run the result
    through enquiry_validator.validate_file()/enquiry_doctor.diagnose()
    before trusting or importing it — this function does not do that for
    you."""
    params, selects, propmeta, layouts, permissions, warnings = compile_spec(spec)
    env, model = build(spec.description, "GL", query_xml(params, selects), propmeta, layouts,
                        permissions=permissions)
    return env, model, warnings
