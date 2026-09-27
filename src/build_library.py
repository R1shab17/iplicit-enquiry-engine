"""
Build the library of ready-to-import iplicit enquiries using enqgen.py.

Each `enquiry_NN_name()` function below is the single source of truth for
one confirmed report shape: it returns everything `build()` needs (params,
selects, propmeta, layouts, permissions) plus the filename/description/
notes used when writing it into generated/. Nothing about these functions
depends on where they're called from — that's deliberate. `main()` below
calls all 14 and writes them into ../generated/<module>/; src/templates.py
calls the *same* functions to serve the customer-facing report builder
(tools/enquiry_builder_app.py), so the two never drift apart the way a
second, hand-copied implementation would.

Regenerate after editing any function below, then re-validate before
trusting the new output:

    python3 build_library.py
    python3 enquiry_validator.py ../generated/**/*.json

Importing this module (`import build_library`) never writes anything —
only running it as a script (or calling main() explicitly) does.
"""
import os
import json

from enqgen import *  # noqa: F401,F403 — param/src/fld/multi_filter/query_xml/meta/m_*/layout/build/PERM/setting

GENERATED = os.path.join(os.path.dirname(__file__), "..", "generated")

LE_PARAM = param("LegalEntityId", "Legal entity", setting_xml=setting("LegalEntity"))
CUR_PARAM = param("Currency", "Currency", setting_xml=setting("Currency", value_member="Code"), default="#def_cur_code", mandatory=True)


# ---------------------------------------------------------------- 1. Trial balance
def enquiry_01_gl_trial_balance():
    P = [LE_PARAM,
         param("FinancialYearGroupId", "Financial year group", "Guid",
               setting_xml=setting("FinancialYearGroup", catalog="FinancialYearGroupForLegalEntity",
                                    # Binding Name must be the actual declared Param name the value comes
                                    # from (LegalEntityId), not the PropertyName-style label ("LegalEntity")
                                    # — fixed 2026-09-27 after src/ir.py's cross-reference check flagged this
                                    # binding as pointing at an undeclared param. See docs/DISCOVERED_FAILURE_MODES.md #2.
                                    bindings=[("LegalEntityId", "Text", "LegalEntity")]),
               default="#def_financial_year_group"),
         param("PeriodId", "Period", setting_xml=setting("Period", catalog="PeriodsForFYG_FY_LE",
               bindings=[("FinancialYearGroupId", "Guid", "FinancialYearGroup"), ("LegalEntityId", "Text", "LegalEntity")])),
         CUR_PARAM]
    S = [{"name": "Main", "sources": [
            src("g", "[dbo].[dac_gl]", "View"),
            src("a", "[dbo].[account]", join="InnerJoin", on="[a].[id] = [g].[account_id]"),
            src("le", "[dbo].[legal_entity]", join="InnerJoin", on="[le].[id] = [g].[legal_entity_id]"),
            src("p", "[dbo].[period]", join="InnerJoin", on="[p].[id] = [g].[period_id]"),
         ], "fields": [
            fld("LegalEntityId", "legal_entity_id", "g", op="In", arg="@LegalEntityId", orr="@LegalEntityId is null", output=False),
            fld("PeriodId", "period_id", "g", op="In", arg="@PeriodId", orr="@PeriodId is null", output=False),
            fld("AccountId", "account_id", "g"),
            fld("AccountCode", "code", "a"),
            fld("AccountDescription", "description", "a"),
            fld("Debit", "CASE WHEN SUM([g].[amount]) > 0 THEN SUM([g].[amount]) ELSE 0 END", type="Summary"),
            fld("Credit", "CASE WHEN SUM([g].[amount]) < 0 THEN -SUM([g].[amount]) ELSE 0 END", type="Summary"),
            fld("Balance", "SUM([g].[amount])", type="Summary"),
            fld("BaseCurrency", "base_currency", "g", op="Equal", arg="@Currency"),
         ]}]
    M = {"AccountId": m_catalog("AccountId", "Account", "Account", 220),
         "AccountCode": m_text("AccountCode", "Code", 90),
         "AccountDescription": m_text("AccountDescription", "Description", 220),
         "Debit": m_amount("Debit", "Debit"), "Credit": m_amount("Credit", "Credit"), "Balance": m_amount("Balance", "Balance"),
         "BaseCurrency": m_text("BaseCurrency", "Base currency", 60)}
    L = [layout("Trial balance", ["AccountCode", "AccountDescription", "Debit", "Credit", "Balance"],
                group_rows=[{"field": "AccountId", "sticky": True}], group_data=[{"field": "Balance", "aggregator": "sum"}],
                includes=["BaseCurrency"])]
    return dict(
        filename="gl/01_gl_trial_balance.json",
        description="Trial balance by legal entity and period",
        group="GL", params=P, selects=S, propmeta=M, layouts=L,
        permissions=[PERM["GeneralLedger.TrialBalance"]],
        notes="Debit/Credit split derived from the base-currency Amount sign; Balance = net. LegalEntityId/PeriodId are "
              "filter-only (Output=False) so they don't force a finer implicit GROUP BY than 'one row per account'.",
    )


