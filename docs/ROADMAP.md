# Roadmap

Priorities: **P0** = correctness/reliability, **P1** = major capability, **P2** = developer experience, **P3** = experimental. Ordered by what actually reduces risk first within each tier, not by what's easiest. Updated after the engine-hardening pass (`docs/PROJECT_AUDIT.md`) — items marked **done** were completed in that pass; everything else is still open.

## P0 — correctness/reliability

1. **Close the live-validation loop.** Nothing in `generated/` has been run against a real iplicit database from *this repo's own tooling*. The validator (structural + cross-reference) and `src/confidence.py` check everything derivable without one; neither can confirm a column exists. Next time a browser session (Claude in Chrome or similar) has access to an iplicit tenant:
   - Run the two corpus-pull queries (`SELECT * FROM dbo.enquiry`, `SELECT * FROM dbo.enquiry_layout`) via the preview-runner hook in `docs/IPLICIT_ENQUIRY_MASTER_SKILL.md` §9 and save the raw results into `corpus/real_enquiries/`. **This is still the single highest-leverage action available to this project** — see `docs/PROJECT_AUDIT.md` §0: the widely-cited "640 real enquiry definitions" this project was reverse-engineered from were never actually saved into this repo, only their distilled patterns. Nothing below substitutes for having the raw data back.
   - For each enquiry currently flagged in `corpus/unknown_patterns/`, run its QueryXml through the same preview-runner override and confirm or fix it.
   - Move confirmed patterns into `corpus/confirmed_patterns/` and update `docs/SCHEMA.md` + `src/schema.py` accordingly.
   - This does not need Playwright or hours of unattended PC time — it's a handful of SQL queries, done once.

2. ~~**Cross-reference validation** (Source↔Field, Param↔filter/Binding usage, layout↔output fields, PropMeta↔output fields).~~ **Done.** `src/ir.py` + `src/enquiry_validator.py`'s `check_source_references`/`check_param_references`/`check_layout_field_references`/`check_orphan_prop_meta`. Found and fixed 3 real bugs already sitting in `generated/` — see `docs/DISCOVERED_FAILURE_MODES.md`.

3. ~~**Mutation test harness** against the real 14, to find validator blind spots empirically.~~ **Done.** `tests/test_mutations.py` — 10 mutation types × every applicable file in `generated/`, all currently caught. Re-run whenever a new check is added; a mutation that stops tripping its check is itself a regression.

