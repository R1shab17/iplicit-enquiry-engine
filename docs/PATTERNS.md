# Confirmed pattern catalogue

Mined from 14 real, validated enquiries in `generated/`. Regenerate with `python3 src/build_docs.py` after changing anything there. See `src/patterns.py`'s module docstring for what this catalogue is — and, importantly, is not — a license to do.

## Joins

| Table | Alias | Join type | On | Evidence | Modules | Confirmed via |
|---|---|---|---|---|---|---|
| `dac_doc_base` | `db` | Principal | *(principal)* | 6 | ap, gl, purchasing, sales | ap/09_overdue_purchase_invoices.json, gl/11_manual_journals_by_date.json, gl/12_documents_by_user.json, purchasing/08_purchase_invoices_by_supplier_month.json, sales/06_top_customers_by_revenue.json, sales/14_credit_notes_by_period.json |
| `contact_account` | `ca` | InnerJoin | `[ca].[id] = [db].[contact_account_id]` | 5 | ap, ar, purchasing, sales | ap/07_aged_creditors_by_supplier.json, ap/09_overdue_purchase_invoices.json, ar/05_aged_debtors_by_customer.json, purchasing/08_purchase_invoices_by_supplier_month.json, sales/06_top_customers_by_revenue.json |
| `dac_gl` | `g` | Principal | *(principal)* | 5 | budgets, gl | budgets/13_budget_vs_actual.json, gl/01_gl_trial_balance.json, gl/02_gl_detail_by_nominal.json, gl/03_balance_sheet_by_department_nominal.json, gl/04_pl_by_month.json |
| `account` | `a` | InnerJoin | `[a].[id] = [g].[account_id]` | 4 | gl | gl/01_gl_trial_balance.json, gl/02_gl_detail_by_nominal.json, gl/03_balance_sheet_by_department_nominal.json, gl/04_pl_by_month.json |
| `crv_gl` | `cg` | LeftJoin | `[g].[id] = [cg].[id]` | 3 | budgets, gl | budgets/13_budget_vs_actual.json, gl/02_gl_detail_by_nominal.json, gl/03_balance_sheet_by_department_nominal.json |
| `dac_doc_base` | `db` | InnerJoin | `[db].[id] = [r].[id]` | 2 | ap, ar | ap/07_aged_creditors_by_supplier.json, ar/05_aged_debtors_by_customer.json |
| `doc_type` | `dt` | InnerJoin | `[dt].[id] = [db].[doc_type_id] AND [dt].[is_purchase] = 1` | 2 | ap, purchasing | ap/09_overdue_purchase_invoices.json, purchasing/08_purchase_invoices_by_supplier_month.json |
| `period` | `p` | InnerJoin | `[p].[id] = [g].[period_id]` | 2 | gl | gl/01_gl_trial_balance.json, gl/04_pl_by_month.json |
| `bank_account` | `ba` | InnerJoin | `[ba].[id] = [bt].[bank_account_id]` | 1 | bank | bank/10_bank_transactions_by_account.json |
| `bank_transaction` | `bt` | Principal | *(principal)* | 1 | bank | bank/10_bank_transactions_by_account.json |
| `budget2_key` | `bk` | InnerJoin | `[bk].[id] = [bv].[budget_key_id]` | 1 | budgets | budgets/13_budget_vs_actual.json |
| `budget2_value` | `bv` | Principal | *(principal)* | 1 | budgets | budgets/13_budget_vs_actual.json |
| `contact_account` | `ca` | LeftJoin | `[ca].[id] = [db].[contact_account_id]` | 1 | sales | sales/14_credit_notes_by_period.json |
| `dac_doc_base` | `db` | LeftJoin | `[db].[id] = [g].[doc_id]` | 1 | gl | gl/02_gl_detail_by_nominal.json |
| `doc_outstanding` | `do_` | InnerJoin | `[do_].[id] = [db].[id]` | 1 | ap | ap/09_overdue_purchase_invoices.json |
| `doc_type` | `dt` | InnerJoin | `[dt].[id] = [db].[doc_type_id] AND [dt].[is_gl] = 1` | 1 | gl | gl/11_manual_journals_by_date.json |
| `doc_type` | `dt` | InnerJoin | `[dt].[id] = [db].[doc_type_id] AND [dt].[is_sale] = 1` | 1 | sales | sales/06_top_customers_by_revenue.json |
| `doc_type` | `dt` | InnerJoin | `[dt].[id] = [db].[doc_type_id] AND [dt].[is_credit_note] = 1` | 1 | sales | sales/14_credit_notes_by_period.json |
| `legal_entity` | `le` | InnerJoin | `[le].[id] = [g].[legal_entity_id]` | 1 | gl | gl/01_gl_trial_balance.json |
| `select * from [dbo].[GetAgedCreditors]('due_date', @AsOfDate) r` | `r` | Principal | *(principal)* | 1 | ap | ap/07_aged_creditors_by_supplier.json |
| `select * from [dbo].[GetAgedDebt]('due_date', @AsOfDate) r` | `r` | Principal | *(principal)* | 1 | ar | ar/05_aged_debtors_by_customer.json |