# ---------------------------------------------------------------- 2. GL detail with dims
def enquiry_02_gl_detail_by_nominal():
    P = [LE_PARAM,
         param("AccountId", "Account", setting_xml=setting("Account", filter="Extra.account_type IS NOT NULL")),
         param("DateFrom", "Date from", "Date", "Date"), param("DateTo", "Date to", "Date", "Date", default="#today")]
    S = [{"name": "Main", "sources": [
            src("g", "[dbo].[dac_gl]", "View"),
            src("a", "[dbo].[account]", join="InnerJoin", on="[a].[id] = [g].[account_id]"),
            src("cg", "[generated].[crv_gl]", join="LeftJoin", on="[g].[id] = [cg].[id]"),
            src("db", "[dbo].[dac_doc_base]", join="LeftJoin", on="[db].[id] = [g].[doc_id]"),
         ], "fields": [
            multi_filter("LegalEntityId", "legal_entity_id", "g", "LegalEntityId"),
            multi_filter("AccountId", "account_id", "g", "AccountId"),
            fld("PeriodDate", "period_date", "g", op="Between", arg="ISNULL(@DateFrom,{0}) AND ISNULL(@DateTo,{0})"),
            fld("DocNo", "doc_no", "g"), fld("DocId", "doc_id", "g"),
            fld("Description", "description", "g"),
            fld("Department", "Department", "cg"), fld("CostCentre", "CostCentre", "cg"),
            fld("ContactAccountId", "contact_account_id", "g"),
            fld("CurrencyAmount", "currency_amount", "g"), fld("Amount", "amount", "g"),
            fld("Currency", "currency", "g"), fld("BaseCurrency", "base_currency", "g"),
            fld("LastModifiedBy", "last_modified_by", "g"),
         ]}]
    M = {"LegalEntityId": m_catalog("LegalEntityId", "Legal entity", "LegalEntity", 160),
         "AccountId": m_catalog("AccountId", "Account", "Account", 220),
         "PeriodDate": m_date("PeriodDate", "Date"), "DocNo": m_link("DocNo", "Doc no"),
         "DocId": meta("DocId", "Doc", "guid", None), "Description": m_text("Description", "Description", 220),
         "Department": m_text("Department", "Department", 100), "CostCentre": m_text("CostCentre", "Cost centre", 100),
         "ContactAccountId": m_catalog("ContactAccountId", "Contact account", "ContactAccount", 180),
         "CurrencyAmount": m_amount("CurrencyAmount", "Amount (currency)", "Currency"),
         "Amount": m_amount("Amount", "Amount"), "Currency": m_text("Currency", "Currency", 60),
         "BaseCurrency": m_text("BaseCurrency", "Base currency", 60),
         "LastModifiedBy": meta("LastModifiedBy", "Last modified by", "text", "catalog", 120, attribute="UserAccount", valueMember="Code")}
    L = [layout("GL detail", ["PeriodDate", "DocNo", "Description", "Department", "CostCentre", "ContactAccountId", "Amount"],
                includes=["DocId", "Currency", "BaseCurrency"], sort_by=[{"field": "PeriodDate", "descending": True}])]
    return dict(
        filename="gl/02_gl_detail_by_nominal.json",
        description="GL detail by nominal (with department & cost centre)",
        group="GL", params=P, selects=S, propmeta=M, layouts=L,
        permissions=[PERM["GeneralLedger.Enquiry"]],
        notes="Flat list (no Summary fields), so extra Column fields don't distort grouping. Department/CostCentre pulled via crv_gl left join.",
    )


# ---------------------------------------------------------------- 3. Balance sheet by department & nominal
def enquiry_03_balance_sheet_by_department_nominal():
    P = [LE_PARAM, CUR_PARAM]
    S = [{"name": "Main", "sources": [
            src("g", "[dbo].[dac_gl]", "View"),
            src("a", "[dbo].[account]", join="InnerJoin", on="[a].[id] = [g].[account_id]"),
            src("cg", "[generated].[crv_gl]", join="LeftJoin", on="[g].[id] = [cg].[id]"),
         ], "fields": [
            fld("LegalEntityId", "legal_entity_id", "g", op="In", arg="@LegalEntityId", orr="@LegalEntityId is null", output=False),
            fld("AccountType", "account_type", "a", op="Equal", arg="'BS'", output=False),
            fld("AccountId", "account_id", "g"), fld("Department", "Department", "cg"),
            fld("BaseCurrency", "base_currency", "g", op="Equal", arg="@Currency"),
            fld("Balance", "SUM([g].[amount])", type="Summary"),
         ]}]
    M = {"AccountId": m_catalog("AccountId", "Account", "Account", 240), "Department": m_text("Department", "Department", 100),
         "BaseCurrency": m_text("BaseCurrency", "Base currency", 60), "Balance": m_amount("Balance", "Balance")}
    L = [layout("Department & Nominal", ["AccountId", "Department", "Balance"],
                group_rows=[{"field": "Department", "sticky": True}, {"field": "AccountId", "sticky": True}],
                group_data=[{"field": "Balance", "aggregator": "sum"}], includes=["BaseCurrency"])]
    return dict(
        filename="gl/03_balance_sheet_by_department_nominal.json",
        description="Balance sheet by department and nominal",
        group="GL", params=P, selects=S, propmeta=M, layouts=L,
        permissions=[PERM["GeneralLedger.BalanceSheet"]],
        notes="No 'hierarchy' tree — deliberately, since it conflicts with the 2-level groupRows (confirmed this session). "
              "LegalEntityId/AccountType are filter-only. Reusable, parameterised version of the one built earlier in this conversation.",
    )


