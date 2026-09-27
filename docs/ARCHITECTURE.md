# Architecture

## The problem this solves

An iplicit enquiry is stored as four coupled artifacts — `QueryXml`, `PropMetaJson`, one `EnquiryLayouts` entry per tab, and `RequiredPermissions` — packaged into a base64-in-JSON clipboard envelope for import/export. None of it is documented publicly. Getting it wrong produces no error message: a missing permission just leaves the Create button disabled; a bad row-grouping/hierarchy combination just returns an empty grid. The only way to learn the format was empirical: read real definitions, and provoke real failures.

## How the knowledge was originally obtained

A prior session with browser access (Claude in Chrome) used iplicit's own enquiry-preview feature against itself: the preview screen sends a `queryXml` payload to an endpoint and renders whatever comes back. By hooking `XMLHttpRequest` in the page (see the snippet in `docs/IPLICIT_ENQUIRY_MASTER_SKILL.md` §9) and substituting arbitrary SQL for that payload, it became possible to run `SELECT * FROM dbo.enquiry` / `dbo.enquiry_layout` directly — reading the QueryXml/PropMetaJson/layout of all 640 enquiry definitions already in the sandbox tenant, rather than clicking through each one in the Enquiry Designer. That one-time exploration is where `docs/IPLICIT_ENQUIRY_MASTER_SKILL.md`'s schema and grammar knowledge comes from.

This repo doesn't depend on having that access again for day-to-day use — the generator encodes what was learned as code — but getting a **complete** raw corpus (every one of the 640 definitions' actual SQL, not just the distilled patterns) still needs it. See `docs/ROADMAP.md`.

## Pipeline

```
plain-English request
        │
        ├──▶ src/compiler.py's compile_request() — the customer-facing
        │     entry point (tools/enquiry_builder_app.py). Two paths, tried
        │     in order:
        │       1. src/templates.py matches the request against 14 fixed,
        │          already-confirmed report shapes spanning all 7 modules
        │          (GL/AR/AP/Sales/Purchasing/Bank/Budgets) — each one is
        │          literally one of src/build_library.py's own
        │          enquiry_NN_*() functions, so there's exactly one place
        │          that knows how to build, say, an aged-debtors report.
        │          A clear winner builds that report; a tie returns
        │          "ambiguous" so the caller can ask which one was meant.
        │       2. No template matches → src/nl_parser.py (rule-based
        │          keyword match, not NLP) builds a src/spec.py EnquirySpec,
        │          then src/compiler.py's compile_spec() turns it into the
        │          same enqgen.py calls a human would write by hand — but
        │          only for GL, and only a flexible dimension/measure
        │          combination that doesn't match a fixed template (e.g.
        │          "balance by fund and location"). See "Design choices"
        │          below for why GL alone gets this flexible path.
        │     Anything neither path covers returns "unsupported" with a
        │     plain-English reason — never a guess dressed up as an answer.
        │
        ▼  (everything else: a human writes the enqgen.py calls directly)
src/enqgen.py  (param / src / fld / multi_filter / query_xml / meta / layout / build)
        │  imports from:
        │    src/schema.py       — known tables/views/columns, confirmed vs. inferred
        │    src/joins.py        — reusable join-chain builders
        │    src/layouts.py      — column-metadata & grid/pivot layout helpers
        │    src/permissions.py  — RequiredPermissions GUID lookup table
        ▼
DbEnquiry export JSON  (base64 envelope)
        │
        ▼
src/enquiry_parser.py   ── decodes the envelope into src/ir.py's typed
        │                  Enquiry/Select/Source/Field/Param/Layout dataclasses
        ▼
src/enquiry_validator.py   ── runs three check layers against that IR:
        │                     structural (docs/FAILURE_MODES.md), cross-
        │                     reference (docs/DISCOVERED_FAILURE_MODES.md
        │                     #1-3 — does every Source/Param/layout-field/
        │                     PropMeta name actually resolve to something
        │                     declared), and adversarial (ibid. #4-8 —
        │                     duplicate Field/Source/Param names, malformed
        │                     permission GUIDs, an under-specified
        │                     hierarchy rule — added by attacking enqgen.py's
        │                     own output rather than a bug already seen)
        ▼
generated/<module>/*.json   (only if it passes)
        │
        ├──▶ src/confidence.py + src/enquiry_doctor.py   — one-file PASS/WARN/FAIL
        │     report: the validator's checks bucketed by section, plus a
        │     schema-confidence read (which tables used are confirmed vs.
        │     inferred, via src/schema.py)
        │
        ├──▶ src/enquiry_diff.py   — semantic (not textual) comparison of two
        │     enquiries' params/sources/fields/layouts/permissions, via the
        │     same IR
        ▼
Enquiries ▸ ⋮ ▸ Import from clipboard ▸ Apply ▸ (tick analytic group) ▸ Create
        (a human click — this repo never creates anything inside a live tenant itself)
```

