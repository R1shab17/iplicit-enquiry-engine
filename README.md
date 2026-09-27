# iplicit Enquiry Engine

Generate, validate, and maintain custom [iplicit](https://www.iplicit.com/) ERP enquiries (reports) from a plain-English request — without hand-writing the `QueryXml`/`PropMetaJson`/layout JSON iplicit's Enquiry Designer expects.

This exists because iplicit enquiries are a real but undocumented format: four JSON/XML blobs glued together, imported via a clipboard-paste dialog, with failure modes (a disabled Create button, a pivot that silently returns no rows) that give no error message. This repo turns what was learned by reverse-engineering 640 real enquiry definitions in a live sandbox into versioned code, docs, and tests, instead of tribal knowledge re-derived every time.

## What's here

| Path | What it is |
|---|---|
| `docs/` | The reference material — schema, grammar, known and discovered failure modes, a project audit, a roadmap, and the two skill documents (`IPLICIT_ENQUIRY_MASTER_SKILL.md` full, `IPLICIT_ENQUIRY_QUICK_SKILL.md` condensed, meant to be pasted into a Claude Project's instructions). |
| `src/` | The generator (`enqgen.py` + its `schema.py`/`joins.py`/`layouts.py`/`permissions.py` building blocks), a typed intermediate representation (`ir.py`), a parser that reads an export back into that IR (`enquiry_parser.py`), the structural + cross-reference validator (`enquiry_validator.py`), a schema-confidence report (`confidence.py`), and two CLI tools built on all of the above: `enquiry_doctor.py` (one-file diagnostic report) and `enquiry_diff.py` (semantic comparison of two enquiries). |
| `tests/` | 122 unit tests for every module above, fixtures (one clean, eleven deliberately broken — one per known/discovered failure mode), a mutation-testing harness that applies each of those same mutations to every real `generated/` enquiry, and regression tests for the real bugs this project has hit. |
| `corpus/` | Where real enquiry SQL goes to keep improving this. `real_enquiries/` is empty on purpose — see below. `confirmed_patterns/` and `unknown_patterns/` track what's actually been verified against a live iplicit database versus what's inferred from documented conventions. |
| `generated/` | Ready-to-import enquiry exports, one folder per iplicit module (`gl`, `ar`, `ap`, `sales`, `purchasing`, `bank`, `budgets`). |
| `experiments/` | Scratch space for enquiries being drafted/tested — promote to `generated/` once validated. |

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

# Run the test suite (122 tests)
python3 -m unittest discover -s tests -v
```

To build a new enquiry: write a short Python script using the functions in `src/enqgen.py` (see `src/build_library.py` for 14 worked examples spanning list views, pivots, unions, and table-valued-function sources), validate it, then in iplicit go to **Enquiries > ⋮ > Import from clipboard**, paste the file's contents, tick an analytic group, and click **Create**.

## The honesty policy

Every generated enquiry in `generated/` has been checked by `enquiry_validator.py`, which runs two kinds of check, neither of which is a live database:

- **Structural**: is the XML well-formed, does every optional filter tolerate an empty parameter, is there a permission, does an amount column's currency member resolve, does a hierarchy conflict with its row grouping.
- **Cross-reference** (`src/ir.py`): does every name different parts of the enquiry use to refer to each other actually resolve — a Field's Source, a filter's `@Param`, a layout's field references, a PropMeta entry. These checks found and fixed three real bugs already sitting in this repo's own `generated/` output; see `docs/DISCOVERED_FAILURE_MODES.md`.

What the validator **cannot** do is confirm that a column you referenced actually exists on a table you haven't queried live — `src/confidence.py` (surfaced via `enquiry_doctor.py`'s CONFIDENCE/RISKS sections) tracks which tables an enquiry depends on are confirmed vs. inferred, but "inferred" still means "not independently checked." Where an enquiry leans on one, that's called out explicitly in `generated/INDEX.md`, `docs/SCHEMA.md`, and `corpus/unknown_patterns/`. Treat those as drafts to verify, not finished reports. See `docs/PROJECT_AUDIT.md` for the full picture of what is and isn't actually possible here without live tenant access.

## How this gets better over time

1. Build/find a real, working enquiry in your iplicit tenant.
2. Export it to clipboard, save the JSON under `corpus/real_enquiries/`.
3. Diff what it does against `docs/IPLICIT_ENQUIRY_MASTER_SKILL.md` — anything new (a table, a join, an idiom) moves into `corpus/confirmed_patterns/` and gets folded into the master skill and `src/schema.py`.
4. Anything the new example contradicts in `corpus/unknown_patterns/` gets resolved and moved out.

See `docs/ROADMAP.md` for what's not done yet (the biggest one: nothing in this repo has been run against a live iplicit database within this repo's own tooling — see `docs/ROADMAP.md` for how that loop should close).
