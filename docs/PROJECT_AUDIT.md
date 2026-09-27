# Project audit

Written as a structured self-assessment before a substantial hardening pass
(the `engine-hardening` branch). Re-run this exercise whenever the
architecture changes significantly.

## 0. Correcting a premise before anything else

A brief for this pass asserted that the repo "already contains ... 640
real enquiry definitions from a sandbox." **That is not true of this
repository's contents.** `corpus/real_enquiries/` is empty except for its
own README. What actually exists:

- A one-time exploration (an earlier session, with live browser access to
  an iplicit sandbox) read all 640 `dbo.enquiry`/`dbo.enquiry_layout` rows
  via a preview-runner SQL hook and used them to write
  `docs/IPLICIT_ENQUIRY_MASTER_SKILL.md`'s grammar and schema knowledge.
- **The raw 640 definitions themselves were never saved into this repo.**
  Only the distilled prose/patterns survived, in the master skill doc.
- The 14 files in `generated/` are synthetic — built by this repo's own
  generator, validated structurally, never run against a live tenant.

This matters because operating principle #1 (evidence before assumption)
is meaningless if "evidence" secretly means "a doc's prose summary of
evidence I can no longer inspect." Every claim below is scoped
accordingly: **corpus-mining tasks that require the raw 640 records are
blocked**, not merely unstarted. See §8 and `docs/ROADMAP.md` P0 item 1.

## 1. Current architecture

```
docs/IPLICIT_ENQUIRY_MASTER_SKILL.md, QUICK_SKILL.md   — distilled grammar/schema (prose, from the one-time exploration)
src/schema.py, joins.py, layouts.py, permissions.py    — that knowledge as importable Python data
src/enqgen.py                                           — orchestrator: builds QueryXml + envelope from Python calls
src/enquiry_parser.py                                   — decodes an export envelope back into structured data
src/enquiry_validator.py                                — structural checklist against a parsed enquiry
src/build_library.py                                    — the 14 concrete build scripts
generated/<module>/*.json                               — their validated output
tests/                                                   — 52 unit tests, fixtures, 2 regression cases
corpus/{real_enquiries,confirmed_patterns,unknown_patterns}/ — currently empty placeholders (see §0)
```

Data flow: plain Python calls → `enqgen.py` → QueryXml string + model dict
→ base64 envelope → `enquiry_validator.py` (via `enquiry_parser.py`) →
`generated/`. Nothing in `src/` talks to a live tenant; import/Create is
always a human action.

## 2. Current capabilities

- Deterministic generation of a DbEnquiry export from typed Python calls
  (no hand-written XML/JSON).
- Structural validation: XML well-formedness, union field-list parity,
  `In`/`Between` null-safety idioms, permission presence, hierarchy +
  multi-level groupRows conflict, amount/currencyMember presence,
  PropMeta coverage of the first Select's output fields.
- Round-trip decoding of any export (real or generated) into the same
  shape the generator builds from (`enquiry_parser.py`), enabling
  structural comparison.
- 14 working (structurally-valid, never live-tested) enquiries spanning
  7 modules, each with its assumptions documented per-row in
  `generated/INDEX.md`.
- A three-tier confidence vocabulary (confirmed / inferred / unconfirmed)
  applied inconsistently: `docs/SCHEMA.md` uses prose, `src/schema.py`
  uses a `status` field on some entries, `generated/INDEX.md` uses free
  text. No single machine-readable source of truth (see §6, §9).

## 3. Current weaknesses

- **No formal intermediate representation.** `enqgen.py` builds
  dictionaries by convention (`{"name":..., "sql":..., ...}`), not typed
  objects. Nothing stops a caller from mistyping a key, mismatching a
  `Source` name against a `Field`'s `source`, or referencing an
  undeclared `@Param` in a filter — the generator will happily emit
  malformed-but-well-formed-XML that fails silently in the real UI.
