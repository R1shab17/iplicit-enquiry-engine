# Discovered failure modes

Failure modes found *by building this repo's own tooling* — specifically,
by writing `src/ir.py`'s cross-reference checks and running them against
this repo's own `generated/*/*.json` — rather than by trial and error
against a live tenant (that's `docs/FAILURE_MODES.md`). Same format as that
file, extended with provenance since operating principle #1
(`docs/PROJECT_AUDIT.md`) requires it: symptom, minimal reproduction,
likely cause, evidence, detection rule, prevention rule, regression test.

Modes #1-#3 were real bugs sitting in this repo's own `generated/` output
before the engine-hardening pass — not hypothetical. See that branch's
commit fixing `src/build_library.py` for the exact diffs.

Modes #4-#8 were added in a later, deliberately **adversarial** pass
(attacking `enqgen.py`'s own output — duplicate names, malformed
permission ids, an under-specified hierarchy rule — rather than starting
from a bug already observed live or in this repo's own output). None of
them currently has a real hit in `generated/*/*.json` (all 14 files stay
clean), except #8, which — while still not *live*-confirmed — is grounded
in this repo's own only real hierarchy example rather than pure
speculation. Each is still a permanent, zero-cost check per operating
principle #6 ("actively search for counterexamples") and each is proven to
actually fire via `tests/test_mutations.py`, which mutates the real
`generated/` corpus rather than a synthetic fixture alone.

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

## 4. A duplicate `<Field Name="...">` within one `<Select>`

**Symptom:** untested against a live tenant. **Logically derived, not
live-confirmed.** The builder compiles each output Field into a `SELECT
[Name] = <source>.<sql>` list item; two Fields sharing a `Name` would
produce two columns aliased identically, and any PropMetaJson/layout
reference to that name becomes ambiguous about which one it means.

**Minimal reproduction:** two `<Field Name="Description" .../>` elements in
the same `<Select>`.

**Likely cause:** copy-pasting a field block within the same Select and
forgetting to rename it — easy to miss since XML with a repeated attribute
value is still well-formed.

**Evidence:** not found in any of this repo's 14 real `generated/*/*.json`
files (`tests/test_mutations.py::test_duplicating_a_field_name_is_caught`
confirms all 14 currently have unique Field names per Select). Added
adversarially — attacking `enqgen.py`'s own output rather than from a
discovered live bug — per operating principle #6.

**Detection rule:** `Select.duplicate_field_names()` (`src/ir.py`).

**Prevention rule:** when copying a Field definition within the same
Select, always give the copy a distinct `Name`.

**Regression test:**
`tests/test_validator.py::test_duplicate_field_name_is_flagged` (fixture:
`tests/fixtures/broken_duplicate_field_name.json`);
`tests/test_ir.py::TestSelect::test_duplicate_field_names`;
`tests/test_mutations.py::test_duplicating_a_field_name_is_caught`.

## 5. A duplicate `<Source Name="...">` within one `<Select>`

**Symptom:** untested against a live tenant. **Logically derived, not
live-confirmed.** Two Sources sharing an alias in the same Select would
compile to two `JOIN`s aliased identically — invalid SQL, or at best a SQL
engine silently picking one.

**Minimal reproduction:** `<Source Name="g" Sql="[dbo].[dac_gl]" .../>` and
a second `<Source Name="g" Sql="[dbo].[account]" .../>` in the same Select.

**Likely cause:** copying a join block from another enquiry that happens to
reuse the same short alias convention (`g`, `a`, `db`) without checking it's
not already taken in this Select.

**Evidence:** not found in any real `generated/*/*.json` file — see
`tests/test_mutations.py::test_duplicating_a_source_name_is_caught`. Added
adversarially, same rationale as #4.

**Detection rule:** `Select.duplicate_source_names()` (`src/ir.py`).

**Prevention rule:** keep alias conventions (`g`=dac_gl, `a`=account,
`db`=dac_doc_base, etc. — `docs/SCHEMA.md`) unique within a single Select;
if a second source of the same kind is genuinely needed, alias it distinctly
(`a2`, `db2`, ...).

**Regression test:**
`tests/test_validator.py::test_duplicate_source_name_is_flagged` (fixture:
`tests/fixtures/broken_duplicate_source_name.json`);
`tests/test_ir.py::TestSelect::test_duplicate_source_names`;
`tests/test_mutations.py::test_duplicating_a_source_name_is_caught`.

## 6. A duplicate `<Param Name="...">` across the whole enquiry

**Symptom:** untested against a live tenant. **Logically derived, not
live-confirmed.** Two Params sharing a name would show as two identical
pickers in the parameter panel, with unpredictable which-one-wins behaviour
for any filter or Binding that references the shared name.

**Minimal reproduction:** two `<Param Name="LegalEntityId" .../>` elements
in the same `<Query>`.

**Likely cause:** merging parameter lists from two build-script snippets
(e.g. combining a "standard filters" template with module-specific params)
without checking for an existing declaration of the same name.

**Evidence:** not found in any real `generated/*/*.json` file — see
`tests/test_mutations.py::test_duplicating_a_param_name_is_caught`. Added
adversarially, same rationale as #4/#5.

**Detection rule:** `Enquiry.duplicate_param_names()` (`src/ir.py`).

**Prevention rule:** when combining parameter lists from more than one
source, check the combined `P = [...]` list for name collisions before
calling `query_xml()`.

**Regression test:**
`tests/test_validator.py::test_duplicate_param_name_is_flagged` (fixture:
`tests/fixtures/broken_duplicate_param_name.json`);
`tests/test_ir.py::TestEnquiry::test_duplicate_param_names`;
`tests/test_mutations.py::test_duplicating_a_param_name_is_caught`.

## 7. A `RequiredPermissions` entry that isn't GUID-shaped

**Symptom:** untested against a live tenant — plausibly either a rejected
import or (worse) a silently-ignored permission entry, leaving the Create
button disabled the same way an empty `RequiredPermissions` does
(`docs/FAILURE_MODES.md` #4). **Logically derived, not live-confirmed**
which of those two it actually is.

**Minimal reproduction:** `build(..., permissions=["not-a-real-guid"])`.

**Likely cause:** `src/enqgen.py`'s `build()` accepts any string for a
permission id and only lowercases it — it doesn't check the shape. A typo
in a hand-written permission id (rather than one pulled from
`src/permissions.py`'s `PERM` table) would ship silently.

**Evidence:** not found in any real `generated/*/*.json` file — every one
uses `PERM[...]` from `src/permissions.py`, whose own
`tests/test_permissions.py::test_every_value_is_a_guid` already confirms
every table entry is GUID-shaped. This check guards the case where someone
bypasses that table with a literal string.
`tests/test_mutations.py::test_corrupting_a_permission_guid_is_caught`
confirms all 14 current files trip it once corrupted. Added adversarially.

**Detection rule:** `enquiry_validator.check_permission_guid_format()` — a
plain regex match against the standard 8-4-4-4-12 hex GUID shape.

**Prevention rule:** always take `RequiredPermissions` entries from
`src/permissions.py`'s `PERM` table rather than writing a literal string.

**Regression test:**
`tests/test_validator.py::test_malformed_permission_guid_is_flagged`
(fixture: `tests/fixtures/broken_permission_guid_format.json`);
`tests/test_mutations.py::test_corrupting_a_permission_guid_is_caught`.

## 8. A saved hierarchy with zero `groupRows` (not just more than one)

**Symptom:** untested against a live tenant. **Logically derived, not
live-confirmed** — but grounded in this repo's own real output, unlike #4-7:
the *only* confirmed-working hierarchy layout ever built here
(`generated/gl/04_pl_by_month.json`, "Uses a P&L tree hierarchy on a
SINGLE-level groupRows (AccountId only) — safe combination") always pairs
the tree with **exactly one** `groupRows` entry — the field whose values
map onto the tree's leaf nodes. The original check (`docs/FAILURE_MODES.md`
#1) only flagged *more than one* level; it never asked whether zero levels
might be just as broken, for the same underlying reason (the tree has
nothing to bucket rows by).

**Minimal reproduction:** a layout with `"hierarchy": {...}` set and no
`groupRows` key (or an empty list) at all.

**Likely cause:** building a hierarchy-based layout by deleting an
"extra" groupRows level to fix the #1 conflict and accidentally deleting
the *only* level instead of the second one.

**Evidence:** not found in real output — `04_pl_by_month.json` has exactly
one groupRows level, and no other generated enquiry uses a hierarchy at
all. `tests/test_mutations.py::test_stripping_grouprows_from_a_hierarchy_layout_is_caught`
mutates that one file's groupRows to empty and confirms the validator now
catches it (it did not, before this pass — a genuine validator gap in the
existing #1 check, closed here). Added adversarially while stress-testing
the existing hierarchy check.

**Detection rule:** extended `enquiry_validator.check_layouts()` — when a
hierarchy is present, `len(groupRows) != 1` (not merely `> 1`) is flagged,
with a distinct message for the `== 0` case.

**Prevention rule:** a hierarchy layout should always declare exactly one
`groupRows` entry, naming the field whose values are tree leaf codes.

**Regression test:**
`tests/test_validator.py::test_hierarchy_with_no_grouprows_is_flagged`
(fixture: `tests/fixtures/broken_hierarchy_no_grouprows.json`);
`tests/test_doctor.py::test_hierarchy_no_grouprows_lands_in_layout_section`;
`tests/test_mutations.py::test_stripping_grouprows_from_a_hierarchy_layout_is_caught`.

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
