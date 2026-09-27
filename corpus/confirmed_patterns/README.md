# corpus/confirmed_patterns/

Schema facts and QueryXml/layout idioms that have been independently
verified against a live iplicit tenant — not just inferred from naming
conventions. "Confirmed" in `docs/SCHEMA.md` and `docs/FAILURE_MODES.md`
means the fact should be traceable to something here (or to a specific,
citable moment in `docs/ARCHITECTURE.md`'s history).

**Currently empty of dedicated files** — the confirmations made so far
(`account.last_modified`/`last_modified_by`; the hierarchy+groupRows
failure mode; the two live-tested enquiry fixes) are recorded inline in
`docs/SCHEMA.md`, `docs/FAILURE_MODES.md`, and `tests/test_regressions.py`
rather than as separate files here yet. As confirmations accumulate,
promote them into standalone files in this folder (one per table/pattern)
so they don't only live as prose in the docs.

## What belongs here

- A short note + the exact query or hook output that proved a column/table
  exists (e.g. `dbo.account.result.json` showing `INFORMATION_SCHEMA.COLUMNS`
  output for `account`).
- A worked-and-confirmed QueryXml/layout snippet, with a one-line note on
  what was confirmed and when.

## What doesn't

- Anything not yet checked against a live tenant — that's
  `corpus/unknown_patterns/` instead. Don't move something here just
  because it "seems obviously right."

## Promotion path

`corpus/unknown_patterns/<x>.md` → (confirmed live) → delete from
`unknown_patterns/`, add to `confirmed_patterns/`, and update
`docs/SCHEMA.md` / `src/schema.py` to drop the "inferred" flag.
