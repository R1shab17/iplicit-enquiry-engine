"""
Unit tests for tools/enquiry_builder_app.py — the customer-facing web
front end. Tests call its render functions directly (no real HTTP server),
since those functions contain all the actual behavior; do_GET/do_POST are
thin http.server plumbing around them.

This app is a thin skin over src/compiler.py's compile_request(), which
covers all 7 modules (GL, AR, AP, Sales, Purchasing, Bank, Budgets) via
src/templates.py's 14 confirmed report shapes plus a flexible GL-only
fallback — see docs/ROADMAP.md item 10. These tests cover the app's own
job: translating compile_request()'s four possible statuses ("ok",
"ambiguous", "invalid", "unsupported") into the right page, never leaking
internals, and wiring the clarifying-question flow end to end.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))

from enquiry_builder_app import render_form, render_result, render_ambiguous, friendly_notes  # noqa: E402


class TestRenderResultHappyPath(unittest.TestCase):
    def test_valid_gl_fallback_request_produces_the_ready_page(self):
        html_out = render_result("Show me balance by department and cost centre, monthly")
        self.assertIn("Your report is ready", html_out)
        self.assertIn("DbEnquiry", html_out)  # the escaped JSON is present
        self.assertNotIn("class=\"error\"", html_out)

    def test_no_notes_block_when_nothing_to_flag(self):
        html_out = render_result("balance by department")
        self.assertNotIn("A few notes about this report", html_out)

    def test_each_module_s_template_request_produces_the_ready_page(self):
        # One phrasing per module — confirms the app isn't secretly GL-only
        # anymore now that it routes through compile_request().
        requests = [
            "Show me the trial balance",
            "Aged debtors, who owes us",
            "Aged creditors, who do we owe",
            "Top customers by revenue",
            "Purchase invoices by supplier by month",
            "Bank transactions by account",
            "Budget vs actual by cost centre",
        ]
        for text in requests:
            with self.subTest(text=text):
                html_out = render_result(text)
                self.assertIn("Your report is ready", html_out)
                self.assertNotIn("class=\"error\"", html_out)

    def test_confirmed_template_gets_no_confidence_caveat(self):
        html_out = render_result("Show me the trial balance")
        self.assertNotIn("worth double-checking", html_out)
        self.assertNotIn("draft to verify", html_out)

    def test_mixed_confidence_template_shows_a_caveat(self):
        # Bank transactions leans on a table src/schema.py records as
        # inferred rather than confirmed (docs/ROADMAP.md item 4's
        # bank_transaction column list) — src/confidence.py scores this
        # template's overall as "mixed", and the app should say so rather
        # than handing over a silent report.
        html_out = render_result("Bank transactions by account")
        self.assertIn("A few notes about this report", html_out)
        self.assertIn("worth double-checking", html_out)


class TestRenderResultAmbiguousFlow(unittest.TestCase):
    def test_ambiguous_request_offers_a_choice_not_a_guess(self):
        html_out = render_result("I want the aged debt and aged credit position")
        self.assertIn("Which one did you mean?", html_out)
        self.assertIn("Aged debtors by customer", html_out)
        self.assertIn("Aged creditors by supplier", html_out)
        self.assertNotIn("Your report is ready", html_out)

    def test_choosing_a_template_key_resolves_to_the_ready_page(self):
        ambiguous = render_result("I want the aged debt and aged credit position")
        self.assertIn("ar_aged_debtors", ambiguous)
        html_out = render_result("I want the aged debt and aged credit position",
                                   template_key="ar_aged_debtors")
        self.assertIn("Your report is ready", html_out)

    def test_render_ambiguous_escapes_the_request_text(self):
        html_out = render_ambiguous("<script>alert(1)</script>",
                                      [("ar_aged_debtors", "Aged debtors by customer", "AR")])
        self.assertNotIn("<script>alert(1)</script>", html_out)
        self.assertIn("&lt;script&gt;", html_out)


class TestRenderResultGuardrails(unittest.TestCase):
    def test_empty_request_shows_friendly_error(self):
        html_out = render_result("")
        self.assertIn("Please describe the report you", html_out)
        self.assertIn("class=\"error\"", html_out)

    def test_whitespace_only_request_shows_friendly_error(self):
        html_out = render_result("   ")
        self.assertIn("class=\"error\"", html_out)

    def test_truly_out_of_scope_request_shows_friendly_error_not_a_wrong_report(self):
        # Fixed Assets isn't one of the 7 covered modules (docs/ROADMAP.md
        # item 9) and has no GL dimension either — nothing should be built.
        html_out = render_result("Show me our fixed assets register")
        self.assertIn("class=\"error\"", html_out)
        self.assertIn("contact support", html_out)
        self.assertNotIn("Your report is ready", html_out)

    def test_gibberish_request_shows_friendly_error(self):
        html_out = render_result("asdkfj random text with no meaning")
        self.assertIn("class=\"error\"", html_out)
        self.assertNotIn("Your report is ready", html_out)

    def test_no_raw_validator_or_python_internals_leak_to_customer(self):
        # Whatever happens, a customer should never see a stack trace, a
        # module path, or the word "validator"/"NotImplementedError".
        for request in ("", "aged debtors by customer", "balance by department",
                         "fixed assets register", "I want the aged debt and aged credit position"):
            html_out = render_result(request)
            self.assertNotIn("Traceback", html_out)
            self.assertNotIn("NotImplementedError", html_out)
            self.assertNotIn("enquiry_validator", html_out)
            self.assertNotIn("compile_request", html_out)

    def test_html_in_the_request_is_escaped_not_executed(self):
        html_out = render_result("<script>alert(1)</script> balance by department")
        self.assertNotIn("<script>alert(1)</script>", html_out)
        self.assertIn("&lt;script&gt;", html_out)


class TestFriendlyNotes(unittest.TestCase):
    def test_unconfirmed_measure_warning_translated(self):
        raw = ["Measure 'debit' isn't confirmed as its own column on dac_gl ... not fabricating a debit/credit split ..."]
        notes = friendly_notes(raw)
        self.assertTrue(any("net balance" in n for n in notes))

    def test_thin_spec_warning_translated(self):
        raw = ["No recognized dimension or measure keywords found in the request — "
               "this spec is too thin to compile into a meaningful enquiry as-is; treat this as a starting point"]
        notes = friendly_notes(raw)
        self.assertTrue(any("general version" in n for n in notes))

    def test_unrecognized_warning_produces_no_note(self):
        # A warning string that doesn't match any known rule is dropped
        # rather than shown verbatim (it would be internal jargon).
        notes = friendly_notes(["some future warning text nobody has written a rule for yet"])
        self.assertEqual(notes, [])

    def test_duplicate_notes_are_not_repeated(self):
        raw = ["... not fabricating a debit/credit split ...", "... not fabricating a debit/credit split ..."]
        notes = friendly_notes(raw)
        self.assertEqual(len(notes), 1)


class TestRenderForm(unittest.TestCase):
    def test_form_renders_without_error_by_default(self):
        html_out = render_form()
        self.assertNotIn("class=\"error\"", html_out)
        self.assertIn("<form", html_out)

    def test_form_preserves_previous_text_on_error(self):
        html_out = render_form(error="oops", previous_text="balance by <department>")
        self.assertIn("balance by &lt;department&gt;", html_out)


if __name__ == "__main__":
    unittest.main()
