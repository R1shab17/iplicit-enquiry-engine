"""
Two ways in, one honesty rule, no live tenant: compiles a customer's
free-text report request into a ready-to-import enquiry export.

  1. compile_request(text) — the entry point tools/enquiry_builder_app.py
     (and anything else customer-facing) should call. It first tries to
     match `text` against src/templates.py's catalog of 14 confirmed,
     already-validated report shapes (src/build_library.py); a clear
     winner builds that exact report, a tie asks the caller to disambiguate
     (return "status": "ambiguous"), and no match at all falls through to
     (2) below. This is how modules without GL's confirmed dimension
     flexibility (AR, AP, Sales, Purchasing, Bank, Budgets) get covered
     without fabricating a new flexible query language for each — see
     docs/ROADMAP.md item 10 and src/templates.py's own docstring.

  2. compile_spec(spec) / compile_and_build(spec) — the original flexible
     GL-only compiler, kept as compile_request()'s fallback for a custom
     GL dimension combination that doesn't match any fixed template (e.g.
     "balance by fund and location"). Scope, stated plainly rather than
     oversold:
       - Only module="GL" is supported. Anything else raises
         NotImplementedError with a pointer to write a build script by
         hand, the same as every document/AR/AP enquiry in generated/
         today (compile_request() catches this and turns it into a plain
         "unsupported" result — see below).
       - Only a flat or single-select, one-or-more-dimension GL enquiry is
         built: the standard join fan-out (src/joins.py's
         gl_standard_joins), optional crv_gl dimension columns, and a
         Balance (SUM(g.amount)) measure. No unions, hierarchies,
         table-valued-function sources, or document joins — those need a
         hand-written script.
       - A measure phrase that isn't confirmed as its own dac_gl column
         (e.g. "debit"/"credit" — dac_gl only has one signed `amount`
         column, per docs/SCHEMA.md) is NOT fabricated as a separate
         field. It's recorded as a warning instead, and the compiled query
         falls back to Balance.

Neither path talks to a live iplicit tenant, and neither replaces
enquiry_validator.py/enquiry_doctor.py/src/confidence.py — compile_request()
runs both the validator and the confidence assessor on every "ok" result
before returning it (never returns a result that failed validation), and
still cannot confirm a column exists beyond what docs/SCHEMA.md already
documents. See CLAUDE.md's "one rule that matters most".
"""
import os
import tempfile

from enqgen import param, fld, multi_filter, query_xml, meta, m_amount, m_decimal, m_text, layout, build, PERM
from joins import gl_standard_joins
from spec import EnquirySpec
import build_library
import templates as templates_module
from nl_parser import parse as parse_request
from enquiry_validator import validate_file
from enquiry_parser import parse as parse_enquiry
from confidence import assess_enquiry

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


def _validate_and_assess(env):
    """Write `env` (an export JSON string) to a throwaway temp file, run it
    through the real validator and the schema-confidence assessor, and
    clean up. Returns (issues, confidence_report) — `issues` is the same
    list enquiry_validator.validate_file() returns (empty means clean)."""
    fd, path = tempfile.mkstemp(suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(env)
        issues = validate_file(path)
        confidence_report = assess_enquiry(parse_enquiry(path)["ir"])
    finally:
        os.unlink(path)
    return issues, confidence_report


def _build_from_template(tpl):
    """Build one of src/templates.py's fixed, already-confirmed report
    shapes via its own build_library.py function — never a second copy of
    the query logic. Still validates before returning "ok", exactly like
    the flexible-GL path, so a template result is held to the same bar."""
    spec = tpl.build_fn()
    env, model = build_library.build_export(spec)
    issues, confidence_report = _validate_and_assess(env)
    if issues:
        # A confirmed template failing validation would mean build_library.py
        # itself regressed — surface it rather than silently degrading, but
        # don't hand a customer raw validator jargon (the app layer does the
        # plain-English translation; this just reports the fact).
        return {"status": "invalid", "template": tpl, "issues": issues}
    return {
        "status": "ok",
        "env": env,
        "model": model,
        "template": tpl,
        "warnings": [],
        "confidence": confidence_report,
        "notes": spec.get("notes", ""),
    }


def compile_request(text, chosen_template_key=None):
    """The customer-facing entry point. Given free-text `text`, returns one
    of:

      {"status": "ok", "env": ..., "model": ..., "template": Template|None,
       "warnings": [...], "confidence": {...}}
          A ready-to-import, already-validated enquiry. `template` is the
          matched src/templates.py.Template if a fixed report shape was
          used, or None if the flexible GL fallback compiled a custom
          dimension combination instead.

      {"status": "ambiguous", "candidates": [(key, title, module), ...]}
          More than one fixed template scored equally highest. The caller
          (tools/enquiry_builder_app.py) should ask the person to pick one,
          then call compile_request(text, chosen_template_key=key) to
          finish — this is the "I will be able to provide whatever the
          tool asks for in return" clarifying-question flow.

      {"status": "invalid", "template": Template|None, "issues": [...]}
          Something compiled but failed enquiry_validator.py — this should
          only happen for the flexible GL fallback (every fixed template is
          validated by tests/test_build_library.py already), and means the
          fallback logic itself has a bug, not that the request was bad.

      {"status": "unsupported", "message": "..."}
          Nothing in this repo can build the request yet — either it names
          another module in a shape none of the 14 templates cover, or it
          doesn't look like a report request at all. Never a guess dressed
          up as an answer (CLAUDE.md's "one rule that matters most").

    Pass `chosen_template_key` (one of templates.BY_KEY's keys) to build a
    specific template directly, skipping the matching step — this is how a
    clarifying-question answer resolves an "ambiguous" result.
    """
    if chosen_template_key:
        tpl = templates_module.BY_KEY.get(chosen_template_key)
        if tpl is None:
            return {"status": "unsupported",
                     "message": f"{chosen_template_key!r} isn't a recognized report type."}
        return _build_from_template(tpl)

    matches = templates_module.match(text)
    if matches:
        top_score = matches[0][1]
        tied = [tpl for tpl, s in matches if s == top_score]
        if len(tied) == 1:
            return _build_from_template(tied[0])
        return {"status": "ambiguous",
                 "candidates": [(t.key, t.title, t.module) for t in tied]}

    # No fixed template matched — fall back to the flexible GL compiler, but
    # only when the request actually looks like a GL dimension/measure ask.
    # Never silently build an irrelevant GL report just because nothing else
    # matched; that would be exactly the guess-as-answer CLAUDE.md forbids.
    spec = parse_request(text)
    if spec.module == "GL" and (spec.dimensions or spec.measures):
        try:
            env, model, warnings = compile_and_build(spec)
        except NotImplementedError as e:
            return {"status": "unsupported", "message": str(e)}
        issues, confidence_report = _validate_and_assess(env)
        if issues:
            return {"status": "invalid", "template": None, "issues": issues}
        return {"status": "ok", "env": env, "model": model, "template": None,
                 "warnings": warnings, "confidence": confidence_report}

    if spec.module.startswith("OTHER:"):
        hint = spec.module.split(":", 1)[1]
        return {"status": "unsupported",
                 "message": f"This looks like a {hint} request. None of this tool's report types "
                            "match it yet — please contact support."}

    return {"status": "unsupported",
             "message": "We couldn't recognize a report type in that request. Try naming a report "
                        "(trial balance, aged debtors, budget vs actual, ...) or describing a General "
                        "Ledger balance by dimension (department, cost centre, fund, ...) — or contact "
                        "support if you need a report this tool doesn't cover yet."}
