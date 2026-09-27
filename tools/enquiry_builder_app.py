#!/usr/bin/env python3
"""
Report builder — a customer-facing "describe it, get the file" tool.

Run:
    python3 tools/enquiry_builder_app.py

Then open http://localhost:8765 in a browser. Type a plain-English request
for a report — General Ledger, Aged debtors/creditors, Top customers,
Purchase invoices, Overdue invoices, Bank transactions, Manual journals,
Documents by user, Budget vs actual, or Credit notes — click Generate, and
get back a ready-to-import iplicit report file. Prompt in, file out, no
jargon in between. If a request is genuinely ambiguous between two report
types, the tool asks which one you meant instead of guessing.

This is a thin, friendly front end over src/compiler.py's compile_request()
(itself built on src/templates.py's 14 confirmed report shapes plus a
flexible General-Ledger-only fallback for custom dimension combinations —
see src/compiler.py's own docstring and docs/ROADMAP.md item 10). It adds
no new report-building logic of its own. Anything it can't build reliably —
another module entirely (Fixed Assets, Projects, ...), or a request that
doesn't read as a report at all — it says so in plain language and points
to support rather than handing over a guess. It never talks to a live
iplicit tenant — it only produces the file a person then pastes into
iplicit's own Enquiries > Import from clipboard dialog.

Stdlib only, so it runs anywhere Python 3 runs — nothing to install.
"""
import html
import http.server
import os
import socketserver
import sys
from urllib.parse import parse_qs

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from compiler import compile_request  # noqa: E402

PORT = int(os.environ.get("ENQUIRY_BUILDER_PORT", "8765"))

EXAMPLES = [
    "Show me the trial balance",
    "Aged debtors by customer",
    "Top customers by revenue",
    "Overdue purchase invoices",
    "Balance by fund and location, monthly",
]

PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Report builder</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
  :root {{ color-scheme: light; }}
  body {{ font-family: -apple-system, Segoe UI, Roboto, Helvetica, Arial, sans-serif;
          max-width: 720px; margin: 48px auto; padding: 0 20px; color: #1a1a1a; }}
  h1 {{ font-size: 1.5rem; margin-bottom: 4px; }}
  p.lead {{ color: #555; margin-top: 0; }}
  textarea {{ width: 100%; font-size: 1rem; padding: 10px; border: 1px solid #ccc;
              border-radius: 6px; box-sizing: border-box; font-family: inherit; }}
  textarea#output {{ font-family: ui-monospace, Consolas, monospace; font-size: 0.8rem; background: #f7f7f8; }}
  button {{ margin-top: 12px; background: #2563eb; color: white; border: none;
            padding: 10px 20px; border-radius: 6px; font-size: 1rem; cursor: pointer; }}
  button:hover {{ background: #1d4ed8; }}
  button.secondary {{ background: #6b7280; }}
  button.secondary:hover {{ background: #4b5563; }}
  .error {{ background: #fef2f2; border: 1px solid #fca5a5; color: #991b1b;
            padding: 10px 14px; border-radius: 6px; }}
  .notes {{ background: #eff6ff; border: 1px solid #bfdbfe; color: #1e3a8a;
            padding: 10px 14px; border-radius: 6px; }}
  .notes ul {{ margin: 4px 0 0 0; padding-left: 18px; }}
  .examples {{ color: #777; font-size: 0.85rem; margin-top: 4px; }}
  .steps {{ background: #f0fdf4; border: 1px solid #bbf7d0; padding: 10px 14px; border-radius: 6px; }}
  .choices {{ display: flex; flex-direction: column; gap: 8px; margin: 14px 0; }}
  .choice {{ display: block; text-align: left; background: white; color: #1a1a1a;
             border: 1px solid #ccc; border-radius: 6px; padding: 12px 14px; cursor: pointer; }}
  .choice:hover {{ border-color: #2563eb; background: #f5f8ff; }}
  .choice .title {{ font-weight: 600; }}
  .choice .module {{ color: #777; font-size: 0.85rem; }}
  a {{ color: #2563eb; }}
</style>
</head>
<body>
{body}
</body>
</html>
"""


def _page(body):
    return PAGE.format(body=body)


def render_form(error=None, previous_text=""):
    error_html = f'<p class="error">{html.escape(error)}</p>' if error else ""
    examples_html = " &nbsp;|&nbsp; ".join(f'<a href="#" onclick="fill(this)">{html.escape(e)}</a>' for e in EXAMPLES)
    return _page(f"""
      <h1>Report builder</h1>
      <p class="lead">Describe the report you'd like, in plain English, and we'll build the file for you.</p>
      {error_html}
      <form method="post" action="/generate">
        <textarea name="request" rows="3" placeholder="e.g. Aged debtors by customer">{html.escape(previous_text)}</textarea>
        <div class="examples">Try: {examples_html}</div>
        <button type="submit">Generate report</button>
      </form>
      <script>
        function fill(a) {{
          document.querySelector('textarea[name=request]').value = a.textContent;
          return false;
        }}
      </script>
    """)


def render_ambiguous(request_text, candidates):
    """candidates: [(key, title, module), ...]. Each renders as a button
    that resubmits the same request text plus the chosen template key — the
    "I will be able to provide whatever the tool asks for in return"
    clarifying-question flow, satisfied without any client-side JS state."""
    buttons = []
    for key, title, module in candidates:
        buttons.append(f"""
          <form method="post" action="/generate" style="margin:0;">
            <input type="hidden" name="request" value="{html.escape(request_text)}">
            <input type="hidden" name="template_key" value="{html.escape(key)}">
            <button type="submit" class="choice">
              <span class="title">{html.escape(title)}</span><br>
              <span class="module">{html.escape(module)}</span>
            </button>
          </form>
        """)
    return _page(f"""
      <h1>Which one did you mean?</h1>
      <p class="lead">Your request could match more than one report. Pick the one you'd like:</p>
      <div class="choices">{''.join(buttons)}</div>
      <button type="button" class="secondary" onclick="location.href='/'">Start over</button>
    """)


# Internal warning text -> a plain-English note a customer can actually use.
# Matched by substring against src/compiler.py's own warning strings, so a
# wording change there just falls through to the generic fallback below
# rather than crashing.
_NOTE_RULES = [
    ("not fabricating", "This report shows a net balance rather than a separate debit/credit split — "
                          "a verified breakdown isn't available for that yet."),
    ("not yet wired", "Filtering to a specific period or date range isn't automated in this tool yet — "
                        "contact support if you need the report limited to one."),
    ("No recognized measure", "We didn't spot a specific measure in your request, so we've used the "
                                "overall balance."),
    ("too thin to compile", "We didn't spot much detail in your request, so we've built a general "
                              "version of the report. Mention a department, cost centre, or time period "
                              "for something more specific."),
]


def friendly_notes(warnings):
    notes = []
    for w in warnings:
        for needle, note in _NOTE_RULES:
            if needle in w:
                if note not in notes:
                    notes.append(note)
                break
    return notes


# A confidence report's "overall" (src/confidence.py) -> a plain-English
# caveat. Derived generically from that one field rather than hand-writing
# a caveat per template, so a template's schema confidence changing (e.g.
# once corpus/confirmed_patterns/ grows) is reflected here automatically.
_CONFIDENCE_NOTES = {
    "mixed": "Part of this report relies on a table this tool hasn't independently confirmed against a "
             "live system yet — it should work, but treat it as worth double-checking once imported.",
    "unconfirmed": "This report relies on tables this tool hasn't independently confirmed against a live "
                   "system yet — treat it as a draft to verify, not a finished report.",
}


def _confidence_note(confidence):
    if not confidence:
        return None
    return _CONFIDENCE_NOTES.get(confidence.get("overall"))


def render_result(request_text, template_key=None):
    request_text = (request_text or "").strip()
    if not request_text:
        return render_form(error="Please describe the report you'd like first.")

    result = compile_request(request_text, chosen_template_key=template_key or None)
    status = result["status"]

    if status == "ambiguous":
        return render_ambiguous(request_text, result["candidates"])

    if status == "unsupported":
        return render_form(error=result["message"], previous_text=request_text)

    if status == "invalid":
        # A customer never sees raw validator output — that's for the
        # people maintaining this tool (see tests/, docs/FAILURE_MODES.md).
        return render_form(
            error="We couldn't put together a reliable report from that description. "
                  "Try rephrasing it, or contact support for help.",
            previous_text=request_text,
        )

    # status == "ok"
    notes = friendly_notes(result.get("warnings", []))
    confidence_note = _confidence_note(result.get("confidence"))
    if confidence_note:
        notes.append(confidence_note)
    notes_html = ""
    if notes:
        items = "".join(f"<li>{html.escape(n)}</li>" for n in notes)
        notes_html = f'<div class="notes"><strong>A few notes about this report:</strong><ul>{items}</ul></div>'

    escaped_env = html.escape(result["env"])
    return _page(f"""
      <h1>Your report is ready</h1>
      <div class="steps">
        <strong>Next steps:</strong> copy the text below, then in iplicit go to
        <strong>Enquiries &rsaquo; &#8942; &rsaquo; Import from clipboard</strong>, paste it,
        tick an analytic group, and click <strong>Create</strong>.
      </div>
      {notes_html}
      <textarea id="output" rows="14" readonly onclick="this.select()">{escaped_env}</textarea>
      <div>
        <button type="button" onclick="copyOutput()">Copy to clipboard</button>
        <button type="button" class="secondary" onclick="location.href='/'">Describe another report</button>
      </div>
      <span id="copied" style="display:none; color: #15803d; margin-left: 10px;">Copied!</span>
      <script>
        function copyOutput() {{
          const el = document.getElementById('output');
          el.select();
          document.execCommand('copy');
          const c = document.getElementById('copied');
          c.style.display = 'inline';
          setTimeout(() => c.style.display = 'none', 1500);
        }}
      </script>
    """)


class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/":
            self._send_html(render_form())
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        if self.path == "/generate":
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length).decode("utf-8")
            fields = parse_qs(body)
            request_text = fields.get("request", [""])[0]
            template_key = fields.get("template_key", [""])[0]
            self._send_html(render_result(request_text, template_key=template_key))
        else:
            self.send_response(404)
            self.end_headers()

    def _send_html(self, body):
        encoded = body.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def log_message(self, format, *args):
        pass  # keep the console quiet — this is meant to be handed to a customer/support agent


class ReusableTCPServer(socketserver.TCPServer):
    # Without this, restarting the tool shortly after stopping it fails
    # with "Address already in use" while the OS still holds the old
    # socket in TIME_WAIT — surprising behavior for something meant to be
    # started and stopped casually.
    allow_reuse_address = True


def main():
    with ReusableTCPServer(("", PORT), Handler) as httpd:
        print(f"Report builder running at http://localhost:{PORT}  (Ctrl+C to stop)")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nStopped.")


if __name__ == "__main__":
    main()