# ---------------------------------------------------------------- 4. P&L by month
def enquiry_04_pl_by_month():
    P = [LE_PARAM, CUR_PARAM,
         param("FinancialYear", "Financial year", setting_xml=setting("FinancialYear", catalog="FinancialYearsForGroupOrDefaults"))]
    S = [{"name": "Main", "sources": [
            src("g", "[dbo].[dac_gl]", "View"),
            src("a", "[dbo].[account]", join="InnerJoin", on="[a].[id] = [g].[account_id]"),
            src("p", "[dbo].[period]", join="InnerJoin", on="[p].[id] = [g].[period_id]"),
         ], "fields": [
            fld("LegalEntityId", "legal_entity_id", "g", op="In", arg="@LegalEntityId", orr="@LegalEntityId is null", output=False),
            fld("FinancialYearId", "financial_year_id", "p", op="In", arg="@FinancialYear", orr="@FinancialYear is null", output=False),
            fld("AccountType", "account_type", "a", op="Equal", arg="'PL'", output=False),
            fld("AccountId", "account_id", "g"),
            fld("Month", "FORMAT([p].[date_from],'yyyy-MM')", type="Expression"),
            fld("BaseCurrency", "base_currency", "g", op="Equal", arg="@Currency"),
            fld("Amount", "SUM([g].[amount])", type="Summary"),
         ]}]
    M = {"AccountId": m_catalog("AccountId", "Account", "Account", 240), "Month": m_text("Month", "Month", 80),
         "BaseCurrency": m_text("BaseCurrency", "Base currency", 60), "Amount": m_amount("Amount", "Amount")}
    L = [layout("P&L by month", ["AccountId", "Amount"], group_rows=[{"field": "AccountId", "sticky": True}],
                group_columns=[{"field": "Month", "total": True}], group_data=[{"field": "Amount", "aggregator": "sum"}],
                includes=["BaseCurrency"],
                extra={"hierarchy": {"treeId": "STANDARD_PL_TREE_ID_REPLACE_ME", "name": "Standard P&L tree"}})]
    return dict(
        filename="gl/04_pl_by_month.json",
        description="Profit & loss by month",
        group="GL", params=P, selects=S, propmeta=M, layouts=L,
        permissions=[PERM["GeneralLedger.ProfitLoss"]],
        notes="Uses a P&L tree hierarchy on a SINGLE-level groupRows (AccountId only) — safe combination, unlike #3. "
              "treeId is a placeholder: replace with your tenant's actual P&L tree id (Export any existing P&L enquiry to find it), "
              "or delete the hierarchy key for a flat grouping.",
    )


# ---------------------------------------------------------------- 5. Aged debtors
def enquiry_05_aged_debtors_by_customer():
    P = [LE_PARAM, param("AsOfDate", "As of date", "Date", "Date", default="#today")]
    S = [{"name": "Main", "sources": [
            src("r", "select * from [dbo].[GetAgedDebt]('due_date', @AsOfDate) r", "Sql", "Principal"),
            src("db", "[dbo].[dac_doc_base]", join="InnerJoin", on="[db].[id] = [r].[id]"),
            src("ca", "[dbo].[contact_account]", join="InnerJoin", on="[ca].[id] = [db].[contact_account_id]"),
         ], "fields": [
            fld("LegalEntityId", "legal_entity_id", "db", op="In", arg="@LegalEntityId", orr="@LegalEntityId is null", output=False),
            fld("ContactAccountId", "id", "ca"), fld("ContactAccountCode", "code", "ca"),
            fld("ContactAccountDescription", "description", "ca"),
            fld("DocNo", "doc_no", "db"), fld("DueDate", "due_date", "db"),
            fld("Outstanding", "cur_outs_amount", "r", type="Summary"),
         ]}]
    M = {"ContactAccountId": m_catalog("ContactAccountId", "Customer", "Customer", 200),
         "ContactAccountCode": m_text("ContactAccountCode", "Code", 90),
         "ContactAccountDescription": m_text("ContactAccountDescription", "Name", 220),
         "DocNo": m_link("DocNo", "Doc no"), "DueDate": m_date("DueDate", "Due date"),
         "Outstanding": m_decimal("Outstanding", "Outstanding")}
    L = [layout("Aged debtors", ["ContactAccountCode", "ContactAccountDescription", "Outstanding"],
                group_rows=[{"field": "ContactAccountId", "sticky": True}], group_data=[{"field": "Outstanding", "aggregator": "sum"}],
                detail={"columns": ["DocNo", "DueDate", "Outstanding"], "sortBy": [{"field": "DueDate", "descending": False}]})]
    return dict(
        filename="ar/05_aged_debtors_by_customer.json",
        description="Aged debtors by customer",
        group="AR", params=P, selects=S, propmeta=M, layouts=L,
        permissions=[PERM["AR.Enquiry"], PERM["Customer.Enquiry"]],
        notes="Uses dbo.GetAgedDebt as principal Sql source per the master skill's documented pattern. Outstanding uses plain "
              "'decimal' viewType, not 'amount', because GetAgedDebt's currency columns aren't confirmed — verify before "
              "switching to amount+currencyMember. For bucketed ageing (0-30/31-60/...), add CROSS APPLY "
              "dbo.GetIntervalRange(@IntervalId, days) and group by its 'range' column.",
    )


