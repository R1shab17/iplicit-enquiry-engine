"""
Unit tests for src/compiler.py — compiling an EnquirySpec into an actual
DbEnquiry export, and confirming every compiled output still passes
enquiry_validator.py (this pipeline does not get a pass on validation just
because it's generated code, same rule as any hand-written build script).
"""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from spec import EnquirySpec
from compiler import compile_spec, compile_and_build, compile_request
from enquiry_validator import validate_file
import templates as templates_module


def _validate_env(env):
    fd, path = tempfile.mkstemp(suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(env)
        return validate_file(path)
    finally:
        os.unlink(path)


class TestCompileSpecScope(unittest.TestCase):
    def test_non_gl_module_raises_not_implemented(self):
        spec = EnquirySpec(module="AR", description="Aged debtors")
        with self.assertRaises(NotImplementedError):
            compile_spec(spec)

    def test_out_of_scope_hint_from_parser_surfaces_in_error_message(self):
        spec = EnquirySpec(module="OTHER:AR", description="Aged debtors by customer")
        with self.assertRaisesRegex(NotImplementedError, "AR"):
            compile_spec(spec)


class TestCompileAndBuildValidatesClean(unittest.TestCase):
    def test_dimension_and_balance_measure_compiles_clean(self):
        spec = EnquirySpec(module="GL", description="Balance by department",
                            dimensions=["Department"], measures=["balance"], group_by=["Department"])
        env, model, warnings = compile_and_build(spec)
        self.assertEqual(_validate_env(env), [])
        self.assertEqual(warnings, [])

    def test_multiple_dimensions_compiles_clean(self):
        spec = EnquirySpec(module="GL", description="Balance by department and cost centre",
                            dimensions=["Department", "CostCentre"], measures=["balance"],
                            group_by=["Department", "CostCentre"])
        env, model, warnings = compile_and_build(spec)
        self.assertEqual(_validate_env(env), [])

    def test_monthly_pivot_compiles_clean(self):
        spec = EnquirySpec(module="GL", description="Balance by department, monthly",
                            dimensions=["Department"], measures=["balance"],
                            group_by=["Department"], pivot_by_month=True)
        env, model, warnings = compile_and_build(spec)
        self.assertEqual(_validate_env(env), [])

    def test_no_dimensions_no_measures_still_compiles_clean(self):
        # Thin spec (e.g. from an unrecognized sentence) — still produces a
        # structurally valid enquiry (a totals-only GL balance), just with
        # warnings explaining what was defaulted.
        spec = EnquirySpec(module="GL", description="Give me a report")
        env, model, warnings = compile_and_build(spec)
        self.assertEqual(_validate_env(env), [])
        self.assertTrue(any("No recognized measure" in w for w in warnings))


class TestCompileSpecWarnings(unittest.TestCase):
    def test_unconfirmed_measure_is_flagged_not_fabricated(self):
        spec = EnquirySpec(module="GL", description="Debit and credit by department",
                            dimensions=["Department"], measures=["debit", "credit"],
                            group_by=["Department"])
        params, selects, propmeta, layouts, permissions, warnings = compile_spec(spec)
        self.assertTrue(any("debit" in w.lower() and "not fabricating" in w for w in warnings))
        self.assertTrue(any("credit" in w.lower() and "not fabricating" in w for w in warnings))
        # No separate Debit/Credit field was invented — only Amount (the
        # non-aggregated fallback, since neither "debit" nor "credit" is a
        # recognized balance-measure phrase).
        field_names = {f["name"] for f in selects[0]["fields"]}
        self.assertNotIn("Debit", field_names)
        self.assertNotIn("Credit", field_names)
        self.assertIn("Amount", field_names)

    def test_balance_measure_present_alongside_unconfirmed_ones_uses_balance(self):
        spec = EnquirySpec(module="GL", description="Balance, debit and credit by department",
                            dimensions=["Department"], measures=["balance", "debit", "credit"],
                            group_by=["Department"])
        params, selects, propmeta, layouts, permissions, warnings = compile_spec(spec)
        field_names = {f["name"] for f in selects[0]["fields"]}
        self.assertIn("Balance", field_names)
        self.assertTrue(any("not fabricating" in w for w in warnings))

    def test_unwired_filters_are_flagged_not_silently_dropped(self):
        spec = EnquirySpec(module="GL", description="Balance by department for a given period",
                            dimensions=["Department"], measures=["balance"],
                            group_by=["Department"], filters=["PeriodId"])
        params, selects, propmeta, layouts, permissions, warnings = compile_spec(spec)
        self.assertTrue(any("PeriodId" in w and "not yet wired" in w for w in warnings))

    def test_parser_notes_carry_through_as_compiler_warnings(self):
        spec = EnquirySpec(module="GL", description="Give me a report", notes=["thin spec note"])
        params, selects, propmeta, layouts, permissions, warnings = compile_spec(spec)
        self.assertIn("thin spec note", warnings)


class TestCompileSpecOutputShape(unittest.TestCase):
    def test_legal_entity_filter_always_present_and_output_false(self):
        spec = EnquirySpec(module="GL", description="Balance by department",
                            dimensions=["Department"], measures=["balance"], group_by=["Department"])
        params, selects, propmeta, layouts, permissions, warnings = compile_spec(spec)
        le_field = next(f for f in selects[0]["fields"] if f["name"] == "LegalEntityId")
        self.assertFalse(le_field["output"])
        self.assertEqual({p["name"] for p in params}, {"LegalEntityId"})

    def test_group_rows_only_include_requested_group_by_dimensions(self):
        spec = EnquirySpec(module="GL", description="Balance by department, shown by cost centre too",
                            dimensions=["Department", "CostCentre"], measures=["balance"],
                            group_by=["Department"])  # only Department requested for grouping
        params, selects, propmeta, layouts, permissions, warnings = compile_spec(spec)
        group_rows = layouts[0]["def"]
        self.assertIn('"Department"', group_rows)
        # CostCentre is an output column but not a groupRows entry.
        import json
        grid = json.loads(layouts[0]["def"])["layout"]["grid"]
        group_row_fields = [g["field"] for g in grid.get("groupRows", [])]
        self.assertEqual(group_row_fields, ["Department"])
        self.assertIn("CostCentre", grid["columns"])


class TestCompileRequestTemplateMatch(unittest.TestCase):
    """compile_request() is the multi-module entry point: a clear template
    match builds that exact confirmed report (docs/ROADMAP.md item 10's
    "complete enquiry builder" expansion) — see src/templates.py for the
    matching rules themselves, tested separately in tests/test_templates.py."""

    def test_clear_template_match_returns_ok_with_template(self):
        result = compile_request("Show me the trial balance")
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["template"].key, "gl_trial_balance")
        self.assertEqual(result["confidence"]["overall"], "confirmed")
        self.assertIn('"type": "DbEnquiry"', result["env"])

    def test_template_result_covers_every_module(self):
        # One phrasing per module, confirming compile_request() isn't
        # secretly GL-only anymore.
        cases = {
            "GL": "trial balance",
            "AR": "aged debtors, who owes us",
            "AP": "aged creditors, who do we owe",
            "Sales": "top customers by revenue",
            "Purchasing": "purchase invoices by supplier by month",
            "Bank": "bank transactions by account",
            "Budgets": "budget vs actual by cost centre",
        }
        for module, text in cases.items():
            with self.subTest(module=module):
                result = compile_request(text)
                self.assertEqual(result["status"], "ok")
                self.assertEqual(result["template"].module, module)

    def test_ambiguous_when_two_templates_tie(self):
        # Force an artificial tie by asking with only a shared-weight phrase
        # from two distinct templates' keyword lists, one keyword each.
        # ("aged debt" and "aged credit" score 1 each and belong to
        # different templates when both phrases appear.)
        result = compile_request("I want the aged debt and aged credit position")
        self.assertEqual(result["status"], "ambiguous")
        keys = {c[0] for c in result["candidates"]}
        self.assertEqual(keys, {"ar_aged_debtors", "ap_aged_creditors"})

    def test_chosen_template_key_resolves_an_ambiguous_result(self):
        ambiguous = compile_request("I want the aged debt and aged credit position")
        chosen_key = sorted(c[0] for c in ambiguous["candidates"])[0]
        resolved = compile_request(None, chosen_template_key=chosen_key)
        self.assertEqual(resolved["status"], "ok")
        self.assertEqual(resolved["template"].key, chosen_key)

    def test_unknown_chosen_template_key_is_unsupported_not_a_crash(self):
        result = compile_request(None, chosen_template_key="not_a_real_key")
        self.assertEqual(result["status"], "unsupported")

    def test_every_template_builds_ok_via_compile_request(self):
        for tpl in templates_module.TEMPLATES:
            with self.subTest(key=tpl.key):
                result = compile_request(None, chosen_template_key=tpl.key)
                self.assertEqual(result["status"], "ok")
                self.assertEqual(result["warnings"], [])


class TestCompileRequestFlexibleGlFallback(unittest.TestCase):
    """A GL request with a custom dimension combination that matches no
    fixed template still falls through to the flexible compiler."""

    def test_custom_gl_dimension_combo_falls_back_and_builds(self):
        result = compile_request("Show me GL balance by department and cost centre, monthly")
        self.assertEqual(result["status"], "ok")
        self.assertIsNone(result["template"])
        self.assertIn('"type": "DbEnquiry"', result["env"])

    def test_fallback_result_still_carries_confidence(self):
        result = compile_request("Balance by fund and location")
        self.assertEqual(result["status"], "ok")
        self.assertIn("confidence", result)


class TestCompileRequestUnsupported(unittest.TestCase):
    def test_out_of_scope_module_with_no_template_match_is_unsupported(self):
        result = compile_request("Show me our fixed assets register")
        self.assertEqual(result["status"], "unsupported")

    def test_gibberish_is_unsupported_not_a_guess(self):
        result = compile_request("asdkfj random text with no meaning")
        self.assertEqual(result["status"], "unsupported")
        self.assertNotIn("env", result)


if __name__ == "__main__":
    unittest.main()