## Fields (columns/expressions/summaries confirmed available per table)

| Type | Table | Alias | SQL | Evidence | Modules |
|---|---|---|---|---|---|
| Column | dac_doc_base | db | `legal_entity_id` | 8 | ap, ar, gl, purchasing, sales |
| Column | contact_account | ca | `id` | 6 | ap, ar, purchasing, sales |
| Column | contact_account | ca | `description` | 6 | ap, ar, purchasing, sales |
| Column | dac_doc_base | db | `doc_no` | 6 | ap, ar, gl, sales |
| Column | dac_doc_base | db | `base_currency` | 5 | ap, gl, purchasing, sales |
| Column | dac_gl | g | `account_id` | 5 | budgets, gl |
| Summary | - | - | `SUM([g].[amount])` | 4 | budgets, gl |
| Column | dac_doc_base | db | `doc_date` | 4 | gl, sales |
| Column | dac_gl | g | `legal_entity_id` | 4 | gl |
| Column | dac_gl | g | `base_currency` | 4 | gl |
| Column | dac_doc_base | db | `due_date` | 3 | ap, ar |
| Summary | - | r | `cur_outs_amount` | 2 | ap, ar |
| Summary | - | - | `SUM([db].[net_amount] * [dt].[mul_control])` | 2 | purchasing, sales |
| Column | account | a | `account_type` | 2 | gl |
| Column | crv_gl | cg | `CostCentre` | 2 | budgets, gl |
| Column | crv_gl | cg | `Department` | 2 | gl |
| Column | dac_doc_base | db | `description` | 2 | gl |
| Column | dac_doc_base | db | `created_by` | 2 | gl |
| Column | dac_gl | g | `period_id` | 2 | budgets, gl |
| Summary | - | - | `SUM([bv].[amount])` | 1 | budgets |
| Constant | - | - | `0` | 1 | budgets |
| Summary | - | - | `CASE WHEN SUM([g].[amount]) > 0 THEN SUM([g].[amount]) ELSE 0 END` | 1 | gl |
| Summary | - | - | `CASE WHEN SUM([g].[amount]) < 0 THEN -SUM([g].[amount]) ELSE 0 END` | 1 | gl |
| Expression | - | - | `FORMAT([p].[date_from],'yyyy-MM')` | 1 | gl |
| Expression | - | - | `FORMAT([db].[doc_date],'yyyy-MM')` | 1 | purchasing |
| Expression | - | - | `[db].[gross_amount] * [dt].[mul_control]` | 1 | sales |
| Column | account | a | `code` | 1 | gl |
| Column | account | a | `description` | 1 | gl |
| Column | bank_account | ba | `code` | 1 | bank |
| Column | bank_transaction | bt | `bank_account_id` | 1 | bank |
| Column | bank_transaction | bt | `trans_date` | 1 | bank |
| Column | bank_transaction | bt | `description` | 1 | bank |
| Column | bank_transaction | bt | `amount` | 1 | bank |
| Column | budget2_key | bk | `account_id` | 1 | budgets |
| Column | budget2_key | bk | `cost_centre` | 1 | budgets |
| Column | budget2_value | bv | `period_id` | 1 | budgets |
| Column | contact_account | ca | `code` | 1 | ar |
| Column | dac_doc_base | db | `net_amount` | 1 | gl |
| Column | dac_gl | g | `period_date` | 1 | gl |
| Column | dac_gl | g | `doc_no` | 1 | gl |
| Column | dac_gl | g | `doc_id` | 1 | gl |
| Column | dac_gl | g | `description` | 1 | gl |
| Column | dac_gl | g | `contact_account_id` | 1 | gl |
| Column | dac_gl | g | `currency_amount` | 1 | gl |
| Column | dac_gl | g | `amount` | 1 | gl |
| Column | dac_gl | g | `currency` | 1 | gl |
| Column | dac_gl | g | `last_modified_by` | 1 | gl |
| Column | doc_outstanding | do_ | `cur_outs_amount` | 1 | ap |
| Column | period | p | `financial_year_id` | 1 | gl |

## Filter idioms