`src/ir.py` is the formal intermediate representation (docs/PROJECT_AUDIT.md #3, #9): typed dataclasses instead of the plain dicts/ElementTree objects `enqgen.py` and the original `enquiry_parser.py` passed around by convention. It exists specifically so relationships like "this Field's Source must name a declared Source" have a name and a place to live, rather than being re-discovered by reading strings each time a new check is added. `src/enquiry_parser.py` builds an `Enquiry` from any export — real (something dropped into `corpus/real_enquiries/`) or generated — so a real example and a generated one can be compared through `src/enquiry_diff.py` on equal footing.

## Why the validator can't be the whole story

`enquiry_validator.py` checks the *shape* of an enquiry — the structural layer (does every optional filter tolerate an empty parameter, is there a permission, does an amount column's currency member actually resolve, does a hierarchy conflict with its row grouping), the cross-reference layer added in the engine-hardening pass (does every Field's Source, every filter's `@Param`, every layout field reference, and every PropMeta entry actually name something declared elsewhere in the same enquiry), and the adversarial layer added in the pass after that (are those same names actually *unique* within their scope, and is a permission id actually GUID-shaped) — none of it found by trial and error, all of it found by treating the generator's own output as an attack surface. All of that is derivable from the JSON alone. What it cannot check is whether `[dbo].[bank_transaction]` actually has a `currency` column, or whether `dac_doc_base` has its own `last_modified_by` — that requires a live database. `src/confidence.py` tracks which tables an enquiry depends on are confirmed vs. inferred (surfaced via `enquiry_doctor.py`), but "inferred" is a flag on an assumption, not a substitute for checking it. The repo is explicit (in `generated/INDEX.md`, `docs/SCHEMA.md`, and `corpus/unknown_patterns/`) about which enquiries carry that kind of unconfirmed assumption. See `docs/PROJECT_AUDIT.md` §0 for what this project currently does and does not have evidence for.

## Design choices worth knowing about

- **Stdlib only.** No dependencies to install, so the generator, validator, doctor, and diff tool all run anywhere Python 3 runs, including headless/CI contexts with no access to iplicit itself.
- **Generator produces text, never calls an API.** Nothing in `src/` talks to a live iplicit tenant. Import and Create are always a human action, by design — see `CLAUDE.md`.
- **The split between `schema.py` / `joins.py` / `layouts.py` / `permissions.py`** exists so that updating one axis (e.g. a newly confirmed table) doesn't require touching the query-building logic in `enqgen.py`, and so `enquiry_parser.py`/`ir.py` can share the same vocabulary when decoding real examples.
- **`ir.py` is a read/represent layer, not a generator rewrite.** `enqgen.py` still builds QueryXml directly with string templates — that code is simple and already battle-tested across 14 real builds. The IR exists so *validation and tooling* (the validator's cross-reference layer, the doctor, the diff tool) have typed data to work with, without forcing a generator rewrite that would risk the working 14.
- **The natural-language front end compiles *into* `enqgen.py` calls (or `build_library.py` functions), never around them.** Whether `compile_request()` takes the template path or the flexible-GL path, the result is the same `(params, selects, propmeta, layouts, permissions)` shape a hand-written `src/build_library.py` entry builds, handed to the same `enqgen.build()` — so a compiled enquiry goes through exactly the same `enquiry_validator.py`/`enquiry_doctor.py` gate as a hand-written one, with no separate, weaker code path.
- **Fixed templates for modules without GL's confirmed flexibility, not a second flexible compiler per module.** GL has a confirmed, general-purpose dimension mechanism (`crv_gl`), so `compile_spec()` can assemble *any* combination of confirmed dimensions freely. AR/AP/Sales/Purchasing/Bank/Budgets don't have an equivalent — each of this repo's 14 confirmed examples in those modules is its own bespoke join/shape, hand-verified once. Rather than fabricate a flexible query language for those modules (which would mean guessing at column/table combinations nobody has confirmed — exactly what `CLAUDE.md`'s "one rule that matters most" forbids), `src/templates.py` treats those 14 examples as a fixed catalog: a request either matches one of them closely enough to build with confidence, or it doesn't and says so. Widening a module's coverage means confirming a new report shape against a real tenant and adding it as the 15th `build_library.py` function — never stretching an existing one to guess at a shape nobody's built.
- **Ambiguity is surfaced, not resolved by guessing.** When a request scores an equal-highest match against more than one template (e.g. "purchase invoices" alone could plausibly mean the by-supplier-by-month report or the overdue-invoices report), `compile_request()` returns `"status": "ambiguous"` with every tied candidate rather than picking one. `tools/enquiry_builder_app.py` turns that into a one-click picker; a caller with no UI can just ask the person directly.
- **Mutation testing over fuzzing.** `tests/test_mutations.py` mutates real, already-valid `generated/*/*.json` files one meaningful edit at a time, rather than generating random XML/JSON — the goal is finding validator blind spots on realistic near-misses, not crash-testing the parser.