- **The validator only checks the first Select's output fields against
  PropMeta**, and only checks the *union* field-list-length/name parity —
  it never confirms that a `Field`'s `Source` attribute actually names a
  declared `Source`, that a `layout` column/groupRows/groupData entry
  names a real output field, or that every `@Param` used in a filter was
  actually declared as a `<Param>`. These are exactly the kind of
  structural mistakes a generator refactor (like the one just done) could
  introduce without any test catching it.
- **No fuzz/mutation testing.** The 52 unit tests are all hand-written
  example-based tests; nothing systematically explores the space of valid
  vs. invalid mutations of a real (generated) enquiry to find validator
  blind spots.
- **No confidence/evidence report is emitted per enquiry.** A reader has
  to open `generated/INDEX.md` and read prose to learn that enquiry #10
  depends on an unconfirmed table. There's no `enquiry_doctor.py`-style
  tool that computes this from the file itself.
- **No semantic diff tool.** Comparing two enquiry exports means reading
  raw JSON/XML by eye.
- **No natural-language front end.** Nothing between "plain English
  request" and "call `enqgen.py` functions by hand" exists yet — that's
  entirely aspirational (see `docs/ROADMAP.md` P3).
- **Corpus mining is blocked, not merely unstarted** (§0) — none of "mine
  the 640 enquiries for recurring patterns" can be honestly done without
  that raw data.

## 4. Missing tests

- No test that a `Field`'s `Source` alias matches a declared `Source` name
  (a plausible generator-authoring mistake with no runtime error).
- No test that every `@Param` used in a `FilterArgument`/`Filter`/`Setting`
  binding string was actually declared as a `<Param>`.
- No test that layout `columns`/`groupRows`/`groupColumns`/`groupData`/
  `includes`/`sortBy` field names exist among the query's output fields.
- No test that a declared `<Param>` is actually used anywhere (dead
  parameters are harmless but indicate a stale build script).
- No property-based/mutation coverage — see §3.
- No test asserting `docs/SCHEMA.md` and `src/schema.py` agree (they can
  drift silently; nothing enforces it).

## 5. Schema knowledge gaps

Unchanged since the last audit (`docs/ROADMAP.md` item 2) — restated here
for completeness, now cross-referenced to `src/schema.py`'s
`unconfirmed_columns`/`status` fields where they exist:

- `dac_doc_base.last_modified`/`last_modified_by` — existence unconfirmed.
- `dbo.GetAgedDebt`/`GetAgedCreditors` real output column names.
- `bank_transaction` full column list (esp. currency).
- `budget2`/`budget2_key`/`budget2_value` full column list.
- A real P&L tree id (placeholder in `generated/gl/04_pl_by_month.json`).
- A confirmed `AP.Enquiry` permission GUID (`generated/ap/*` reuses
  `AR.Enquiry`'s).

None of these can be resolved without live tenant/browser access. They
are correctly flagged inline today; the gap is that flagging isn't
machine-checkable (§3, §9).

## 6. Generator weaknesses

- Functions return plain dicts, not validated objects — see §3.
- `fld()`'s `type` inference (`"Column"` if `source` else `"Expression"`)
  is a convenient default that can silently produce the wrong `Type` if a
  caller passes both a `source` and means `Expression` (e.g., a computed
  column that happens to reference one aliased table). Not currently
  guarded against.
- No helper enforces the "mark filter-only fields `Output=False`"
  discipline from `docs/FAILURE_MODES.md` #5 — it's a documentation
  convention, not a type-level one.
- `joins.py`'s `gl_standard_joins()`/`doc_standard_joins()` were added in
  the last pass but aren't yet used by `build_library.py` (which still
  inlines its own `src()` calls per enquiry) — an inconsistency worth
  resolving so there's one source of truth for the standard join chains.

## 7. Validator weaknesses