# ---------------------------------------------------------------- 6. Top customers by revenue
def enquiry_06_top_customers_by_revenue():
    P = [LE_PARAM, param("DateFrom", "Date from", "Date", "Date"), param("DateTo", "Date to", "Date", "Date", default="#today")]
    S = [{"name": "Main", "sources": [
            src("db", "[dbo].[dac_doc_base]", "View"),
            src("dt", "[dbo].[doc_type]", join="InnerJoin", on="[dt].[id] = [db].[doc_type_id] AND [dt].[is_sale] = 1"),
            src("ca", "[dbo].[contact_account]", join="InnerJoin", on="[ca].[id] = [db].[contact_account_id]"),
         ], "fields": [
            fld("LegalEntityId", "legal_entity_id", "db", op="In", arg="@LegalEntityId", orr="@LegalEntityId is null", output=False),
            fld("DocDate", "doc_date", "db", op="Between", arg="ISNULL(@DateFrom,{0}) AND ISNULL(@DateTo,{0})", output=False),
            fld("ContactAccountId", "id", "ca"), fld("ContactAccountDescription", "description", "ca"),
            fld("BaseCurrency", "base_currency", "db"),
            fld("Revenue", "SUM([db].[net_amount] * [dt].[mul_control])", type="Summary"),
         ]}]
    M = {"ContactAccountId": m_catalog("ContactAccountId", "Customer", "Customer", 220),
         "ContactAccountDescription": m_text("ContactAccountDescription", "Name", 220),
         "BaseCurrency": m_text("BaseCurrency", "Base currency", 60), "Revenue": m_amount("Revenue", "Revenue")}
    L = [layout("Top customers", ["ContactAccountDescription", "Revenue"],
                group_rows=[{"field": "ContactAccountId", "sticky": True}], group_data=[{"field": "Revenue", "aggregator": "sum"}],
                includes=["BaseCurrency"], sort_by=[{"field": "Revenue", "descending": True}])]
    return dict(
        filename="sales/06_top_customers_by_revenue.json",
        description="Top customers by revenue",
        group="Sale", params=P, selects=S, propmeta=M, layouts=L,
        permissions=[PERM["SaleInvoice.Enquiry"], PERM["Customer.Enquiry"]],
        notes="DocDate is filter-only (Output=False) — as a raw Column it would otherwise force grouping by (customer, date) "
              "instead of a single total per customer across the whole range. Ranking/'top N' is done by sorting the grid "
              "descending, not a SQL TOP-per-group.",
    )


# ---------------------------------------------------------------- 7. Aged creditors
def enquiry_07_aged_creditors_by_supplier():
    P = [LE_PARAM, param("AsOfDate", "As of date", "Date", "Date", default="#today")]
    S = [{"name": "Main", "sources": [
            src("r", "select * from [dbo].[GetAgedCreditors]('due_date', @AsOfDate) r", "Sql", "Principal"),
            src("db", "[dbo].[dac_doc_base]", join="InnerJoin", on="[db].[id] = [r].[id]"),
            src("ca", "[dbo].[contact_account]", join="InnerJoin", on="[ca].[id] = [db].[contact_account_id]"),
         ], "fields": [
            fld("LegalEntityId", "legal_entity_id", "db", op="In", arg="@LegalEntityId", orr="@LegalEntityId is null", output=False),
            fld("ContactAccountId", "id", "ca"), fld("ContactAccountDescription", "description", "ca"),
            fld("DocNo", "doc_no", "db"), fld("DueDate", "due_date", "db"),
            fld("Outstanding", "cur_outs_amount", "r", type="Summary"),
         ]}]
    M = {"ContactAccountId": m_catalog("ContactAccountId", "Supplier", "Supplier", 220),
         "ContactAccountDescription": m_text("ContactAccountDescription", "Name", 220),
         "DocNo": m_link("DocNo", "Doc no"), "DueDate": m_date("DueDate", "Due date"),
         "Outstanding": m_decimal("Outstanding", "Outstanding")}
    L = [layout("Aged creditors", ["ContactAccountDescription", "Outstanding"],
                group_rows=[{"field": "ContactAccountId", "sticky": True}], group_data=[{"field": "Outstanding", "aggregator": "sum"}],
                detail={"columns": ["DocNo", "DueDate", "Outstanding"], "sortBy": [{"field": "DueDate", "descending": False}]})]
    return dict(
        filename="ap/07_aged_creditors_by_supplier.json",
        description="Aged creditors by supplier",
        group="AP", params=P, selects=S, propmeta=M, layouts=L,
        permissions=[PERM["AR.Enquiry"], PERM["Supplier.Enquiry"]],
        notes="Mirror of #5 using GetAgedCreditors. Permission list reuses AR.Enquiry pending confirmation of a dedicated "
              "AP.Enquiry id in your tenant.",
    )


