# corpus/unknown_patterns/

Every place this repo currently relies on a guess — a table, column, or
behaviour that follows a documented naming convention but has **not** been
checked against a live iplicit tenant. This folder exists so those guesses
are visible and trackable, instead of silently shipped as fact inside
`generated/` output.

**Currently empty of dedicated files** — today's unconfirmed items are
tracked inline (flagged in `docs/SCHEMA.md`, `generated/INDEX.md`, and
`docs/ROADMAP.md` item 2) rather than as one file per item. As the list
grows, or as any one item needs its own worked notes, give it a file here.

## What belongs here

One short file per open question, e.g. `dac_doc_base-last-modified.md`:
what's assumed, why (naming convention, analogy with a confirmed sibling
table), and which `generated/` enquiry depends on it. The known open items
right now, cross-referenced from `docs/SCHEMA.md` and `docs/ROADMAP.md`:

- Does `dac_doc_base` have its own `last_modified`/`last_modified_by`?
- `dbo.GetAgedDebt` / `GetAgedCreditors` — real output column names.
- `bank_transaction` — full column list, especially currency.
- `budget2` / `budget2_key` / `budget2_value` — full column list.
- A real P&L tree id (`generated/gl/04_pl_by_month.json` uses a placeholder).
- A confirmed `AP.Enquiry` permission GUID (currently reusing `AR.Enquiry`).

## What doesn't

- Anything already verified — move it to `corpus/confirmed_patterns/`
  instead, and update `docs/SCHEMA.md` / `src/schema.py`.

## Rule

Per `CLAUDE.md`'s "one rule that matters most": never let something land
here quietly and then get treated as fact elsewhere. Every unconfirmed
column referenced in `generated/` must show up in that enquiry's notes in
`generated/INDEX.md`.
