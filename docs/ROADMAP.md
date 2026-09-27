# Roadmap

Ordered by what actually reduces risk first, not by what's easiest.

## 1. Close the live-validation loop (highest priority)

Nothing in `generated/` has been run against a real iplicit database from *this repo's* tooling. The validator checks structure; it can't confirm a column exists. The fastest way to close this gap, next time a browser session (Claude in Chrome or similar) has access to an iplicit tenant:

- Run the two corpus-pull queries (`SELECT * FROM dbo.enquiry`, `SELECT * FROM dbo.enquiry_layout`) via the preview-runner hook in `docs/IPLICIT_ENQUIRY_MASTER_SKILL.md` §9 and save the raw results into `corpus/real_enquiries/`.
- For each enquiry currently flagged in `corpus/unknown_patterns/`, run its QueryXml through the same preview-runner override and confirm or fix it.
- Move confirmed patterns into `corpus/confirmed_patterns/` and update `docs/SCHEMA.md` + `src/schema.py` accordingly.

This does not need Playwright or hours of unattended PC time — it's a handful of SQL queries, done once.

## 2. Resolve the specific unconfirmed columns

In priority order (highest-usage enquiries first):
- `dac_doc_base` — does it have its own `last_modified`/`last_modified_by`? (`generated/gl/12_documents_by_user.json`)
- `dbo.GetAgedDebt` / `GetAgedCreditors` — actual output column names. (`generated/ar/05...`, `generated/ap/07...`)
- `bank_transaction` — full column list, especially currency. (`generated/bank/10...`)
- `budget2_value` / `budget2_key` — full column list. (`generated/budgets/13...`)
- A real P&L tree id, to replace the placeholder in `generated/gl/04_pl_by_month.json`.
- A confirmed `AP.Enquiry` permission GUID (currently reusing `AR.Enquiry` in `generated/ap/*`).

## 3. Aged-debt/creditor bucketing

`dbo.GetIntervalRange(@IntervalId, days)` is documented but not yet used anywhere in `generated/`. Add proper 0-30/31-60/61-90/90+ bucketing to the aged debtors/creditors enquiries once the TVF's real output is confirmed (item 1).

## 4. Expand module coverage

Not yet represented in `generated/`: Fixed Assets, VAT/Tax Return figures, Projects (beyond a mention in the master skill), Timesheets, Intercompany. Add once there's a real request or a confirmed pattern to build from — don't pad the library with unconfirmed guesses just for coverage's sake.

## 5. CI

`tests/` runs via stdlib `unittest` and needs nothing installed — wiring it into GitHub Actions (`.github/workflows/test.yml`, plain `python -m unittest discover`) is a small addition whenever this repo gets its first real collaborator or PR.

## 6. Feedback loop discipline

Every time a `generated/` enquiry is imported and confirmed working (or confirmed broken) in a real tenant, that outcome belongs in `corpus/confirmed_patterns/` (or a fix + regression test in `tests/test_regressions.py`), not just in someone's memory. That discipline is the entire reason this repo produces compounding value instead of the same rediscovery every time.