| Shape | Operator | Example argument | Example OR clause | Evidence | Modules |
|---|---|---|---|---|---|
| `multi_select_in_or_null` | In | `@LegalEntityId` | `@LegalEntityId is null` | 14 | ap, ar, bank, budgets, gl, purchasing, sales |
| `between_isnull_date_range` | Between | `ISNULL(@DateFrom,{0}) AND ISNULL(@DateTo,{0})` | `None` | 5 | bank, gl, sales |
| `equal_param` | Equal | `@Currency` | `None` | 3 | gl |
| `equal_literal` | Equal | `'BS'` | `None` | 2 | gl |
| `comparison_against_param` | Less | `@AsOfDate` | `None` | 1 | ap |
| `not_equal_literal` | NotEqual | `0` | `None` | 1 | ap |

## Parameters

| Attribute | Value type | Presenter | Value member | Catalog | Evidence | Modules |
|---|---|---|---|---|---|---|
| LegalEntity | Text | MultiGit | ObjectId | - | 12 | ap, ar, gl, purchasing, sales |
| *(none — plain value)* | Date | Date | - | - | 8 | ap, ar, bank, gl, sales |
| Currency | Text | MultiGit | Code | - | 3 | gl |
| BankAccount | Text | MultiGit | ObjectId | - | 1 | bank |
| Period | Text | MultiGit | ObjectId | - | 1 | budgets |
| FinancialYearGroup | Guid | MultiGit | ObjectId | FinancialYearGroupForLegalEntity | 1 | gl |
| Period | Text | MultiGit | ObjectId | PeriodsForFYG_FY_LE | 1 | gl |
| Account | Text | MultiGit | ObjectId | - | 1 | gl |
| FinancialYear | Text | MultiGit | ObjectId | FinancialYearsForGroupOrDefaults | 1 | gl |

## Layout shapes

| Shape | Evidence | Modules | Confirmed via |
|---|---|---|---|
| `flat_list` | 6 | ap, bank, gl, sales | ap/09_overdue_purchase_invoices.json, bank/10_bank_transactions_by_account.json, gl/02_gl_detail_by_nominal.json, gl/11_manual_journals_by_date.json, gl/12_documents_by_user.json, sales/14_credit_notes_by_period.json |
| `grouped_rows` | 4 | budgets, gl, sales | budgets/13_budget_vs_actual.json, gl/01_gl_trial_balance.json, gl/03_balance_sheet_by_department_nominal.json, sales/06_top_customers_by_revenue.json |
| `grouped_rows_with_drilldown` | 2 | ap, ar | ap/07_aged_creditors_by_supplier.json, ar/05_aged_debtors_by_customer.json |
| `hierarchy_pivot` | 1 | gl | gl/04_pl_by_month.json |
| `grouped_rows_and_column_pivot` | 1 | purchasing | purchasing/08_purchase_invoices_by_supplier_month.json |

## Permissions

| Name | GUID | Evidence | Modules |
|---|---|---|---|
| Supplier.Enquiry | `9b4a71b5-8d55-420f-a876-4f8df2c1e7be` | 3 | ap, purchasing |
| AR.Enquiry | `f15cfadc-7a9f-4443-8492-a8a1581b0d5f` | 2 | ap, ar |
| PurchaseInvoice.Enquiry | `cf0ef798-1361-4d9d-8b8a-8cb7afd2ca33` | 2 | ap, purchasing |
| Customer.Enquiry | `dc6ff301-e2d6-4933-8cef-3347f7ddd177` | 2 | ar, sales |
| SaleInvoice.Enquiry | `39e3b643-9552-457d-b402-82c2e9db6b71` | 2 | sales |
| Cashbook.Enquiry | `c212b965-02c9-4a27-a8c4-f9869d4adc84` | 1 | bank |
| BudgetForecast.Enquiry | `af31aa72-1f3d-4352-9216-f4849a2b5166` | 1 | budgets |
| GeneralLedger.TrialBalance | `57257282-a05b-49ea-a625-1aee2bf5f941` | 1 | gl |
| GeneralLedger.Enquiry | `693b164b-b59f-4946-97b7-cd01465847a7` | 1 | gl |
| GeneralLedger.BalanceSheet | `f4eb155f-d660-46b2-a84e-47395efd2a82` | 1 | gl |
| GeneralLedger.ProfitLoss | `fc25f7a9-2a3c-471a-8a4e-6dd29434f3d9` | 1 | gl |
| ManualJournal.Enquiry | `20df7f94-fc51-4a48-8d65-9d88f7075954` | 1 | gl |
| DocBase.Enquiry | `8891d6f9-6d92-4612-b367-d526c57f5a8d` | 1 | gl |

