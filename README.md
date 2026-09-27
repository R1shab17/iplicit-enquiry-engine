# iplicit Enquiry Engine

Generate, validate, and maintain custom [iplicit](https://www.iplicit.com/) ERP enquiries (reports) from a plain-English request — without hand-writing the `QueryXml`/`PropMetaJson`/layout JSON iplicit's Enquiry Designer expects.

This exists because iplicit enquiries are a real but undocumented format: four JSON/XML blobs glued together, imported via a clipboard-paste dialog, with failure modes (a disabled Create button, a pivot that silently returns no rows) that give no error message. This repo turns what was learned by reverse-engineering 640 real enquiry definitions in a live sandbox into versioned code, docs, and tests, instead of tribal knowledge re-derived every time.

## What's here

| Path | What it is |
|---|---|
| `docs/` | The reference material — schema, grammar, known failure modes, and the two skill documents (`IPLICIT_ENQUIRY_MASTER_SKILL.md` full, `IPLICIT_ENQUIRY_QUICK_SKILL.md` condensed, meant to be pasted into a Claude Project's instructions). |
| `src/` | The generator (`enqgen.py` + its `schema.py`/`joins.py`/`layouts.py`/`permissions.py` building blocks), a parser that reads an export back into structured data (`enquiry_parser.py`), and the validator (`enquiry_validator.py`). |
| `tests/` | Unit tests for the generator, validator, layouts, and permissions, plus regression tests for the two real bugs this project has already hit in production use. |
| `corpus/` | Where real enquiry SQL goes to keep improving this. `real_enquiries/` is empty on purpose — see below. `confirmed_patterns/` and `unknown_patterns/` track what's actually been verified against a live iplicit database versus what's inferred from documented conventions. |
| `generated/` | Ready-to-import enquiry exports, one folder per iplicit module (`gl`, `ar`, `ap`, `sales`, `purchasing`, `bank`, `budgets`). |
| `experiments/` | Scratch space for enquiries being drafted/tested — promote to `generated/` once validated. |

## Quick start

Requires only the Python standard library — nothing to install.

```bash
# Generate the library of example enquiries into generated/
python3 src/build_library.py

# Validate every generated enquiry against the known checklist
python3 src/enquiry_validator.py generated/**/*.json

# Run the test suite
python3 -m unittest discover -s tests -v
```

To build a new enquiry: write a short Python script using the functions in `src/enqgen.py` (see `src/build_library.py` for 14 worked examples spanning list views, pivots, unions, and table-valued-function sources), validate it, then in iplicit go to **Enquiries > ⋮ > Import from clipboard**, paste the file's contents, tick an analytic group, and click **Create**.

## The honesty policy

Every generated enquiry in `generated/` has been checked by `enquiry_validator.py` — a structural linter, not a live database. It catches the mistakes that are *knowable from the JSON alone* (a filter that excludes everything when its param is empty, a permission list that leaves Create disabled, a pivot hierarchy that conflicts with its row grouping). It **cannot** confirm that a column you referenced actually exists on a table you haven't queried live. Where an enquiry leans on an unconfirmed column or table, that's called out explicitly in `generated/<module>/../INDEX.md` and in `corpus/unknown_patterns/`. Treat those as drafts to verify, not finished reports.

## How this gets better over time

1. Build/find a real, working enquiry in your iplicit tenant.
2. Export it to clipboard, save the JSON under `corpus/real_enquiries/`.
3. Diff what it does against `docs/IPLICIT_ENQUIRY_MASTER_SKILL.md` — anything new (a table, a join, an idiom) moves into `corpus/confirmed_patterns/` and gets folded into the master skill and `src/schema.py`.
4. Anything the new example contradicts in `corpus/unknown_patterns/` gets resolved and moved out.

See `docs/ROADMAP.md` for what's not done yet (the biggest one: nothing in this repo has been run against a live iplicit database within this repo's own tooling — see `docs/ROADMAP.md` for how that loop should close).
