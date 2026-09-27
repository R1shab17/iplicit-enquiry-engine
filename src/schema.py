"""
Structured schema knowledge for iplicit's enquiry data model.

This is the importable-data counterpart to docs/SCHEMA.md — keep the two in
sync. Every table entry carries a `status` of "confirmed" (seen directly in
a real enquiry's QueryXml, or verified live against a sandbox tenant) or
"inferred" (follows documented naming/structure conventions but hasn't been
independently checked against INFORMATION_SCHEMA.COLUMNS). Treat "inferred"
as a hypothesis, not a fact.

Nothing in this module talks to a live iplicit tenant — see
docs/ARCHITECTURE.md's "design choices" section.
"""

# Principal dac_* views. Use these as the Principal source for GL/document
# queries — they apply the user's legal-entity access control. The
# equivalent base tables (dbo.gl, dbo.doc_base, dbo.doc_detail) exist but
# skip that security and should only be used when cross-entity visibility
# is deliberate.
PRINCIPAL_VIEWS = {
    "dac_gl": {
        "sql": "[dbo].[dac_gl]",
        "alias": "g",
        "status": "confirmed",
        "notes": "GL posting lines. Applies legal-entity access control.",
    },
    "dac_doc_base": {
        "sql": "[dbo].[dac_doc_base]",
        "alias": "db",
        "status": "confirmed",
        "notes": "Document headers (invoices, orders, journals). Applies legal-entity access control.",
    },
    "dac_legal_entity": {
        "sql": "[dbo].[dac_legal_entity]",
        "alias": "le",
        "status": "confirmed",
        "notes": "Legal entity list, access-controlled.",
    },
}

# Base tables that skip legal-entity security. Flagged by
# enquiry_validator.py's check_query_xml() whenever one is used as a
# Principal source and a dac_* equivalent exists.
UNSAFE_BASE_TABLES = {"dbo.gl", "dbo.doc_base", "dbo.doc_detail"}

