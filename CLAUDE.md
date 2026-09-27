# CLAUDE.md — instructions for working in this repo

This repo generates iplicit ERP enquiries (custom reports). Read this before making changes.

## Before doing anything else

- Read `docs/IPLICIT_ENQUIRY_QUICK_SKILL.md` first (short). Read `docs/IPLICIT_ENQUIRY_MASTER_SKILL.md` when you need the full grammar, schema, or generator source.
- If asked to build a new enquiry: don't hand-write QueryXml/PropMetaJson/layout JSON. Use `src/enqgen.py`'s functions (`param`, `src`, `fld`, `multi_filter`, `query_xml`, `meta`, `layout`, `build`) the way `src/build_library.py` does. Save the script that builds it, not just the output — so it can be regenerated and diffed later.
- Every new enquiry must pass `python3 src/enquiry_validator.py <file>.json` before being added to `generated/`. If it doesn't pass, fix the generator script, not the output JSON by hand.
- Put a new enquiry's build script and its output in the right module folder under `generated/<module>/` (`gl`, `ar`, `ap`, `sales`, `purchasing`, `bank`, `budgets`). If none fits, ask rather than guessing — don't invent an eighth folder without saying so.
- Draft/unsure work goes in `experiments/`, not `generated/`. Only promote it once validated and, ideally, confirmed against a live tenant.

## The one rule that matters most

**This repo's validator cannot confirm a column or table actually exists.** It checks structure (filter idioms, permissions, layout conflicts), not your live schema. Anything you write that references a table/column not already in `docs/SCHEMA.md` or `corpus/confirmed_patterns/` must be flagged as unconfirmed in the enquiry's notes/docstring — don't present a guess as a fact. When in doubt, say what you don't know rather than filling the gap with something plausible-sounding.

## Known failure modes — check `docs/FAILURE_MODES.md` before debugging from scratch

The two costliest mistakes so far, both discovered by trial and error against a live sandbox, not from documentation:
1. A saved row `hierarchy` (a chart-of-accounts/BS/PL tree) combined with a multi-level `groupRows` returns **no data**, with no error. Don't combine them unless the extra level is genuinely nested inside that tree.
2. `dac_gl.last_modified_by` is the GL posting's audit stamp; `account.last_modified_by` is the chart-of-accounts record's. They are not interchangeable — ask which one is meant if a request says "last modified" without saying which entity.

## Testing

```bash
python3 -m unittest discover -s tests -v
```

Add a regression test to `tests/test_regressions.py` for any new failure mode you confirm — that file exists specifically so a mistake is caught by CI the next time, not rediscovered by hand.

## Corpus discipline

Don't invent "real examples." If you don't have a live enquiry's actual QueryXml in front of you, say the pattern is *inferred from documented conventions*, not confirmed. `corpus/confirmed_patterns/` vs `corpus/unknown_patterns/` exists to keep that distinction visible — respect it when adding to either.

## Attribution

This repo builds on iplicit-enquiry-builder, a Claude skill reverse-engineered from 640 real enquiry definitions via SQL injected through the enquiry preview's `queryXml` endpoint (see `docs/ARCHITECTURE.md`). If you gain live database/browser access to an iplicit tenant again, that's still the fastest way to pull a full raw corpus — two `SELECT * FROM dbo.enquiry` / `dbo.enquiry_layout` queries, not a UI walkthrough.
