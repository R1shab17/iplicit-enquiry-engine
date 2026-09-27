# Known failure modes

iplicit gives no error message for most of these — an enquiry just doesn't render, or the Create button stays disabled. Every one of these is checked by `src/enquiry_validator.py`; this document is the "why" behind each check.

## 1. Hierarchy + multi-level `groupRows` → silently returns no data

**Confirmed by direct trial and error this session.** A layout's `hierarchy` key (a saved tree — e.g. "Standard Balance Sheet tree") nests the row grouping inside that tree's structure. It's built around a *single* grouping field (typically `AccountId`). Adding a second `groupRows` level in front of it (e.g. grouping by Department, then Account) breaks the grid's ability to reconcile the two grouping mechanisms, and the enquiry returns an empty result with no error.

- **Fix:** either drop `hierarchy` and use a plain multi-level `groupRows` (what `generated/gl/03_balance_sheet_by_department_nominal.json` does), or keep `hierarchy` and restrict `groupRows` to the single field the tree is built on (what `generated/gl/04_pl_by_month.json` does).
- **Validator check:** `check_layouts()` in `src/enquiry_validator.py` flags any layout combining `hierarchy` with `len(groupRows) > 1`.

## 2. Optional filter without the "or is null" pairing → excludes everything when the param is empty

`FilterOperator="In" FilterArgument="@X"` alone means SQL Server evaluates `column IN (NULL)`, which is never true — so leaving a multi-select picker empty (the normal "don't filter by this" state) returns zero rows instead of all rows.

- **Fix:** always pair it — `FilterOperator="In" FilterArgument="@X" FilterOr="@X is null"`.
- **Validator check:** `check_query_xml()` flags any `FilterOperator="In"` field without a matching `FilterOr`.

## 3. `Between` filter without `ISNULL(...)` → same failure, for date ranges

`FilterOperator="Between" FilterArgument="@From AND @To"` fails the same way when either bound is left blank.

- **Fix:** `FilterArgument="ISNULL(@From,{0}) AND ISNULL(@To,{0})"` (`{0}` substitutes the field's own SQL).
- **Validator check:** flags any `Between` filter whose argument doesn't contain `ISNULL(`.

## 4. Missing `RequiredPermissions` → Create button stays disabled, no error shown

The single most common reason a generated/imported enquiry "doesn't work" — it imports fine, previews fine, and then Create is simply greyed out.

- **Fix:** always include at least one `AttributeOperationId` matching the module (`src/permissions.py` has the known GUIDs).
- **Validator check:** flags an empty `RequiredPermissions` list.

## 5. Non-Summary field silently widening the GROUP BY grain

Any query field that is `Type="Column"` or a non-aggregated `Expression` becomes an implicit `GROUP BY` key the moment *any* field in the same Select is `Type="Summary"`. A filter-only field (a date range bound, a constant type filter, a legal-entity picker) left as a plain output column will split an intended "one row per customer" aggregate into "one row per customer per date/legal-entity/etc." instead — with no error, just a report that looks wrong.

- **Fix:** mark filter-only fields `Output="False"` unless they're genuinely meant to be part of the display grain (fine in a flat list with no `Summary` fields at all — see `generated/gl/02_gl_detail_by_nominal.json` for that case).
- **Validator check:** not fully automatable (requires knowing intent), but `check_query_xml`/`check_prop_meta` catch the related symptom of an unlabelled output field; see `tests/test_regressions.py` for worked before/after examples from this project's own history (§ "6. Top customers by revenue" originally leaked `DocDate` into the grain — fixed in `src/build_library.py`).

## 6. Amount column with an unresolvable `currencyMember`

A PropMetaJson column with `viewType: "amount"` needs its `currencyMember` (typically `BaseCurrency`) to be present somewhere in the layout — either the query's output fields or the layout's `includes` — or the amount won't render correctly.

- **Fix:** always add the base-currency field to the query and to the layout's `includes` (or `columns`) alongside any `amount`-typed column.
- **Validator check:** `check_layouts()` cross-references every `amount`-typed column against `includes`/`columns`.

## 7. Confusing which entity's audit fields you mean

`dac_gl.last_modified_by` (the GL posting's audit stamp) and `account.last_modified_by` (the chart-of-accounts record's) are different columns on different tables, both plausibly called "last modified by" in plain English. Confirmed this session: the user asked for the account's, got the posting's by default, and it took a follow-up to catch. `dac_doc_base`'s own last-modified column existence is still unconfirmed at all (see `docs/SCHEMA.md`).

- **Fix:** when a request says "last modified" without naming the entity, ask, or default to the entity actually being reported on (the account, in an account-grouped report) rather than the transaction.

## 8. Union `Select` blocks with mismatched field lists

Every `<Select Union="...">` after the first must output exactly the same field names, in the same order. A field one side doesn't naturally have (e.g. `ActualAmount` in a budget-only Select) needs a `Type="Constant"` placeholder (`0`) rather than being omitted.

- **Fix:** pad both sides — see `generated/budgets/13_budget_vs_actual.json`.
- **Validator check:** `check_query_xml()` compares each unioned Select's field-name list against the first.
