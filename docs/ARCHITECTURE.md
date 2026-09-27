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
        ▼
src/enqgen.py  (param / src / fld / multi_filter / query_xml / meta / layout / build)
        │  imports from:
        │    src/schema.py       — known tables/views/columns
        │    src/joins.py        — reusable join-chain builders
        │    src/layouts.py      — column-metadata & grid/pivot layout helpers
        │    src/permissions.py  — RequiredPermissions GUID lookup table
        ▼
DbEnquiry export JSON  (base64 envelope)
        │
        ▼
src/enquiry_validator.py   ── uses src/enquiry_parser.py to decode the envelope,
        │                     then runs the structural checklist from
        │                     docs/FAILURE_MODES.md
        ▼
generated/<module>/*.json   (only if it passes)
        │
        ▼
Enquiries ▸ ⋮ ▸ Import from clipboard ▸ Apply ▸ (tick analytic group) ▸ Create
        (a human click — this repo never creates anything inside a live tenant itself)
```

`src/enquiry_parser.py` is also the reverse direction: given a real enquiry's export (something dropped into `corpus/real_enquiries/`), it decodes the envelope back into the same structured shape the generator builds from — params, sources, fields, layouts, permissions — so a real example and a generated one can be diffed field-for-field.

## Why the validator can't be the whole story

`enquiry_validator.py` checks the *shape* of an enquiry: does every optional filter tolerate an empty parameter, is there a permission, does an amount column's currency member actually resolve, does a hierarchy conflict with its row grouping. All of that is derivable from the JSON alone. What it cannot check is whether `[dbo].[bank_transaction]` actually has a `currency` column, or whether `dac_doc_base` has its own `last_modified_by` — that requires a live database. The repo is explicit (in `generated/*/INDEX.md` and `corpus/unknown_patterns/`) about which enquiries carry that kind of unconfirmed assumption.

## Design choices worth knowing about

- **Stdlib only.** No dependencies to install, so the generator and validator run anywhere Python 3 runs, including headless/CI contexts with no access to iplicit itself.
- **Generator produces text, never calls an API.** Nothing in `src/` talks to a live iplicit tenant. Import and Create are always a human action, by design — see `CLAUDE.md`.
- **The split between `schema.py` / `joins.py` / `layouts.py` / `permissions.py`** exists so that updating one axis (e.g. a newly confirmed table) doesn't require touching the query-building logic in `enqgen.py`, and so `enquiry_parser.py` can share the same vocabulary when decoding real examples.