# ---------------------------------------------------------------- 8. Purchase invoices by supplier by month
def enquiry_08_purchase_invoices_by_supplier_month():
    P = [LE_PARAM]
    S = [{"name": "Main", "sources": [
            src("db", "[dbo].[dac_doc_base]", "View"),
            src("dt", "[dbo].[doc_type]", join="InnerJoin", on="[dt].[id] = [db].[doc_type_id] AND [dt].[is_purchase] = 1"),
            src("ca", "[dbo].[contact_account]", join="InnerJoin", on="[ca].[id] = [db].[contact_account_id]"),
         ], "fields": [
            fld("LegalEntityId", "legal_entity_id", "db", op="In", arg="@LegalEntityId", orr="@LegalEntityId is null", output=False),
            fld("ContactAccountId", "id", "ca"), fld("ContactAccountDescription", "description", "ca"),
            fld("Month", "FORMAT([db].[doc_date],'yyyy-MM')", type="Expression"),
            fld("BaseCurrency", "base_currency", "db"),
            fld("NetAmount", "SUM([db].[net_amount] * [dt].[mul_control])", type="Summary"),
         ]}]
    M = {"ContactAccountId": m_catalog("ContactAccountId", "Supplier", "Supplier", 220),
         "ContactAccountDescription": m_text("ContactAccountDescription", "Name", 220),
         "Month": m_text("Month", "Month", 80), "BaseCurrency": m_text("BaseCurrency", "Base currency", 60),
         "NetAmount": m_amount("NetAmount", "Net")}
    L = [layout("By supplier", ["ContactAccountDescription", "NetAmount"], group_rows=[{"field": "ContactAccountId", "sticky": True}],
                group_columns=[{"field": "Month", "total": True}], group_data=[{"field": "NetAmount", "aggregator": "sum"}],
                includes=["BaseCurrency"])]
    return dict(
        filename="purchasing/08_purchase_invoices_by_supplier_month.json",
        description="Purchase invoices by supplier by month",
        group="Purchase", params=P, selects=S, propmeta=M, layouts=L,
        permissions=[PERM["PurchaseInvoice.Enquiry"], PERM["Supplier.Enquiry"]],
        notes="Direct mirror of the tested 'Sales by customer by month' pattern, swapped to is_purchase / Supplier.",
    )


# ---------------------------------------------------------------- 9. Overdue purchase invoices
def enquiry_09_overdue_purchase_invoices():
    P = [LE_PARAM, param("AsOfDate", "As of date", "Date", "Date", default="#today")]
    S = [{"name": "Main", "sources": [
            src("db", "[dbo].[dac_doc_base]", "View"),
            src("dt", "[dbo].[doc_type]", join="InnerJoin", on="[dt].[id] = [db].[doc_type_id] AND [dt].[is_purchase] = 1"),
            src("do_", "[dbo].[doc_outstanding]", join="InnerJoin", on="[do_].[id] = [db].[id]"),
            src("ca", "[dbo].[contact_account]", join="InnerJoin", on="[ca].[id] = [db].[contact_account_id]"),
         ], "fields": [
            fld("LegalEntityId", "legal_entity_id", "db", op="In", arg="@LegalEntityId", orr="@LegalEntityId is null", output=False),
            fld("DueDateFilter", "due_date", "db", op="Less", arg="@AsOfDate", output=False),
            fld("ContactAccountId", "id", "ca"), fld("ContactAccountDescription", "description", "ca"),
            fld("DocNo", "doc_no", "db"), fld("DueDate", "due_date", "db"),
            fld("BaseCurrency", "base_currency", "db"),
            fld("Outstanding", "cur_outs_amount", "do_"),
            fld("HasOutstanding", "cur_outs_amount", "do_", op="NotEqual", arg="0", output=False),
         ]}]
    M = {"ContactAccountId": m_catalog("ContactAccountId", "Supplier", "Supplier", 220),
         "ContactAccountDescription": m_text("ContactAccountDescription", "Name", 220),
         "DocNo": m_link("DocNo", "Doc no"), "DueDate": m_date("DueDate", "Due date"),
         "BaseCurrency": m_text("BaseCurrency", "Base currency", 60), "Outstanding": m_amount("Outstanding", "Outstanding")}
    L = [layout("Overdue", ["ContactAccountDescription", "DocNo", "DueDate", "Outstanding"],
                includes=["BaseCurrency"], sort_by=[{"field": "DueDate", "descending": False}])]
    return dict(
        filename="ap/09_overdue_purchase_invoices.json",
        description="Overdue purchase invoices",
        group="Purchase", params=P, selects=S, propmeta=M, layouts=L,
        permissions=[PERM["PurchaseInvoice.Enquiry"], PERM["Supplier.Enquiry"]],
        notes="Flat list: due_date < AsOfDate AND still outstanding (HasOutstanding filter-only field). Not aged into buckets — see #7.",
    )