4. Resolve the specific unconfirmed columns, in priority order (highest-usage enquiries first) — unchanged, still blocked on item 1:
   - `dac_doc_base` — does it have its own `last_modified`/`last_modified_by`? (`generated/gl/12_documents_by_user.json`)
   - `dbo.GetAgedDebt` / `GetAgedCreditors` — actual output column names. (`generated/ar/05...`, `generated/ap/07...`)
   - `bank_transaction` — full column list, especially currency, and whether it (or `bank_account`) has a `legal_entity_id` (`generated/bank/10...` had its `LegalEntityId` param removed this pass for exactly this reason — see `docs/DISCOVERED_FAILURE_MODES.md` #1).
   - `budget2_value` / `budget2_key` — full column list, including whether either has a `legal_entity_id` (`generated/budgets/13...`, same reason).
   - A real P&L tree id, to replace the placeholder in `generated/gl/04_pl_by_month.json`.
   - A confirmed `AP.Enquiry` permission GUID (currently reusing `AR.Enquiry` in `generated/ap/*`).

## P1 — major capability

5. ~~**Formal intermediate representation** (`src/ir.py`).~~ **Done.** Typed dataclasses (`Param`, `Source`, `Field`, `Select`, `Layout`, `Enquiry`) that `enquiry_parser.py` decodes into and the validator/doctor/diff tools consume. `enqgen.py` itself still builds QueryXml directly (deliberately — see `docs/ARCHITECTURE.md`'s design choices).

6. ~~**`enquiry_doctor.py`**~~ **Done.** One file in, a STATUS (PASS/WARN/FAIL) + STRUCTURE/JOINS/PARAMETERS/METADATA/LAYOUT/PERMISSIONS/CONFIDENCE/RISKS report out.

7. ~~**`enquiry_diff.py`**~~ **Done.** Semantic (params/sources/fields/layouts/permissions by name) comparison of two enquiries.

8. **Aged-debt/creditor bucketing.** `dbo.GetIntervalRange(@IntervalId, days)` is documented but not yet used anywhere in `generated/`. Add proper 0-30/31-60/61-90/90+ bucketing to the aged debtors/creditors enquiries once the TVF's real output is confirmed (P0 item 1).

9. **Expand module coverage.** Not yet represented in `generated/`: Fixed Assets, VAT/Tax Return, Projects (beyond a mention in the master skill), Timesheets, Intercompany. Add once there's a real request or a confirmed pattern to build from — don't pad the library with unconfirmed guesses just for coverage's sake (this is the same discipline that led to removing two dead parameters this pass rather than fabricating their filters).

10. **Natural-language enquiry compiler** (prototype). Converts a sentence like "Create a GL enquiry showing nominal account, department and cost centre with debit, credit and net balance, grouped by department, filtered by accounting period" into a structured spec, then through requirement-parsing → schema resolution (`src/schema.py`) → query planning → layout planning → `enqgen.py` → `enquiry_validator.py`/`enquiry_doctor.py` → export. Deliberately deferred until now: building this on top of ad-hoc dicts (before `src/ir.py` existed) would have meant redoing it. The IR, validator, and doctor are the prerequisite infrastructure; this is the next P1 once appetite exists for it.

## P2 — developer experience

11. **Knowledge graph / pattern catalogue.** `docs/PROJECT_AUDIT.md` §9 scoped this down from the original ambition (a graph "mined from 640 enquiries") to what's actually possible: a `patterns/` catalogue (parameters/joins/metadata/layouts/permissions/filters/summaries/hierarchies) derived from this repo's own 14 real, working examples, each with its evidence count and confidence. Worth doing once module coverage (item 9) gives more than 14 examples to draw patterns from — 14 is thin evidence for calling something "the GL pattern" today.

12. **Explanation engine.** Given an enquiry, generate a plain-English account of what it reads, how the joins work, what each parameter does, which fields are calculated/aggregated, and which parts are confirmed vs. inferred — derived from `src/ir.py` + `src/confidence.py`, not hand-written. `enquiry_doctor.py`'s report is a step in this direction but is a diagnostic, not a walkthrough; this would be a separate, friendlier output mode.

13. **CI.** `tests/` runs via stdlib `unittest` and needs nothing installed — wiring it into GitHub Actions (`.github/workflows/test.yml`, plain `python -m unittest discover`) is a small addition whenever this repo gets its first real collaborator or PR.

14. **Keep `docs/SCHEMA.md` and `src/schema.py` from drifting.** They're meant to say the same thing in two forms (prose vs. importable data) and nothing currently enforces that. A `crv_gl`-shaped gap (present in `docs/SCHEMA.md`'s prose from the start, missing from `src/schema.py`'s `TABLES` dict until `src/confidence.py` surfaced it this pass) is exactly the kind of drift a small consistency test could catch automatically.

## P3 — experimental

15. **Property-based/fuzz testing beyond mutation.** `tests/test_mutations.py` covers deliberate, meaningful mutations of real enquiries. A further step — generating larger combinatorial spaces of field/filter/layout combinations, still seeded from real examples rather than random XML — is lower priority than the P0/P1 items above, since the mutation harness already found (i.e., confirmed catching) every failure mode currently documented.

16. **Feedback loop discipline.** Every time a `generated/` enquiry is imported and confirmed working (or confirmed broken) in a real tenant, that outcome belongs in `corpus/confirmed_patterns/` (or a fix + regression test in `tests/test_regressions.py`), not just in someone's memory. That discipline is the entire reason this repo produces compounding value instead of the same rediscovery every time — it applies to every item above, not just P0 item 1.
