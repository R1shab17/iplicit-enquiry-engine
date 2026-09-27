# Schema reference

Confirmation status matters here. **Confirmed** = seen directly in a real enquiry definition's QueryXml (from the original 640-definition exploration) or verified live this session. **Inferred** = follows the documented naming/structure conventions but hasn't been independently checked against `INFORMATION_SCHEMA.COLUMNS`. Treat "inferred" as a hypothesis, not a fact — see `corpus/unknown_patterns/`.

## Principal views (use these, not the base tables)

| View | Alias convention | Status | Notes |
|---|---|---|---|
| `[dbo].[dac_gl]` | `g` | Confirmed | GL posting lines. Applies legal-entity access control. |
| `[dbo].[dac_doc_base]` | `db` | Confirmed | Document headers (invoices, orders, journals). Applies legal-entity access control. |
| `[dbo].[dac_legal_entity]` | `le` | Confirmed | Legal entity list, access-controlled. |

Base tables (`dbo.gl`, `dbo.doc_base`, `dbo.doc_detail`) exist underneath these but **skip legal-entity security** — only use them when you deliberately want cross-entity visibility (rare, and should be called out explicitly).

## Analytic-dimension views (confirmed)

| View | Alias convention | Keyed by | Notes |
|---|---|---|---|
| `[generated].[crv_gl]` | `cg` | `cg.id = g.id` (left join) | Department, CostCentre, Fund, Resource, Location, Activity, Intercon, Country, IncomeType, etc. for a GL line. Not every line has every dimension set. |
| `[generated].[crv_doc_base]` | `cd` | `cd.id = db.id` (left join) | Document-header equivalent. |
| `[generated].[crv_doc_detail]` | — | keyed to `doc_detail` | Document-line equivalent. |

These were confirmed-in-use from the start of this project (every GL-grain
enquiry in `generated/` joins `crv_gl`) but were missing their own entries
in `src/schema.py`'s `TABLES` dict until `src/confidence.py`'s report
surfaced the gap — every enquiry using them was scoring as "unknown
confidence" for a view that was never actually in doubt. Fixed during the
engine-hardening pass; see `docs/DISCOVERED_FAILURE_MODES.md`'s "also
checked for" pattern of keeping cheap checks even when they're clean.

## `dac_gl` columns (confirmed)

`id`, `amount` (base currency), `currency_amount`, `currency`, `base_currency`, `account_id`, `period_id`, `period_date`, `post_date`, `trans_date`, `doc_id`, `doc_no`, `doc_type_id`, `contact_account_id`, `project_id`, `product_id`, `legal_entity_id`, `tax_code_id`, `description`, `invoice_no`, `trans_no`, `trans_line_no`, `attribute_id`, `bank_account_id`, `last_modified`, `last_modified_by`.

Analytic dimensions (Department, CostCentre, Fund, Resource, Location, Activity, Intercon, Country, IncomeType…) are **not** on `dac_gl` — join `[generated].[crv_gl]` (alias `cg`) on `cg.id = g.id` (left join; not every GL line has every dimension set).

## `dac_doc_base` columns (confirmed)

`id`, `doc_no`, `doc_date`, `due_date`, `tax_date`, `status`, `net_amount`/`tax_amount`/`gross_amount` (base) + `*_currency_amount` variants, `currency`, `base_currency`, `contact_account_id`, `doc_type_id`, `doc_class`, `period_id`, `legal_entity_id`, `project_id`, `their_doc_no`, `their_ref`, `order_no`, `description`, `created_by`, `created_date`, plus boolean helpers `status_is_draft`/`status_is_posted`/`status_is_abandoned`/`status_is_dispute`/`status_is_closed`.

**Inferred, not confirmed:** whether `dac_doc_base` has its own `last_modified`/`last_modified_by` columns (distinct from `created_by`/`created_date`). `generated/gl/12_documents_by_user.json` stubs `LastModifiedBy` to `created_by` pending this. Check `INFORMATION_SCHEMA.COLUMNS` on `dac_doc_base` before relying on a real one.

## `doc_detail` (confirmed)

`doc_id`, `product_id`, `description`, `quantity`, `net_amount`/`tax_amount`/`gross_amount` (+ `*_currency_amount`), `tax_code_id`, `period_id`, `order_index`.

## Sign convention (confirmed)

Multiply document amounts by `doc_type.mul_control` so credit notes/negative document types come out with the correct sign. Never trust a document amount's raw stored sign alone when doc type varies.

