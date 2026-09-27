# iplicit Enquiry — Quick Skill (paste into Project Instructions)

When asked for a custom iplicit enquiry/report, build it, don't ask to browse iplicit for it.

**Model:** an enquiry = `QueryXml` (params + `<Select>` blocks compiling to one `SELECT`) + `PropMetaJson` (column labels/types) + `EnquiryLayouts` (grid/pivot JSON per tab) + `RequiredPermissions` (≥1 attribute-operation GUID, else Create stays disabled). Export/import envelope: `{"type":"DbEnquiry","description","exportDate","data": base64(utf8(json))}` — deliver this, user pastes via **Enquiries > ⋮ > Import from clipboard > Apply**, ticks an analytic group, clicks **Create** themselves.

**Schema:**
- GL lines: `dac_gl` (alias `g`) — `amount` (base), `currency_amount`, `account_id`, `period_id`, `period_date`, `doc_id`, `contact_account_id`, `project_id`, `legal_entity_id`, `last_modified_by`. Analytic dims (Department, CostCentre, Fund, Resource…) come from `LEFT JOIN [generated].[crv_gl] cg ON cg.id=g.id`, not `dac_gl` directly.
- Documents: `dac_doc_base` (alias `db`) — `doc_no`, `doc_date`, `status`, `net/tax/gross_amount` (+`*_currency_amount`), `contact_account_id`, `doc_type_id`. Lines: `doc_detail`. Multiply amounts by `doc_type.mul_control` for correct sign.
- Chart of accounts: `account` (`code`,`description`,`account_type`,`coa_group_id`) — its own `last_modified_by` is the **account master's** audit stamp, different from `dac_gl.last_modified_by` (the posting's). Ask which one is wanted.
- Status checks: `StatusIsDraft/Posted/Abandoned/Disputed/Outstanding/Closed(...)` scalar functions on the `status` bitmask.
- Aged debt/creditors: `dbo.GetAgedDebt(@col,@to_date)` / `GetAgedCreditors`, buckets via `CROSS APPLY dbo.GetIntervalRange(@IntervalId, days)`.
- **Always use `dac_*` views as the principal source**, never the base table — they enforce legal-entity access.

**Params:** `<Param Name Setting="<Setting Attribute=... Catalog=... ValueMember=.../>" .../>`. Optional multi-select filter = `FilterOperator="In" FilterArgument="@X" FilterOr="@X is null"` (always this pair, never bare `In`). Date range = `FilterOperator="Between" FilterArgument="ISNULL(@From,{0}) AND ISNULL(@To,{0})"`. Defaults: `#today`, `#def_legal_entity`, `#def_financial_year_group`, `#user`, sentinel `20000000-0000-0000-0000-000000000000` = current FY.

**Fields:** `Type="Column"` (passthrough), `"Expression"` (computed SQL), `"Summary"` (aggregate — everything non-Summary becomes an implicit GROUP BY key), `"Constant"` (scalar subquery), `Output="False"` (filter-only, not in result).

**Layout:** flat `columns` = list view. Add `groupRows`/`groupColumns`/`groupData` for a pivot; `hierarchy` (saved coa/BS/PL tree) only when the row grouping *is* that tree's structure — don't combine a tree `hierarchy` with an extra `groupRows` field in front of it (returns no data). `includes` must list any field a formatted column depends on (e.g. `currencyMember` target for `amount` viewType).

**Permissions:** always set ≥1 `RequiredPermissions` GUID matching the module (`GeneralLedger.*` for GL, `SaleInvoice.Enquiry`/`Customer.Enquiry` for sales, `PurchaseInvoice.Enquiry`/`Supplier.Enquiry` for purchase, `AR.Enquiry`/`AR.CreditControl`, `Account.Enquiry`, `BankReconciliation.Enquiry`, etc.) — this is the #1 reason a generated enquiry looks broken (Create button stays disabled, no error shown).

**Checklist before handing over:** dac_* principal · optional filters use the In/OrNull pair · date filters use ISNULL/{0} · permission set · sign correct (mul_control) · amount columns' currencyMember is in `includes` · analytic dims via crv_gl/crv_doc_base, not assumed on the base view · no stray non-Summary field forcing an unwanted GROUP BY grain · hierarchy not mixed with extra groupRows levels · union Selects match field-for-field.

Full reference with the generator script, join chains, and 15+ worked example mappings: `IPLICIT_ENQUIRY_MASTER_SKILL.md`.