# ---------------------------------------------------------------- 10. Bank transactions by account
def enquiry_10_bank_transactions_by_account():
    # No LegalEntityId param here (deliberately, fixed 2026-09-27): neither
    # bank_transaction nor bank_account has a confirmed legal_entity_id column
    # (docs/SCHEMA.md), so a Legal entity picker would render with no effect —
    # a dead parameter, caught by src/ir.py's unused-param check. See
    # docs/DISCOVERED_FAILURE_MODES.md #1. Re-add it once that column is confirmed.
    P = [param("BankAccountId", "Bank account", setting_xml=setting("BankAccount")),
         param("DateFrom", "Date from", "Date", "Date"), param("DateTo", "Date to", "Date", "Date", default="#today")]
    S = [{"name": "Main", "sources": [
            src("bt", "[dbo].[bank_transaction]", "Table"),
            src("ba", "[dbo].[bank_account]", join="InnerJoin", on="[ba].[id] = [bt].[bank_account_id]"),
         ], "fields": [
            fld("BankAccountId", "bank_account_id", "bt", op="In", arg="@BankAccountId", orr="@BankAccountId is null", output=False),
            fld("TransDate", "trans_date", "bt", op="Between", arg="ISNULL(@DateFrom,{0}) AND ISNULL(@DateTo,{0})"),
            fld("BankAccountCode", "code", "ba"), fld("Description", "description", "bt"), fld("Amount", "amount", "bt"),
         ]}]
    M = {"TransDate": m_date("TransDate", "Date"), "BankAccountCode": m_text("BankAccountCode", "Bank account", 100),
         "Description": m_text("Description", "Description", 220), "Amount": m_decimal("Amount", "Amount")}
    L = [layout("By account", ["TransDate", "BankAccountCode", "Description", "Amount"], sort_by=[{"field": "TransDate", "descending": True}])]
    return dict(
        filename="bank/10_bank_transactions_by_account.json",
        description="Bank transactions by account",
        group="Bank", params=P, selects=S, propmeta=M, layouts=L,
        permissions=[PERM["Cashbook.Enquiry"]],
        notes="Base-table join since bank_transaction has no dac_* equivalent documented in the master skill. Amount uses plain "
              "'decimal' viewType (currency column on bank_transaction not confirmed) — verify against the live schema before relying on this one.",
    )


# ---------------------------------------------------------------- 11. Manual journals in date range
def enquiry_11_manual_journals_by_date():
    P = [LE_PARAM, param("DateFrom", "Date from", "Date", "Date"), param("DateTo", "Date to", "Date", "Date", default="#today")]
    S = [{"name": "Main", "sources": [
            src("db", "[dbo].[dac_doc_base]", "View"),
            src("dt", "[dbo].[doc_type]", join="InnerJoin", on="[dt].[id] = [db].[doc_type_id] AND [dt].[is_gl] = 1"),
         ], "fields": [
            fld("LegalEntityId", "legal_entity_id", "db", op="In", arg="@LegalEntityId", orr="@LegalEntityId is null", output=False),
            fld("PostDate", "doc_date", "db", op="Between", arg="ISNULL(@DateFrom,{0}) AND ISNULL(@DateTo,{0})"),
            fld("DocNo", "doc_no", "db"), fld("Description", "description", "db"),
            fld("CreatedBy", "created_by", "db"), fld("BaseCurrency", "base_currency", "db"),
            fld("NetAmount", "net_amount", "db"),
         ]}]
    M = {"PostDate": m_date("PostDate", "Date"), "DocNo": m_link("DocNo", "Doc no"),
         "Description": m_text("Description", "Description", 250),
         "CreatedBy": meta("CreatedBy", "Created by", "text", "catalog", 120, attribute="UserAccount", valueMember="Code"),
         "BaseCurrency": m_text("BaseCurrency", "Base currency", 60), "NetAmount": m_amount("NetAmount", "Amount")}
    L = [layout("Manual journals", ["PostDate", "DocNo", "Description", "CreatedBy", "NetAmount"],
                includes=["BaseCurrency"], sort_by=[{"field": "PostDate", "descending": True}])]
    return dict(
        filename="gl/11_manual_journals_by_date.json",
        description="Manual journals posted in a date range",
        group="GL", params=P, selects=S, propmeta=M, layouts=L,
        permissions=[PERM["ManualJournal.Enquiry"]],
        notes="doc_type.is_gl=1 identifies manual-journal-family documents per the master skill.",
    )


