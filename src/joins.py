"""
Source/join helpers for building a QueryXml <Select> block's <Source> list.

`src()` is the low-level building block (one <Source> element). The
`*_joins()` functions below return ready-made lists of `src()` calls for the
standard fan-outs documented in docs/SCHEMA.md — use them as a starting
point and slice/extend as needed, rather than re-typing the same join chain
in every build script.
"""


def src(name, sql, type="Table", join="Principal", on=None):
    """One <Source> element.

    name -- the alias used elsewhere in the Select (e.g. "g", "a", "db").
    sql  -- the source's Sql attribute, e.g. "[dbo].[dac_gl]" or a
            Type="Sql" subquery.
    type -- "Table" | "View" | "Sql".
    join -- "Principal" | "InnerJoin" | "LeftJoin" | "OuterApply" | "CrossApply".
    on   -- JoinCondition, e.g. "[a].[id] = [g].[account_id]". Required for
            every join except the Principal source.
    """
    return dict(name=name, sql=sql, type=type, join=join, on=on)


def gl_standard_joins(include_dimensions=True, include_document=False):
    """The standard join fan-out for a GL-grain enquiry (docs/SCHEMA.md):

        g (dac_gl) -> a (account) -> le (legal_entity) -> p (period) -> fy (financial_year)
                   -> cg (crv_gl, left)                                   [if include_dimensions]
                   -> db (doc_base, left) -> dt (doc_type)                [if include_document]
    """
    joins = [
        src("g", "[dbo].[dac_gl]", type="View", join="Principal"),
        src("a", "[dbo].[account]", join="InnerJoin", on="[a].[id] = [g].[account_id]"),
        src("le", "[dbo].[dac_legal_entity]", type="View", join="InnerJoin", on="[le].[id] = [g].[legal_entity_id]"),
        src("p", "[dbo].[period]", join="InnerJoin", on="[p].[id] = [g].[period_id]"),
        src("fy", "[dbo].[financial_year]", join="InnerJoin", on="[fy].[id] = [p].[financial_year_id]"),
    ]
    if include_dimensions:
        joins.append(src("cg", "[generated].[crv_gl]", type="View", join="LeftJoin", on="[cg].[id] = [g].[id]"))
    if include_document:
        joins.append(src("db", "[dbo].[dac_doc_base]", type="View", join="LeftJoin", on="[db].[id] = [g].[doc_id]"))
        joins.append(src("dt", "[dbo].[doc_type]", join="LeftJoin", on="[dt].[id] = [db].[doc_type_id]"))
    return joins


def doc_standard_joins(include_contact=True, contact_role=None, include_dimensions=False):
    """The standard join fan-out for a document-grain enquiry:

        db (dac_doc_base) -> dt (doc_type) -> le (legal_entity)
                           -> ca (contact_account, left) -> cs/cc (contact_supplier/customer, left)
                           -> cd (crv_doc_base, left)                     [if include_dimensions]

    contact_role -- "customer" | "supplier" | None. When set, also joins the
    matching contact_customer/contact_supplier table sharing contact_account's id.
    """
    joins = [
        src("db", "[dbo].[dac_doc_base]", type="View", join="Principal"),
        src("dt", "[dbo].[doc_type]", join="InnerJoin", on="[dt].[id] = [db].[doc_type_id]"),
        src("le", "[dbo].[dac_legal_entity]", type="View", join="InnerJoin", on="[le].[id] = [db].[legal_entity_id]"),
    ]
    if include_contact:
        joins.append(src("ca", "[dbo].[contact_account]", join="LeftJoin", on="[ca].[id] = [db].[contact_account_id]"))
        if contact_role == "customer":
            joins.append(src("cc", "[dbo].[contact_customer]", join="LeftJoin", on="[cc].[id] = [ca].[id]"))
        elif contact_role == "supplier":
            joins.append(src("cs", "[dbo].[contact_supplier]", join="LeftJoin", on="[cs].[id] = [ca].[id]"))
    if include_dimensions:
        joins.append(src("cd", "[generated].[crv_doc_base]", type="View", join="LeftJoin", on="[cd].[id] = [db].[id]"))
    return joins


def doc_detail_joins():
    """Join doc_detail (dd) onto an existing doc_standard_joins() list, keyed on db.id."""
    return [src("dd", "[dbo].[doc_detail]", join="InnerJoin", on="[dd].[doc_id] = [db].[id]")]