## `doc_type` (confirmed)

Flags: `is_sale`, `is_purchase`, `is_credit_note`, `is_gl`, `has_outstandings`, `is_cb`, `doc_class`, `attribute_id`, `mul_control`.

## Outstanding / aged debt (confirmed structure, inferred column names on the TVFs)

- `doc_outstanding` (PK = doc id): `cur_outs_amount`, `posted_outs_amount`, `mul_control`. Confirmed.
- `doc_allocation (doc_id, alloc_doc_id, amount)`. Confirmed.
- `dbo.GetAgedDebt(@col, @to_date)` / `dbo.GetAgedCreditors(@col, @to_date)` — confirmed to exist and to be usable as a `Sql`-type source; **the exact output column names are inferred** (`cur_outs_amount` assumed by analogy with `doc_outstanding`, not independently checked). See `generated/ar/05_aged_debtors_by_customer.json` and `generated/ap/07_aged_creditors_by_supplier.json`, both flagged.
- `dbo.GetIntervalRange(@IntervalId, days)` — confirmed to exist for bucketing (`CROSS APPLY`), giving `range`/`range_index`. Not yet used in any `generated/` enquiry — see `docs/ROADMAP.md`.

## Status helper functions (confirmed)

Scalar functions taking the raw `status` bitmask: `StatusIsDraft`, `StatusIsPosted`, `StatusIsAbandoned`, `StatusIsDisputed`, `StatusIsReversed`, `StatusIsOutstanding`, `StatusIsClosed`, `StatusIsPendingAuth`, `StatusIsApproved`, `StatusIsRejected`, `StatusIsWrittenOff`.

## Contacts (confirmed)

`contact_account` (`code`, `description`, `contact_classification_id`, `parent_contact_account_id`); `contact_customer` / `contact_supplier` share the same `id` as `contact_account` and add `credit_limit`, `pay_term_id`, `contact_group_customer_id` / `contact_group_supplier_id`, `is_hold`, `is_stop`.

## Chart of accounts / periods (confirmed)

`account` (`code`, `description`, `name`, `account_type`, `coa_group_id`, flags `ar_flag`/`ap_flag`/`cb_flag`/`control_flag`/`tax_flag`, **and** `last_modified`/`last_modified_by` — confirmed live this session, distinct from `dac_gl`'s) → `coa_group`; `period` (`code`, `date_from`, `date_to`, `financial_year_id`, `is_bf`/`is_cf`/`is_adjustment`) → `financial_year` (`code`, `description`, `date_from`, `date_to`, `financial_year_group_id`, `previous_financial_year_id`) → `financial_year_group`.

## Other reference tables

| Table | Status | Notes |
|---|---|---|
| `legal_entity` (`code`, `description`, `currency`) | Confirmed | |
| `project`, `department`, `cost_centre` | Confirmed to exist as catalogs | Analytic-dimension values on GL/doc lines come via `crv_gl`/`crv_doc_base`, not these tables directly |
| `product` (`code`, `description`) | Confirmed | |
| `tax_code`, `bank_account` | Confirmed to exist | |
| `bank_transaction` | **Inferred** | No `dac_*` equivalent documented; exact column set (especially any currency columns) not confirmed — see `generated/bank/10_bank_transactions_by_account.json` |
| `resource`, `user_account` | Confirmed | `user_account.code` is what catalog attribute `UserAccount` resolves against |
| `budget2` / `budget2_key` / `budget2_value (budget_key_id, period_id, amount)` | **Inferred** | Structure assumed from naming convention; not independently verified |
| `credit_control_note` | Confirmed to exist | Not yet used in `generated/` |

## Standard join fan-out for a GL enquiry (confirmed pattern)

```
g (dac_gl) → a (account) → le (legal_entity) → p (period) → fy (financial_year)
           → cg (crv_gl, left)
           → db (doc_base, left) → dt (doc_type)
                                  → ca (contact_account, left) → cs/cc (contact_supplier/customer, left)
           → prod (product, left)
           → proj (project, left)
```

## When you don't know

Query `INFORMATION_SCHEMA.COLUMNS` (and `sys.objects`/`sys.parameters` for functions) through the same preview-runner mechanism described in `docs/ARCHITECTURE.md`, rather than guessing. If that access isn't available, say the column is unconfirmed and record it in `corpus/unknown_patterns/` — don't silently ship a guess as fact.
