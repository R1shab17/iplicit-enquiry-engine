"""
PropMetaJson column-metadata helpers and EnquiryLayouts grid/pivot builder.
"""
import json


def meta(name, label, data_type="text", view_type="text", width=100, **settings):
    """One PropMetaJson entry. `name` must match a QueryXml output Field's Name."""
    m = {"label": label, "defaultWidth": width, "visible": True, "dataType": data_type, "viewType": view_type, "name": name}
    if settings:
        m["settings"] = settings
    return m


def m_catalog(name, label, attribute, width=150, **kw):
    """A column that shows a catalog's display name for a stored id (or code, with valueMember='Code')."""
    return meta(name, label, "guid", "catalog", width, attribute=attribute, **kw)


def m_amount(name, label, currency_member="BaseCurrency", width=110):
    """A currency-formatted amount column. `currency_member` must be an output
    field present in the layout's includes/columns (docs/FAILURE_MODES.md #6)."""
    return meta(name, label, "decimal", "amount", width, currencyMember=currency_member)


def m_decimal(name, label, width=110):
    """A plain decimal column with no currency formatting — use this instead
    of m_amount() when the source of the value's currency isn't confirmed
    (see docs/FAILURE_MODES.md #6 and CLAUDE.md's honesty rule): it renders
    a number without presenting an unverified currency assumption as fact."""
    return meta(name, label, "decimal", "decimal", width)


def m_date(name, label, width=95):
    return meta(name, label, "date", "date", width)


def m_text(name, label, width=120):
    return meta(name, label, "text", "text", width)


def m_link(name, label, id_member="DocId", attribute_member="Attribute", width=130):
    """A column that renders as a clickable link to a document. `id_member`
    and `attribute_member` must be other output fields on the same row —
    typically a raw doc id and `[attribute].[type_name]` joined via
    doc_type.attribute_id."""
    return meta(name, label, "text", "link", width, idMember=id_member, attributeMember=attribute_member)


def m_status(name="Status", label="Status"):
    return meta(name, label, "int64", "status", 22)


def m_int(name, label, width=80):
    return meta(name, label, "int32", "integer", width)


def m_bit(name, label, width=60):
    return meta(name, label, "bit", "checkbox", width)


def layout(description, columns, group_rows=None, group_columns=None, group_data=None, includes=None, widths=None,
           sort_by=None, group_rows_expand=None, detail=None, extra=None):
    """One EnquiryLayouts entry (a tab). No group_rows/group_columns = flat
    list; with them = pivot, and `detail` is the drill-down grid under a
    pivot cell. Pass `extra={"hierarchy": {...}}` for a saved tree — but see
    docs/FAILURE_MODES.md #1 before combining that with a multi-level
    group_rows."""
    g = {"columns": columns}
    if group_rows:
        g["groupRows"] = group_rows
    if group_columns:
        g["groupColumns"] = group_columns
    if group_data:
        g["groupData"] = group_data
    if includes:
        g["includes"] = includes
    if widths:
        g["widths"] = widths
    if sort_by:
        g["sortBy"] = sort_by
    if group_rows_expand is not None:
        g["groupRowsExpand"] = group_rows_expand
    if detail:
        g["detail"] = detail
    if extra:
        g.update(extra)
    return {"description": description, "def": json.dumps({"layout": {"grid": g}}, indent=2)}