Already covered in detail in §3/§4. Summarized: the validator checks
*envelope-level* structure well, but does not check *cross-reference*
integrity (Source ↔ Field, Param ↔ filter usage, output fields ↔ layout
references, PropMeta ↔ non-first-Select fields in a union). These are
exactly the errors a human editing generated XML by hand (which
`CLAUDE.md` forbids, but which the validator should still defend against)
would introduce.

## 8. Corpus opportunities

Real opportunities, scoped to what's actually possible without the raw
640 corpus:

- **Mutation testing against the real 14** (`generated/*/*.json`): apply
  small, meaning-changing edits (drop a permission, break a filter's
  null-safety, reintroduce a hierarchy+multi-groupRows conflict, corrupt
  a union's field list, dangle a Source reference) and confirm the
  validator catches each one. This is honest, real, and immediately
  actionable — it doesn't need the missing 640.
- **When live/browser access to an iplicit tenant is available again**,
  pulling the raw 640 rows into `corpus/real_enquiries/` is still the
  single highest-leverage action available to this project (unchanged
  from `docs/ROADMAP.md`). Nothing here can substitute for it.

## 9. Highest-value improvements (this pass)

In priority order, all achievable without new external evidence:

1. **P0 — Cross-reference validation** (Source↔Field, Param↔filter usage,
   layout↔output fields, PropMeta↔all-Selects-in-a-union). Closes the
   biggest real gap in §3/§7 and protects the generator refactor already
   done.
2. **P0 — Formal IR** (`src/ir.py`, typed dataclasses) that
   `enquiry_parser.py` decodes into and the new validator layers consume,
   making "Source referenced by a Field must exist" a structural
   invariant the type system can help enforce, not just a runtime check.
3. **P1 — Mutation test harness** against the real 14, to find validator
   blind spots empirically rather than by inspection alone.
4. **P1 — `enquiry_doctor.py`**: one command, one file in, a structured
   PASS/WARN/FAIL report out (structure/schema/joins/params/metadata/
   layout/permissions/confidence/risks), built on the IR + validator +
   `schema.py`'s confidence data — not a new source of truth, a better
   window onto the existing one.
5. **P1 — `enquiry_diff.py`**: semantic diff of two enquiries, for
   comparing a generated draft against a real export once one is
   available, or two generated drafts against each other.
6. **P2 — Confidence/evidence module** (`src/confidence.py`): centralizes
   the "confirmed / inferred / unconfirmed" judgment already scattered
   across `docs/SCHEMA.md` prose, `src/schema.py`'s `status` field, and
   `generated/INDEX.md` prose, so `enquiry_doctor.py` and future tooling
   read one source instead of three.
7. **P3 — natural-language front end**: explicitly deferred. Building a
   requirement parser/planner on top of an IR that didn't exist until
   this pass would be premature; §9 items 1–2 are the prerequisite.

## 10. Proposed autonomous execution order

1. `src/ir.py` (dataclasses) + `tests/test_ir.py`.
2. Extend `enquiry_parser.py`/`enquiry_validator.py` with the
   cross-reference checks from item 1 above; extend `tests/test_validator.py`
   and add targeted fixtures.
3. `tests/test_mutations.py` — mutation harness against `generated/*/*.json`.
4. `src/confidence.py` + wiring it into a report.
5. `src/enquiry_doctor.py` (CLI).
6. `src/enquiry_diff.py` (CLI).
7. Update `docs/DISCOVERED_FAILURE_MODES.md` with anything the above
   surfaces (a dangling Source reference already stands out as a
   plausible, previously-undocumented failure mode — see that file).
8. Refresh `docs/ROADMAP.md` with P0–P3 priorities reflecting the above,
   `docs/ARCHITECTURE.md` with the new pieces, and `README.md`'s
   quick-start commands.
9. Full regression run (`unittest discover`) + validator run against
   every `generated/` file before committing.

This audit is the input to that work, not a substitute for it — see the
commit history on the `engine-hardening` branch for what was actually
done versus deferred.
