# Discovered failure modes

Failure modes found *by building this repo's own tooling* — specifically,
by writing `src/ir.py`'s cross-reference checks and running them against
this repo's own `generated/*/*.json` — rather than by trial and error
against a live tenant (that's `docs/FAILURE_MODES.md`). Same format as that
file, extended with provenance since operating principle #1
(`docs/PROJECT_AUDIT.md`) requires it: symptom, minimal reproduction,
likely cause, evidence, detection rule, prevention rule, regression test.

All three of these were real bugs sitting in this repo's own `generated/`
output before this pass — not hypothetical. See the `engine-hardening`
branch's commit fixing `src/build_library.py` for the exact diffs.

## 1. A declared `<Param>` that no filter, Source, or Binding ever uses

**Symptom:** the enquiry imports and runs fine; a picker appears in the
Enquiry's parameter panel; changing its value has *zero* effect on the
results. No error anywhere — the parameter is simply decorative.

**Minimal reproduction:** declare `<Param Name="LegalEntityId" .../>` and
never reference `@LegalEntityId` in any `FilterArgument`/`FilterOr`/`Filter`,
any `Source`'s `Sql`, or any other Param's `<Binding Name="LegalEntityId">`.

**Likely cause:** copy-pasting a standard parameter list (most of this
project's enquiries start from a `LegalEntityId` + module-specific params
template) without wiring the corresponding filter field — especially
tempting when the natural filter column lives on a table whose schema
isn't confirmed (see below), so the field gets quietly dropped but the
param declaration doesn't.

**Evidence:** found live in this repo's own output —
`generated/bank/10_bank_transactions_by_account.json` and
`generated/budgets/13_budget_vs_actual.json` both declared a `LegalEntityId`
param with no corresponding filter field, in both cases because the
natural filter target (`bank_transaction.legal_entity_id`,
`budget2_key.legal_entity_id`) is an unconfirmed column
(`docs/SCHEMA.md`) and adding it would have meant presenting a guess as
fact — CLAUDE.md's "one rule that matters most." The correct fix (applied)
was to remove the dead parameter, not to fabricate the column.

**Detection rule:** `Enquiry.unused_params()` (`src/ir.py`) — a declared
Param name absent from `Enquiry.referenced_param_names()` (which unions
every Field's filter references, every Source's inline `@token`s, and
every other Param's `<Binding Name="...">` targets).

**Prevention rule:** when a natural filter column isn't confirmed, remove
the parameter rather than leave it dangling — an absent filter is honest;
a picker with no effect is misleading. Re-add it once the column is
confirmed (`docs/ROADMAP.md` item 2).

**Regression test:** `tests/test_validator.py::test_unused_param_is_flagged`
(fixture: `tests/fixtures/broken_unused_param.json`);
`tests/test_ir.py::TestEnquiry::test_unused_params`.

## 2. A cascading `<Binding Name="...">` pointing at the wrong name

**Symptom:** a cascading picker (e.g. "Financial year group", filtered by
legal entity) either shows every option regardless of the parent picker's
value, or behaves inconsistently — with no error, because the binding
silently fails to resolve rather than throwing.

**Minimal reproduction:** a Param's Setting XML contains
`<Binding Name="LegalEntity" ... PropertyName="LegalEntity"/>` when the
actual declared parameter supplying that value is named `LegalEntityId`.
`Binding`'s `Name` attribute must be the literal name of another declared
`<Param>` — not the semantic property label a catalog function expects
(that's what `PropertyName` is for).

**Likely cause:** `src/enqgen.py`'s `setting(bindings=...)` helper takes
`(source_param_name, value_type, property_name)` tuples, and it's easy to
transpose "the param" and "the property" when both happen to share a
similar name (`LegalEntity` the property vs. `LegalEntityId` the param) —
exactly what happened here.

**Evidence:** found live in `generated/gl/01_gl_trial_balance.json`: the
`FinancialYearGroupId` param's binding used
`bindings=[("LegalEntity", "Text", "LegalEntity")]` in
`src/build_library.py`, where the correctly-working `PeriodId` param two
lines later correctly used
`bindings=[("LegalEntityId", "Text", "LegalEntity")]` for the equivalent
relationship — the inconsistency between the two was the tell. Fixed on
the `engine-hardening` branch.

**Detection rule:** `Enquiry.undeclared_param_references()` (`src/ir.py`)
— a `<Binding Name="X">` (or `@X` token) with no matching declared
`<Param Name="X">`.

**Prevention rule:** when writing a `bindings=[...]` tuple, the first
element is always another Param's exact declared name — verify it appears
verbatim in that Select's/Enquiry's own `P = [...]` list, not a
value borrowed from the `PropertyName` slot.

**Regression test:**
`tests/test_validator.py::test_undeclared_param_reference_is_flagged`
(fixture: `tests/fixtures/broken_undeclared_param.json`);
`tests/test_ir.py::TestEnquiry::test_undeclared_param_references`.

## 3. A `Field`'s `Source` naming an alias that was never declared

**Symptom:** the generated QueryXml is well-formed XML, but the SQL it
compiles to references a table alias that doesn't exist in the `FROM`/
`JOIN` clause — a broken query. Not yet observed against a live tenant
(no such enquiry has been imported), so this is currently a **logically
derived, not live-confirmed** failure mode: it follows directly from how
`docs/IPLICIT_ENQUIRY_MASTER_SKILL.md` says the builder compiles
`Field Source="X"` into `<X>.<sql>` (see "The builder turns QueryXml
into..." in that doc) — an undeclared alias there can only produce invalid
SQL. Treat the *mechanism* as confirmed and the *exact UI failure
behaviour* (silent vs. an error dialog) as unconfirmed until tested live.

**Minimal reproduction:** a Select declares only `<Source Name="g" .../>`
but has `<Field Name="Amount" Source="x" Sql="amount" .../>`.

**Likely cause:** a copy-pasted field from a different enquiry/module
where the source alias convention differs (e.g. `g` for `dac_gl` vs. `db`
for `dac_doc_base`), edited incompletely.

**Evidence:** not found in this repo's current `generated/*/*.json` (all
14 pass this check clean) — discovered as a *blind spot in the validator*
while writing `src/ir.py`, then confirmed absent from real output rather
than present in it. Recorded here anyway per operating principle #6
("actively search for counterexamples") — a check with zero historical
hits is still worth keeping once it's cheap to run.

**Detection rule:** `Select.dangling_source_references()` (`src/ir.py`) —
a Field's `source` not present in that Select's own `source_names()`.

**Prevention rule:** when reusing a field definition across modules,
re-verify its `source=` argument against the Select's actual `src(...)`
alias list, not the alias convention of the enquiry it was copied from.

**Regression test:**
`tests/test_validator.py::test_dangling_source_reference_is_flagged`
(fixture: `tests/fixtures/broken_dangling_source.json`);
`tests/test_ir.py::TestSelect::test_dangling_source_references`.

## Also checked for, not found

While building the cross-reference layer, these were also tested against
all 14 real `generated/` enquiries and came back clean (see
`tests/test_regressions.py::TestAllGeneratedFilesStillValidate`):

- Layout `columns`/`groupRows`/`groupColumns`/`groupData`/`includes`/
  `detail` referencing a field the query doesn't output.
- PropMetaJson entries for a field the query doesn't output ("orphan
  metadata").

Both remain permanent validator checks (`check_cross_references` in
`src/enquiry_validator.py`) even with zero current hits, for the same
reason as #3 above — cheap to run, and the next generated enquiry might
trip one.
