# iplicit Enquiry Engine

Generate, validate, and maintain custom [iplicit](https://www.iplicit.com/) ERP enquiries (reports) from a plain-English request — without hand-writing the `QueryXml`/`PropMetaJson`/layout JSON iplicit's Enquiry Designer expects.

This exists because iplicit enquiries are a real but undocumented format: four JSON/XML blobs glued together, imported via a clipboard-paste dialog, with failure modes (a disabled Create button, a pivot that silently returns no rows) that give no error message. This repo turns what was learned by reverse-engineering 640 real enquiry definitions in a live sandbox into versioned code, docs, and tests, instead of tribal knowledge re-derived every time.

## What's here

| Path | What it is |
|---|---|
| `docs/` | The reference material — schema, grammar, known and discovered failure modes, a project audit, a roadmap, and the two skill documents (`IPLICIT_ENQUIRY_MASTER_SKILL.md` full, `IPLICIT_ENQUIRY_QUICK_SKILL.md` condensed, meant to be pasted into a Claude Project's instructions). |
| `src/` | The generator (`enqgen.py` + its `schema.py`/`joins.py`/`layouts.py`/`permissions.py` building blocks), a typed intermediate representation (`ir.py`), a parser that reads an export back into that IR (`enquiry_parser.py`), the structural + cross-reference + adversarial validator (`enquiry_validator.py`), a schema-confidence report (`confidence.py`), two CLI tools built on all of the above (`enquiry_doctor.py` one-file diagnostic report, `enquiry_diff.py` semantic comparison of two enquiries), the library of 14 confirmed report shapes as reusable functions (`build_library.py`), a keyword-matched catalog over that library (`templates.py`), and a natural-language front end (`spec.py`/`nl_parser.py`/`compiler.py`) whose `compile_request()` covers all 7 modules `generated/` represents — see `docs/ROADMAP.md` item 10. |
| `tests/` | Unit tests for every module above (including `tools/enquiry_builder_app.py`), fixtures (one clean, sixteen deliberately broken — one per known/discovered/adversarial failure mode), a mutation-testing harness that applies each of those same mutations to every real `generated/` enquiry, and regression tests for the real bugs this project has hit. Run `python3 -m unittest discover -s tests -v` for the current count. |
| `corpus/` | Where real enquiry SQL goes to keep improving this. `real_enquiries/` is empty on purpose — see below. `confirmed_patterns/` and `unknown_patterns/` track what's actually been verified against a live iplicit database versus what's inferred from documented conventions. |
| `generated/` | Ready-to-import enquiry exports, one folder per iplicit module (`gl`, `ar`, `ap`, `sales`, `purchasing`, `bank`, `budgets`). |
| `experiments/` | Scratch space for enquiries being drafted/tested — promote to `generated/` once validated. |
| `tools/` | `enquiry_builder_app.py` — a customer-facing, stdlib-only local web app: describe a report in plain English (any of the 7 modules above), get back the ready-to-import file, with a one-click clarifying question when a request is genuinely ambiguous between two report types. A thin front end over `src/compiler.py`'s `compile_request()`; adds no report-building logic of its own. |

## Quick start

Requires only the Python standard library — nothing to install.

```bash
# Generate the library of example enquiries into generated/<module>/
python3 src/build_library.py

# Validate every generated enquiry against the full checklist
# (structural + cross-reference — see docs/FAILURE_MODES.md and docs/DISCOVERED_FAILURE_MODES.md)
python3 src/enquiry_validator.py generated/*/*.json

# One-file diagnostic report: STATUS + a section per concern + schema confidence + risks
python3 src/enquiry_doctor.py generated/bank/10_bank_transactions_by_account.json

# Semantic diff of two enquiries (field/join/param/layout/permission level, not textual)
python3 src/enquiry_diff.py generated/ar/05_aged_debtors_by_customer.json generated/ap/07_aged_creditors_by_supplier.json

# Run the test suite
python3 -m unittest discover -s tests -v
```

To build a new enquiry: write a short Python script using the functions in `src/enqgen.py` (see `src/build_library.py` for 14 worked examples spanning list views, pivots, unions, and table-valued-function sources), validate it, then in iplicit go to **Enquiries > ⋮ > Import from clipboard**, paste the file's contents, tick an analytic group, and click **Create**.

For a plain-English request, there's also a compiler covering all 7 modules `generated/` represents (`src/spec.py`/`src/nl_parser.py`/`src/templates.py`/`src/compiler.py` — rule-based keyword matching, not NLP; see `docs/ROADMAP.md` item 10). `compile_request()` is the entry point: it matches the request against 14 confirmed report shapes first, falls back to a flexible General-Ledger-only compiler for a custom dimension combination that matches none of them, and returns a clarifying question instead of guessing when a request ties between two report types:

```python
import sys; sys.path.insert(0, "src")
from compiler import compile_request

result = compile_request("Aged debtors by customer, who owes us")
if result["status"] == "ok":
    env = result["env"]          # still run this through enquiry_validator.py before trusting it
    print(result["warnings"], result["confidence"])
elif result["status"] == "ambiguous":
    print("Which one did you mean?", result["candidates"])   # [(key, title, module), ...]
    # resubmit: compile_request(text, chosen_template_key=key)
else:  # "unsupported" (or "invalid", which should never happen for a template match)
    print(result["message"])
```

There's also a customer-facing web front end over the same pipeline — `tools/enquiry_builder_app.py`, stdlib-only, no install:

```bash
python3 tools/enquiry_builder_app.py
# open http://localhost:8765 — type a request, click Generate, get back the file
```

It's deliberately a thin skin: it hides Python/validator internals from the person using it (no stack traces, no jargon), translates warnings and schema-confidence caveats into plain-English notes, offers a one-click picker when a request is genuinely ambiguous between two report types, and — if a request matches nothing this repo can build or fails validation — says so plainly and points to support instead of handing over a guess. See its own docstring and `tests/test_enquiry_builder_app.py` for exactly what it does and doesn't do.

## The honesty policy

Every generated enquiry in `generated/` has been checked by `enquiry_validator.py`, which runs two kinds of check, neither of which is a live database:

- **Structural**: is the XML well-formed, does every optional filter tolerate an empty parameter, is there a permission (and does it look like a real GUID), does an amount column's currency member resolve, does a hierarchy conflict with its row grouping (now checked both for *too many* groupRows levels and for *none at all*).
- **Cross-reference** (`src/ir.py`): does every name different parts of the enquiry use to refer to each other actually resolve — a Field's Source, a filter's `@Param`, a layout's field references, a PropMeta entry, and (adversarial pass) is every Field/Source/Param name actually unique within its scope. The first four found and fixed three real bugs already sitting in this repo's own `generated/` output; the duplicate-name and permission-format checks were added by attacking the generator's own output rather than from an observed bug. See `docs/DISCOVERED_FAILURE_MODES.md`.

What the validator **cannot** do is confirm that a column you referenced actually exists on a table you haven't queried live — `src/confidence.py` (surfaced via `enquiry_doctor.py`'s CONFIDENCE/RISKS sections) tracks which tables an enquiry depends on are confirmed vs. inferred, but "inferred" still means "not independently checked." Where an enquiry leans on one, that's called out explicitly in `generated/INDEX.md`, `docs/SCHEMA.md`, and `corpus/unknown_patterns/`. Treat those as drafts to verify, not finished reports. See `docs/PROJECT_AUDIT.md` for the full picture of what is and isn't actually possible here without live tenant access.

## How this gets better over time

1. Build/find a real, working enquiry in your iplicit tenant.
2. Export it to clipboard, save the JSON under `corpus/real_enquiries/`.
3. Diff what it does against `docs/IPLICIT_ENQUIRY_MASTER_SKILL.md` — anything new (a table, a join, an idiom) moves into `corpus/confirmed_patterns/` and gets folded into the master skill and `src/schema.py`.
4. Anything the new example contradicts in `corpus/unknown_patterns/` gets resolved and moved out.

See `docs/ROADMAP.md` for what's not done yet (the biggest one: nothing in this repo has been run against a live iplicit database within this repo's own tooling — see `docs/ROADMAP.md` for how that loop should close).