# ---------------------------------------------------------------- 12. Documents by user
def enquiry_12_documents_by_user():
    P = [LE_PARAM]
    S = [{"name": "Main", "sources": [src("db", "[dbo].[dac_doc_base]", "View")],
          "fields": [
            fld("LegalEntityId", "legal_entity_id", "db", op="In", arg="@LegalEntityId", orr="@LegalEntityId is null", output=False),
            fld("DocNo", "doc_no", "db"), fld("Description", "description", "db"),
            fld("DocDate", "doc_date", "db"), fld("CreatedBy", "created_by", "db"),
            fld("LastModifiedBy", "created_by", "db"),  # placeholder — see note
          ]}]
    M = {"DocNo": m_link("DocNo", "Doc no"), "Description": m_text("Description", "Description", 220),
         "DocDate": m_date("DocDate", "Date"),
         "CreatedBy": meta("CreatedBy", "Created by", "text", "catalog", 120, attribute="UserAccount", valueMember="Code"),
         "LastModifiedBy": meta("LastModifiedBy", "Last modified by", "text", "catalog", 120, attribute="UserAccount", valueMember="Code")}
    L = [layout("By user", ["DocNo", "Description", "DocDate", "CreatedBy", "LastModifiedBy"])]
    return dict(
        filename="gl/12_documents_by_user.json",
        description="Documents created/last modified by user",
        group="DocBase", params=P, selects=S, propmeta=M, layouts=L,
        permissions=[PERM["DocBase.Enquiry"]],
        notes="CAUTION: dac_doc_base's own last_modified_by column wasn't confirmed anywhere in the master skill (only "
              "dac_gl's and account's were) — LastModifiedBy is stubbed to created_by here as a placeholder. Check "
              "INFORMATION_SCHEMA.COLUMNS on dac_doc_base before relying on this one; swap the Sql if a real column exists.",
    )


# ---------------------------------------------------------------- 13. Budget vs actual
def enquiry_13_budget_vs_actual():
    # No LegalEntityId param here (deliberately, fixed 2026-09-27): dac_gl.legal_entity_id
    # is confirmed, but budget2_key's is not (docs/SCHEMA.md), and FAILURE_MODES #8
    # requires both sides of a union to carry the same field list — filtering only
    # the "Actual" side would also silently compare mismatched populations. A dead
    # parameter was caught by src/ir.py's unused-param check; see
    # docs/DISCOVERED_FAILURE_MODES.md #1. Re-add once budget2_key's columns are confirmed.
    P = [param("PeriodId", "Period", setting_xml=setting("Period"))]
    S = [{"name": "Budget", "sources": [
            src("bv", "[dbo].[budget2_value]", "Table"),
            src("bk", "[dbo].[budget2_key]", join="InnerJoin", on="[bk].[id] = [bv].[budget_key_id]"),
         ], "fields": [
            fld("PeriodId", "period_id", "bv", op="In", arg="@PeriodId", orr="@PeriodId is null", output=False),
            fld("AccountId", "account_id", "bk"), fld("CostCentre", "cost_centre", "bk"),
            fld("BudgetAmount", "SUM([bv].[amount])", type="Summary"), fld("ActualAmount", "0", type="Constant", output=True),
         ]},
         {"name": "Actual", "union": "UnionAll", "sources": [
            src("g", "[dbo].[dac_gl]", "View"),
            src("cg", "[generated].[crv_gl]", join="LeftJoin", on="[g].[id] = [cg].[id]"),
         ], "fields": [
            fld("PeriodId", "period_id", "g", op="In", arg="@PeriodId", orr="@PeriodId is null", output=False),
            fld("AccountId", "account_id", "g"), fld("CostCentre", "CostCentre", "cg"),
            fld("BudgetAmount", "0", type="Constant", output=True), fld("ActualAmount", "SUM([g].[amount])", type="Summary"),
         ]}]
    M = {"AccountId": m_catalog("AccountId", "Account", "Account", 220), "CostCentre": m_text("CostCentre", "Cost centre", 100),
         "BudgetAmount": m_decimal("BudgetAmount", "Budget"), "ActualAmount": m_decimal("ActualAmount", "Actual")}
    L = [layout("Budget vs actual", ["AccountId", "CostCentre", "BudgetAmount", "ActualAmount"],
                group_rows=[{"field": "AccountId", "sticky": True}, {"field": "CostCentre", "sticky": True}],
                group_data=[{"field": "BudgetAmount", "aggregator": "sum"}, {"field": "ActualAmount", "aggregator": "sum"}])]
    return dict(
        filename="budgets/13_budget_vs_actual.json",
        description="Budget vs actual by cost centre",
        group="GL", params=P, selects=S, propmeta=M, layouts=L,
        permissions=[PERM["BudgetForecast.Enquiry"]],
        notes="UNION ALL of budget2_value and dac_gl, both padded with a 0 Constant for the column the other side doesn't have "
              "so the two Selects output identical field lists (required — see master skill union rule). Amounts use plain "
              "'decimal' viewType since there's no single shared currency field across the union. PeriodId is filter-only.",
    )