TABLES = {
    # NOTE: these three crv_* views were used correctly and consistently
    # throughout generated/ from the start (they're documented in prose in
    # dac_gl's own notes below and in docs/SCHEMA.md), but were missing as
    # their own TABLES entries until src/confidence.py's report surfaced the
    # gap during the engine-hardening pass — every enquiry using crv_gl was
    # showing up as "unknown" confidence for a view that was never actually
    # in doubt. Fixed rather than left as a cosmetic false alarm.
    "crv_gl": {
        "status": "confirmed",
        "columns": [],
        "notes": (
            "[generated].[crv_gl] carries the analytic-dimension codes "
            "(Department, CostCentre, Fund, Resource, Location, Activity, "
            "Intercon, Country, IncomeType, ...) for a GL line, keyed by "
            "cg.id = g.id (left join — not every line has every dimension "
            "set). Exact full column list not enumerated here; the "
            "dimension names above are the ones seen in this project's "
            "own generated/ output."
        ),
    },
    "crv_doc_base": {
        "status": "confirmed",
        "columns": [],
        "notes": "Document-header equivalent of crv_gl, keyed by cd.id = db.id (left join).",
    },
    "crv_doc_detail": {
        "status": "confirmed",
        "columns": [],
        "notes": "Document-line equivalent of crv_gl/crv_doc_base.",
    },
    "dac_gl": {
        "status": "confirmed",
        "columns": [
            "id", "amount", "currency_amount", "currency", "base_currency",
            "account_id", "period_id", "period_date", "post_date", "trans_date",
            "doc_id", "doc_no", "doc_type_id", "contact_account_id", "project_id",
            "product_id", "legal_entity_id", "tax_code_id", "description",
            "invoice_no", "trans_no", "trans_line_no", "attribute_id",
            "bank_account_id", "last_modified", "last_modified_by",
        ],
        "notes": (
            "Analytic dimensions (Department, CostCentre, Fund, Resource, "
            "Location, Activity, Intercon, Country, IncomeType...) are NOT on "
            "dac_gl — join [generated].[crv_gl] (alias cg) on cg.id = g.id "
            "(left join; not every GL line has every dimension set)."
        ),
    },
    "dac_doc_base": {
        "status": "confirmed",
        "columns": [
            "id", "doc_no", "doc_date", "due_date", "tax_date", "status",
            "net_amount", "tax_amount", "gross_amount",
            "net_currency_amount", "tax_currency_amount", "gross_currency_amount",
            "currency", "base_currency", "contact_account_id", "doc_type_id",
            "doc_class", "period_id", "legal_entity_id", "project_id",
            "their_doc_no", "their_ref", "order_no", "description",
            "created_by", "created_date",
            "status_is_draft", "status_is_posted", "status_is_abandoned",
            "status_is_dispute", "status_is_closed",
        ],
        "unconfirmed_columns": ["last_modified", "last_modified_by"],
        "notes": (
            "INFERRED, NOT CONFIRMED: whether dac_doc_base has its own "
            "last_modified/last_modified_by columns (distinct from "
            "created_by/created_date). generated/gl/12_documents_by_user.json "
            "stubs LastModifiedBy to created_by pending this. Check "
            "INFORMATION_SCHEMA.COLUMNS on dac_doc_base before relying on a real one."
        ),
    },
    "doc_detail": {
        "status": "confirmed",
        "columns": [
            "doc_id", "product_id", "description", "quantity",
            "net_amount", "tax_amount", "gross_amount",
            "net_currency_amount", "tax_currency_amount", "gross_currency_amount",
            "tax_code_id", "period_id", "order_index",
        ],
    },
    "doc_type": {
        "status": "confirmed",
        "columns": [
            "is_sale", "is_purchase", "is_credit_note", "is_gl",
            "has_outstandings", "is_cb", "doc_class", "attribute_id", "mul_control",
        ],
        "notes": (
            "Sign convention: multiply document amounts by doc_type.mul_control "
            "so credit notes/negative document types come out with the correct "
            "sign. Never trust a document amount's raw stored sign alone when "
            "doc type varies."
        ),
    },
    "doc_outstanding": {
        "status": "confirmed",
        "columns": ["cur_outs_amount", "posted_outs_amount", "mul_control"],
        "notes": "PK = doc id.",
    },
    "doc_allocation": {
        "status": "confirmed",
        "columns": ["doc_id", "alloc_doc_id", "amount"],
    },
    "account": {
        "status": "confirmed",
        "columns": [
            "code", "description", "name", "account_type", "coa_group_id",
            "ar_flag", "ap_flag", "cb_flag", "control_flag", "tax_flag",
            "last_modified", "last_modified_by",
        ],
        "notes": (
            "last_modified/last_modified_by CONFIRMED LIVE this session and "
            "are distinct from dac_gl's own columns of the same name — see "
            "docs/FAILURE_MODES.md #7. This is the chart-of-accounts record's "
            "audit stamp, not the GL posting's."
        ),
    },
    "coa_group": {"status": "confirmed", "columns": []},
    "period": {
        "status": "confirmed",
        "columns": ["code", "date_from", "date_to", "financial_year_id", "is_bf", "is_cf", "is_adjustment"],
    },
    "financial_year": {
        "status": "confirmed",
        "columns": ["code", "description", "date_from", "date_to", "financial_year_group_id", "previous_financial_year_id"],
    },
    "financial_year_group": {"status": "confirmed", "columns": []},
    "legal_entity": {"status": "confirmed", "columns": ["code", "description", "currency"]},
    "project": {"status": "confirmed", "columns": [], "notes": "Confirmed to exist as a catalog."},
    "department": {"status": "confirmed", "columns": [], "notes": "Confirmed to exist as a catalog."},
    "cost_centre": {"status": "confirmed", "columns": [], "notes": "Confirmed to exist as a catalog."},
    "product": {"status": "confirmed", "columns": ["code", "description"]},
    "tax_code": {"status": "confirmed", "columns": [], "notes": "Confirmed to exist."},
    "bank_account": {"status": "confirmed", "columns": [], "notes": "Confirmed to exist."},
    "bank_transaction": {
        "status": "inferred",
        "columns": [],
        "notes": (
            "No dac_* equivalent documented; exact column set (especially any "
            "currency columns) not confirmed — see "
            "generated/bank/10_bank_transactions_by_account.json"
        ),
    },
    "resource": {"status": "confirmed", "columns": []},
    "user_account": {
        "status": "confirmed",
        "columns": ["code"],
        "notes": "user_account.code is what catalog attribute UserAccount resolves against.",
    },
    "budget2": {"status": "inferred", "columns": [], "notes": "Structure assumed from naming convention; not independently verified."},
    "budget2_key": {"status": "inferred", "columns": []},
    "budget2_value": {
        "status": "inferred",
        "columns": ["budget_key_id", "period_id", "amount"],
        "notes": "Structure assumed from naming convention; not independently verified.",
    },
    "credit_control_note": {"status": "confirmed", "columns": [], "notes": "Confirmed to exist. Not yet used in generated/."},
    "contact_account": {
        "status": "confirmed",
        "columns": ["code", "description", "contact_classification_id", "parent_contact_account_id"],
    },
    "contact_customer": {
        "status": "confirmed",
        "columns": ["credit_limit", "pay_term_id", "contact_group_customer_id", "is_hold", "is_stop"],
        "notes": "Shares its id with contact_account.",
    },
    "contact_supplier": {
        "status": "confirmed",
        "columns": ["credit_limit", "pay_term_id", "contact_group_supplier_id", "is_hold", "is_stop"],
        "notes": "Shares its id with contact_account.",
    },
}

