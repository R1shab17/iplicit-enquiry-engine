# Generated enquiry library — index

14 ready-to-import `DbEnquiry` exports, built by `src/build_library.py` (using `src/enqgen.py`) and passed through `src/enquiry_validator.py` — structural checks only. **None of these have been run against a live iplicit database from this repo's own tooling** (see `docs/ROADMAP.md` item 1); the notes below flag every place the underlying schema wasn't independently confirmed (cross-reference `docs/SCHEMA.md`).

**To use:** open the `.json` file, copy its whole contents, then in iplicit go to **Enquiries > (menu) > Import from clipboard > Apply**, tick an analytic group, and click **Create**. Creating it is a human action — nothing in this repo does that for you.

| # | File | Description | Module | Notes / caveats |
|---|---|---|---|---|
| 1 | `gl/01_gl_trial_balance.json` | Trial balance by legal entity and period | GL | Debit/Credit split derived from the base-currency Amount sign; Balance = net. LegalEntityId/PeriodId are filter-only (Output=False) so they don't force a finer implicit GROUP BY than "one row per account". |
| 2 | `gl/02_gl_detail_by_nominal.json` | GL detail by nominal (with department & cost centre) | GL | Flat list (no Summary fields), so extra Column fields don't distort grouping. Department/CostCentre pulled via crv_gl left join. |
| 3 | `gl/03_balance_sheet_by_department_nominal.json` | Balance sheet by department and nominal | GL | No `hierarchy` tree — deliberately, since it conflicts with the 2-level groupRows (confirmed live; see `docs/FAILURE_MODES.md` #1). LegalEntityId/AccountType are filter-only. This is the parameterised, reusable version of the enquiry originally fixed in this project's first requests. |
| 4 | `gl/04_pl_by_month.json` | Profit & loss by month | GL | Uses a P&L tree hierarchy on a SINGLE-level groupRows (AccountId only) — safe combination, unlike #3. `treeId` is a placeholder: replace with your tenant's actual P&L tree id (export any existing P&L enquiry to find it), or delete the hierarchy key for a flat grouping. See `docs/ROADMAP.md` item 2. |
| 5 | `ar/05_aged_debtors_by_customer.json` | Aged debtors by customer | AR | Uses `dbo.GetAgedDebt` as a principal Sql source. Outstanding uses plain `decimal` viewType, not `amount`, because GetAgedDebt's currency columns aren't confirmed — verify before switching to amount+currencyMember. For bucketed ageing (0-30/31-60/...), add `CROSS APPLY dbo.GetIntervalRange(@IntervalId, days)` and group by its `range` column (see `docs/ROADMAP.md` item 3). |
| 6 | `sales/06_top_customers_by_revenue.json` | Top customers by revenue | Sale | DocDate is filter-only (Output=False) — as a raw Column it would otherwise force grouping by (customer, date) instead of a single total per customer across the whole range (`docs/FAILURE_MODES.md` #5). Ranking/"top N" is done by sorting the grid descending, not a SQL TOP-per-group. |
| 7 | `ap/07_aged_creditors_by_supplier.json` | Aged creditors by supplier | AP | Mirror of #5 using GetAgedCreditors. Permission list reuses AR.Enquiry pending confirmation of a dedicated AP.Enquiry id (`docs/ROADMAP.md` item 2). |
| 8 | `purchasing/08_purchase_invoices_by_supplier_month.json` | Purchase invoices by supplier by month | Purchase | Direct mirror of the tested "sales by customer by month" pattern, swapped to `is_purchase` / Supplier. |
| 9 | `ap/09_overdue_purchase_invoices.json` | Overdue purchase invoices | Purchase | Flat list: `due_date < AsOfDate` AND still outstanding (HasOutstanding filter-only field). Not aged into buckets — see #7. |
| 10 | `bank/10_bank_transactions_by_account.json` | Bank transactions by account | Bank | Base-table join since `bank_transaction` has no dac_* equivalent documented. Amount uses plain `decimal` viewType (currency column on `bank_transaction` not confirmed) — verify against the live schema before relying on this one. |
| 11 | `gl/11_manual_journals_by_date.json` | Manual journals posted in a date range | GL | `doc_type.is_gl=1` identifies manual-journal-family documents. |
| 12 | `gl/12_documents_by_user.json` | Documents created/last modified by user | DocBase | CAUTION: `dac_doc_base`'s own `last_modified_by` column is not confirmed (only `dac_gl`'s and `account`'s were) — `LastModifiedBy` is stubbed to `created_by` here as a placeholder. Check `INFORMATION_SCHEMA.COLUMNS` on `dac_doc_base` before relying on this one; swap the Sql if a real column exists. See `docs/ROADMAP.md` item 2. |
| 13 | `budgets/13_budget_vs_actual.json` | Budget vs actual by cost centre | GL | UNION ALL of `budget2_value` and `dac_gl`, both padded with a `0` Constant for the column the other side doesn't have so the two Selects output identical field lists (`docs/FAILURE_MODES.md` #8). Amounts use plain `decimal` viewType since there's no single shared currency field across the union. PeriodId is filter-only. `budget2*` structure is inferred, not confirmed (`docs/SCHEMA.md`). |
| 14 | `sales/14_credit_notes_by_period.json` | Credit notes issued by period | Sale | Flat list (no Summary fields) so DocDate can safely double as both filter and display column. `doc_type.is_credit_note=1` filters to credit notes; `mul_control` applied for the correct sign. |

## Re-running the generator

```bash
python3 src/build_library.py                       # rebuilds generated/<module>/*.json from the definitions in build_library.py
python3 src/enquiry_validator.py generated/*/*.json # structural checklist
```

Edit `src/build_library.py` to change a definition, or copy its pattern (`src/enqgen.py` functions) to add a new one — see `docs/IPLICIT_ENQUIRY_MASTER_SKILL.md` for the full grammar and schema reference, and `CLAUDE.md` before adding anything new to this folder.
