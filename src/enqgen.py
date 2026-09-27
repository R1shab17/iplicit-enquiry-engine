"""
Build an iplicit enquiry export (paste via Enquiries > (menu) > Import from
clipboard). This is the orchestrator: params, filter fields, QueryXml
assembly, and the final envelope. Table/column knowledge lives in
schema.py, join-chain helpers in joins.py, column-metadata and layout
helpers in layouts.py, and permission GUIDs in permissions.py.

Everything from those four modules is re-exported here so existing scripts
(e.g. build_library.py) can keep doing `from enqgen import *` — see
docs/ARCHITECTURE.md's pipeline diagram.
"""
import json
import base64
import datetime
from xml.sax.saxutils import escape

# Re-exported for backward compatibility with scripts written against the
# original single-file enqgen.py.
from schema import (  # noqa: F401
    PRINCIPAL_VIEWS, UNSAFE_BASE_TABLES, TABLES, FUNCTIONS,
    CATALOG_ATTRIBUTES, CASCADING_CATALOGS, DEFAULT_TOKENS,
    is_unsafe_principal, table_status,
)
from joins import src, gl_standard_joins, doc_standard_joins, doc_detail_joins  # noqa: F401
from layouts import (  # noqa: F401
    meta, m_catalog, m_amount, m_decimal, m_date, m_text, m_link, m_status,
    m_int, m_bit, layout,
)
from permissions import PERM  # noqa: F401


def setting(attribute=None, value_member="ObjectId", allow_closed=True, catalog=None, filter=None,
            display_member=None, bindings=()):
    """A Param's Setting attribute value (itself an escaped inline XML string)."""
    a = []
    if attribute:
        a.append(f'Attribute="{attribute}"')
    if catalog:
        a.append(f'Catalog="{catalog}"')
    if value_member:
        a.append(f'ValueMember="{value_member}"')
    if display_member:
        a.append(f'DisplayMember="{display_member}"')
    if allow_closed:
        a.append('AllowClosed="True"')
    if filter:
        a.append('Filter="' + escape(filter, {'"': '&quot;'}) + '"')
    if bindings:
        inner = "".join(f'\n  <Binding Name="{n}" ValueType="{t}" PropertyName="{p}"/>' for n, t, p in bindings)
        return f'<Setting {" ".join(a)}>{inner}\n</Setting>'
    return f'<Setting {" ".join(a)} />'


def param(name, caption, value_type="Text", presenter="MultiGit", setting_xml="false", default=None,
          mandatory=False, help=None):
    """One <Param> definition."""
    return dict(name=name, caption=caption, value_type=value_type, presenter=presenter, setting=setting_xml,
                default=default, mandatory=mandatory, help=help)


def fld(name, sql, source=None, type=None, op=None, arg=None, orr=None, output=True, filter=None):
    """One <Field> definition. type defaults to Column when a source is
    given, Expression otherwise. Use type="Summary" for an aggregate (this
    turns every other non-Summary field in the Select into an implicit
    GROUP BY key — see docs/FAILURE_MODES.md #5), and output=False for a
    filter-only field."""
    if type is None:
        type = "Column" if source else "Expression"
    return dict(name=name, sql=sql, source=source, type=type, op=op, arg=arg, orr=orr, output=output, filter=filter)


def multi_filter(name, sql, source, param):
    """Standard optional multi-select filter: In @param, or @param is null.
    Always use this (never a bare FilterOperator="In") for an optional
    picker — see docs/FAILURE_MODES.md #2."""
    return fld(name, sql, source, op="In", arg=f"@{param}", orr=f"@{param} is null")


def _esc(v):
    return escape(str(v), {'"': '&quot;', '\n': '&#xA;', '\r': '&#xD;', '\t': '&#x9;'})


def _a(k, v):
    return f' {k}="{_esc(v)}"' if v is not None else ''


def query_xml(params, selects, order_by=None):
    """Assemble the full <Query> XML from param() dicts and a list of Select
    dicts, each shaped like:
        {"name": "Main", "union": None, "sources": [src(...), ...], "fields": [fld(...), ...]}
    """
    out = ['<Query' + _a('OrderBy', order_by) + '>']
    for i, p in enumerate(params):
        out.append('   <Param' + _a('Name', p['name']) + _a('ValueType', p['value_type']) + _a('Setting', p['setting'])
                   + (_a('Mandatory', 'True') if p['mandatory'] else '') + _a('Default', p['default'])
                   + _a('Caption', p['caption']) + _a('Presenter', p['presenter']) + _a('OrderIndex', i) + _a('Help', p['help']) + '/>')
    for si, s in enumerate(selects):
        out.append('   <Select' + _a('Name', s.get('name', f'Select{si}')) + (_a('Union', s['union']) if s.get('union') else _a('OrderIndex', si)) + '>')
        for x in s['sources']:
            out.append('      <Source' + _a('Name', x['name']) + _a('Type', x['type']) + _a('Sql', x['sql']) + _a('JoinType', x['join']) + _a('JoinCondition', x['on']) + '/>')
        for i, f in enumerate(s['fields']):
            out.append('      <Field' + _a('Name', f['name']) + _a('Source', f['source']) + _a('Type', f['type']) + _a('Sql', f['sql'])
                       + _a('FilterOperator', f['op']) + _a('FilterArgument', f['arg']) + _a('FilterOr', f['orr']) + _a('Filter', f['filter'])
                       + ('' if f['output'] else ' Output="False"') + _a('OrderIndex', i) + '/>')
        out.append('   </Select>')
    out.append('</Query>')
    return "\n".join(out)


def build(description, group, qxml, propmeta, layouts, permissions=(), auto_refresh=False,
          param_layout='<AutoPanel ItemWidth="380" ItemPadding="4,2,4,2" />'):
    """Assemble the final DbEnquiry export envelope: base64(model json)
    wrapped in {"type": "DbEnquiry", ...}. Returns (export_json_str, model_dict)."""
    model = {
        "$id": "1", "LinkedAttributes": [], "SharedWith": [],
        "EnquiryLayouts": [{"$id": str(i + 2), "Code": "JsonLayout", "ContainerDefinition": l["def"], "Description": l["description"], "OrderIndex": i}
                           for i, l in enumerate(layouts)],
        "RequiredPermissions": [{"$id": str(100 + i), "AttributeOperationId": pid.lower()} for i, pid in enumerate(permissions)],
        "AnalyticGroups": [],
        "AutoRefresh": auto_refresh, "Description": description, "Group": group,
        "ParamLayoutXml": param_layout, "PreferReplica": True,
        "PropMetaJson": json.dumps(propmeta, indent=2), "QueryXml": qxml,
    }
    data = base64.b64encode(json.dumps(model, ensure_ascii=False).encode("utf-8")).decode()
    env = {"type": "DbEnquiry", "description": description,
           "exportDate": datetime.datetime.now().strftime("%d/%m/%Y %H:%M"), "data": data}
    return json.dumps(env, indent=2), model