# Table-valued functions and scalar helper functions.
FUNCTIONS = {
    "GetAgedDebt": {
        "status": "confirmed_exists",
        "signature": "dbo.GetAgedDebt(@col, @to_date)",
        "notes": "Confirmed to exist and usable as a Sql-type source. Exact output column names are INFERRED (cur_outs_amount assumed by analogy with doc_outstanding, not independently checked).",
    },
    "GetAgedCreditors": {
        "status": "confirmed_exists",
        "signature": "dbo.GetAgedCreditors(@col, @to_date)",
        "notes": "Same caveat as GetAgedDebt.",
    },
    "GetIntervalRange": {
        "status": "confirmed_exists",
        "signature": "dbo.GetIntervalRange(@IntervalId, days)",
        "notes": "Confirmed to exist for bucketing (CROSS APPLY), giving `range`/`range_index`. Not yet used in any generated/ enquiry — see docs/ROADMAP.md.",
    },
    "FinancialYearOrDefaultWithLegalEntity": {
        "status": "confirmed_exists",
        "signature": "dbo.FinancialYearOrDefaultWithLegalEntity(@FinancialYear, @FinancialYearGroup, @LegalEntity)",
    },
    "StatusIsDraft": {"status": "confirmed_exists", "signature": "dbo.StatusIsDraft(status)"},
    "StatusIsPosted": {"status": "confirmed_exists", "signature": "dbo.StatusIsPosted(status)"},
    "StatusIsAbandoned": {"status": "confirmed_exists", "signature": "dbo.StatusIsAbandoned(status)"},
    "StatusIsDisputed": {"status": "confirmed_exists", "signature": "dbo.StatusIsDisputed(status)"},
    "StatusIsReversed": {"status": "confirmed_exists", "signature": "dbo.StatusIsReversed(status)"},
    "StatusIsOutstanding": {"status": "confirmed_exists", "signature": "dbo.StatusIsOutstanding(status)"},
    "StatusIsClosed": {"status": "confirmed_exists", "signature": "dbo.StatusIsClosed(status)"},
    "StatusIsPendingAuth": {"status": "confirmed_exists", "signature": "dbo.StatusIsPendingAuth(status)"},
    "StatusIsApproved": {"status": "confirmed_exists", "signature": "dbo.StatusIsApproved(status)"},
    "StatusIsRejected": {"status": "confirmed_exists", "signature": "dbo.StatusIsRejected(status)"},
    "StatusIsWrittenOff": {"status": "confirmed_exists", "signature": "dbo.StatusIsWrittenOff(status)"},
}

# Analytic-dimension picker attributes usable in a Param's <Setting Attribute="...">
CATALOG_ATTRIBUTES = [
    "LegalEntity", "Customer", "Supplier", "ContactAccount", "Account", "Period",
    "FinancialYear", "FinancialYearGroup", "DocType", "Project", "Department",
    "CostCentre", "Product", "TaxCode", "Currency", "BankAccount", "CoaGroup",
    "ContactGroupCustomer", "ContactClassification", "UserAccount",
]

# Cascading catalogs iplicit uses for Param <Binding> chains.
CASCADING_CATALOGS = [
    "PeriodsForFYG_FY_LE",
    "LegalEntitiesForFinancialGroup",
    "FinancialYearGroupForLegalEntity",
    "FinancialYearsForGroupOrDefaults",
]

# Default tokens usable in a Param's Default attribute.
DEFAULT_TOKENS = [
    "#today", "#now", "#fin_year", "#def_financial_year_group", "#def_legal_entity",
    "#def_cur_code", "#def_exchange_rate_type", "#user", "#ago(7d)",
    "20000000-0000-0000-0000-000000000000",  # "current FY" sentinel
]


def is_unsafe_principal(sql):
    """True if `sql` (a Source's Sql attribute) looks like a raw base table
    that has a dac_* equivalent, and so may leak rows across legal entities.
    Mirrors the check in src/enquiry_validator.py's check_query_xml()."""
    sql_lower = (sql or "").lower()
    if any(v in sql_lower for v in ("dac_gl", "dac_doc_base", "dac_legal_entity")):
        return False
    import re
    return bool(re.search(r"\[dbo\]\.\[(gl|doc_base|doc_detail)\]", sql_lower))


def table_status(name):
    """Return 'confirmed' / 'inferred' / None (unknown table) for a bare table name."""
    entry = TABLES.get(name) or PRINCIPAL_VIEWS.get(name)
    return entry["status"] if entry else None
