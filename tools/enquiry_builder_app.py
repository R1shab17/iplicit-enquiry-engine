#!/usr/bin/env python3
"""
Report builder — a customer-facing "describe it, get the file" tool.

Run:
    python3 tools/enquiry_builder_app.py

Then open http://localhost:8765 in a browser. Type a plain-English request
for a General Ledger report ("Show me balance by department and cost
centre, monthly"), click Generate, and get back a ready-to-import iplicit
report file — prompt in, file out, no jargon in between.

This is a thin, friendly front end over src/nl_parser.py + src/compiler.py
+ src/enquiry_validator.py. It adds no new report-building logic of its
own, and its scope is exactly theirs: General Ledger requests only (see
docs/ROADMAP.md item 10). Anything it can't build reliably, it says so in
plain language and points to support rather than handing over a guess. It
never talks to a live iplicit tenant — it only produces the file a person
then pastes into iplicit's own Enquiries > Import from clipboard dialog.

Stdlib only, so it runs anywhere Python 3 runs — nothing to install.
"""
import html
import http.server
import os
import socketserver
import sys
import tempfile
from urllib.parse import parse_qs

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from nl_parser import parse as parse_request  # noqa: E402
from compiler import compile_and_build  # noqa: E402
from enquiry_validator import validate_file  # noqa: E402

PORT = int(os.environ.get("ENQUIRY_BUILDER_PORT", "8765"))

EXAMPLES = [
    "Show me balance by department and cost centre",
    "GL report by department, monthly",
    "Balance by fund and location",
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
      <p class="lead">Describe the General Ledger report you'd like, in plain English, and we'll build the file for you.</p>
      {error_html}
      <form method="post" action="/generate">
        <textarea name="request" rows="3" placeholder="e.g. Show me balance by department and cost centre, monthly">{html.escape(previous_text)}</textarea>
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


def render_result(request_text):
    request_text = (request_text or "").strip()
    if not request_text:
        return render_form(error="Please describe the report you'd like first.")

    spec = parse_request(request_text)
    try:
        env, model, warnings = compile_and_build(spec)
    except NotImplementedError:
        return render_form(
            error="This tool currently builds General Ledger reports only. For other report "
                  "types (customers, suppliers, sales, purchasing, bank, budgets), please "
                  "contact support.",
            previous_text=request_text,
        )

    fd, path = tempfile.mkstemp(suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(env)
        issues = validate_file(path)
    finally:
        os.unlink(path)

    if issues:
        # A customer never sees raw validator output — that's for the
        # people maintaining this tool (see tests/, docs/FAILURE_MODES.md).
        return render_form(
            error="We couldn't put together a reliable report from that description. "
                  "Try rephrasing it, or contact support for help.",
            previous_text=request_text,
        )

    notes = friendly_notes(warnings)
    notes_html = ""
    if notes:
        items = "".join(f"<li>{html.escape(n)}</li>" for n in notes)
        notes_html = f'<div class="notes"><strong>A few notes about this report:</strong><ul>{items}</ul></div>'

    escaped_env = html.escape(env)
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
            self._send_html(render_result(request_text))
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