# ---------------------------------------------------------------- 14. Credit notes issued by period
def enquiry_14_credit_notes_by_period():
    P = [LE_PARAM, param("DateFrom", "Date from", "Date", "Date"), param("DateTo", "Date to", "Date", "Date", default="#today")]
    S = [{"name": "Main", "sources": [
            src("db", "[dbo].[dac_doc_base]", "View"),
            src("dt", "[dbo].[doc_type]", join="InnerJoin", on="[dt].[id] = [db].[doc_type_id] AND [dt].[is_credit_note] = 1"),
            src("ca", "[dbo].[contact_account]", join="LeftJoin", on="[ca].[id] = [db].[contact_account_id]"),
         ], "fields": [
            fld("LegalEntityId", "legal_entity_id", "db", op="In", arg="@LegalEntityId", orr="@LegalEntityId is null", output=False),
            fld("DocDate", "doc_date", "db", op="Between", arg="ISNULL(@DateFrom,{0}) AND ISNULL(@DateTo,{0})"),
            fld("DocNo", "doc_no", "db"), fld("ContactAccountId", "id", "ca"),
            fld("ContactAccountDescription", "description", "ca"),
            fld("BaseCurrency", "base_currency", "db"),
            fld("GrossAmount", "[db].[gross_amount] * [dt].[mul_control]", type="Expression"),
         ]}]
    M = {"DocNo": m_link("DocNo", "Doc no"), "DocDate": m_date("DocDate", "Date"),
         "ContactAccountId": m_catalog("ContactAccountId", "Contact", "ContactAccount", 200),
         "ContactAccountDescription": m_text("ContactAccountDescription", "Name", 220),
         "BaseCurrency": m_text("BaseCurrency", "Base currency", 60), "GrossAmount": m_amount("GrossAmount", "Gross")}
    L = [layout("Credit notes", ["DocNo", "DocDate", "ContactAccountDescription", "GrossAmount"], includes=["BaseCurrency"])]
    return dict(
        filename="sales/14_credit_notes_by_period.json",
        description="Credit notes issued by period",
        group="Sale", params=P, selects=S, propmeta=M, layouts=L,
        permissions=[PERM["SaleInvoice.Enquiry"]],
        notes="Flat list (no Summary fields) so DocDate can safely double as both filter and display column. "
              "doc_type.is_credit_note=1 filters to credit notes; mul_control applied for the correct sign.",
    )


# All 14, in catalog order — the single list templates.py and main() both walk.
ENQUIRIES = [
    enquiry_01_gl_trial_balance,
    enquiry_02_gl_detail_by_nominal,
    enquiry_03_balance_sheet_by_department_nominal,
    enquiry_04_pl_by_month,
    enquiry_05_aged_debtors_by_customer,
    enquiry_06_top_customers_by_revenue,
    enquiry_07_aged_creditors_by_supplier,
    enquiry_08_purchase_invoices_by_supplier_month,
    enquiry_09_overdue_purchase_invoices,
    enquiry_10_bank_transactions_by_account,
    enquiry_11_manual_journals_by_date,
    enquiry_12_documents_by_user,
    enquiry_13_budget_vs_actual,
    enquiry_14_credit_notes_by_period,
]


def build_export(spec, description=None):
    """spec is one of the dicts an enquiry_NN_*() function returns. Returns
    (export_json_str, model_dict) via enqgen.build() — the same envelope
    emit() writes to disk, without writing anything. `description`
    overrides spec['description'] (used by src/templates.py to carry the
    customer's own wording through when that's wanted)."""
    return build(description or spec["description"], spec["group"], query_xml(spec["params"], spec["selects"]),
                 spec["propmeta"], spec["layouts"], permissions=spec["permissions"])


def emit(spec):
    """Writes one spec dict to generated/<filename> and returns its path."""
    env, model = build_export(spec)
    path = os.path.join(GENERATED, spec["filename"])
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(env)
    return path


def main():
    catalog = []
    for make in ENQUIRIES:
        spec = make()
        emit(spec)
        catalog.append(dict(filename=spec["filename"], description=spec["description"],
                             group=spec["group"], notes=spec["notes"]))
    with open(os.path.join(GENERATED, "catalog.json"), "w") as f:
        json.dump(catalog, f, indent=2)
    print(f"Built {len(catalog)} enquiries into {GENERATED}")


if __name__ == "__main__":
    main()
