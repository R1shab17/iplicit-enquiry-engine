"""
The template catalog: the 14 confirmed report shapes built in
build_library.py, each tagged with the plain-English phrases a request for
it tends to use. src/compiler.py's compile_request() matches a customer's
free-text request against this list to decide which (if any) confirmed
report to build — rather than trying to synthesize a brand-new query from
scratch for modules where this repo doesn't have confirmed dimension
flexibility the way it does for GL (docs/ROADMAP.md item 10; see
src/compiler.py's own docstring for why GL alone also gets a flexible,
custom-dimension path).

Deliberately a thin selection layer, not a second copy of the query logic:
every build_fn here is one of build_library.py's own enquiry_NN_*()
functions, so there is exactly one place that knows how to build, say, an
aged-debtors report — this module only decides *whether* a request wants
one.
"""
from dataclasses import dataclass, field
from typing import Callable, List, Tuple

import build_library as lib


@dataclass(frozen=True)
class Template:
    key: str
    module: str
    title: str
    # Multi-word phrases, not bare nouns — keeps matching precise enough
    # that "supplier" alone doesn't light up three unrelated templates.
    # Kept non-redundant within a template (no phrase that's a substring of
    # another phrase in the same list) so one mention doesn't double-count.
    keywords: Tuple[str, ...]
    build_fn: Callable[[], dict]
    # Phrases that, if present, veto this template even when a keyword also
    # matched — for the case where two templates' keyword lists legitimately
    # overlap (e.g. "overdue purchase invoices" contains both "purchase
    # invoice" and "overdue purchase"). Keeps the *within-one-list*
    # non-redundancy rule above from being defeated by a phrase that's a
    # substring of another template's more specific phrase.
    anti_keywords: Tuple[str, ...] = field(default_factory=tuple)


TEMPLATES: List[Template] = [
    Template("gl_trial_balance", "GL", "Trial balance",
              ("trial balance",),
              lib.enquiry_01_gl_trial_balance),
    Template("gl_detail_by_nominal", "GL", "GL detail by nominal",
              ("gl detail", "nominal detail", "transaction detail", "gl transactions", "general ledger detail"),
              lib.enquiry_02_gl_detail_by_nominal),
    Template("gl_balance_sheet_by_department", "GL", "Balance sheet by department and nominal",
              ("balance sheet",),
              lib.enquiry_03_balance_sheet_by_department_nominal),
    Template("gl_pl_by_month", "GL", "Profit & loss by month",
              ("profit and loss", "profit & loss", "p&l", "p and l", "income statement"),
              lib.enquiry_04_pl_by_month),
    Template("ar_aged_debtors", "AR", "Aged debtors by customer",
              ("aged debt", "customer balance", "outstanding customer balance", "who owes us", "receivables"),
              lib.enquiry_05_aged_debtors_by_customer),
    Template("sales_top_customers", "Sales", "Top customers by revenue",
              ("top customer", "best customer", "revenue by customer", "sales by customer", "biggest customer"),
              lib.enquiry_06_top_customers_by_revenue),
    Template("ap_aged_creditors", "AP", "Aged creditors by supplier",
              ("aged credit", "supplier balance", "outstanding supplier balance", "who do we owe", "payables"),
              lib.enquiry_07_aged_creditors_by_supplier),
    Template("purchasing_by_supplier_month", "Purchasing", "Purchase invoices by supplier by month",
              ("purchase invoice", "spend by supplier", "supplier spend", "purchases by month"),
              lib.enquiry_08_purchase_invoices_by_supplier_month,
              # "overdue purchase invoices" is the overdue-specific report
              # below, not this one, even though it contains "purchase
              # invoice" too — see the Template.anti_keywords docstring.
              anti_keywords=("overdue", "late payment", "unpaid")),
    Template("ap_overdue_invoices", "AP", "Overdue purchase invoices",
              ("overdue purchase", "overdue supplier invoice", "overdue invoice", "late payment", "unpaid supplier"),
              lib.enquiry_09_overdue_purchase_invoices),
    Template("bank_transactions", "Bank", "Bank transactions by account",
              ("bank transaction", "bank statement", "cashbook", "bank account activity"),
              lib.enquiry_10_bank_transactions_by_account),
    Template("gl_manual_journals", "GL", "Manual journals posted in a date range",
              ("manual journal", "journal entry", "journals posted"),
              lib.enquiry_11_manual_journals_by_date),
    Template("gl_documents_by_user", "GL", "Documents created/last modified by user",
              ("documents by user", "who created", "created by user", "last modified by user"),
              lib.enquiry_12_documents_by_user),
    Template("budgets_vs_actual", "Budgets", "Budget vs actual by cost centre",
              ("budget vs actual", "budget versus actual", "budget variance", "actual vs budget", "actuals vs budget"),
              lib.enquiry_13_budget_vs_actual),
    Template("sales_credit_notes", "Sales", "Credit notes issued by period",
              ("credit note", "credit notes issued"),
              lib.enquiry_14_credit_notes_by_period),
]

BY_KEY = {t.key: t for t in TEMPLATES}


def score(text: str, template: Template) -> int:
    """Number of distinct keyword phrases from `template` that appear in
    `text` (case-insensitive substring match) — 0 if any of the template's
    anti_keywords is present, however many keywords also matched."""
    t = text.lower()
    if any(kw in t for kw in template.anti_keywords):
        return 0
    return sum(1 for kw in template.keywords if kw in t)


def match(text: str) -> List[Tuple[Template, int]]:
    """Every template with score > 0, best first. Ties (same top score,
    more than one template) are the caller's cue to ask a clarifying
    question rather than guess which one was meant."""
    scored = [(tpl, score(text, tpl)) for tpl in TEMPLATES]
    scored = [(tpl, s) for tpl, s in scored if s > 0]
    scored.sort(key=lambda pair: -pair[1])
    return scored
