# iplicit Enquiry — Master SQL Skill

Source: reverse-engineered from 640 live enquiry definitions in the `sandbox.rishab` iplicit tenant (`dbo.enquiry` / `dbo.enquiry_layout`), plus one end-to-end tested build ("Sales by customer by month", 27 Sep 2026). Not guessed — every construct below is attested in real definitions.

---

## 1. Core principles

- An enquiry is four parts glued together: **`QueryXml`** (params + one-or-more `<Select>` blocks that compile to a single `SELECT TOP(100) PERCENT`), **`PropMetaJson`** (per-column label/type/formatting), **`EnquiryLayouts`** (one JSON grid/pivot definition per tab), **`RequiredPermissions`** (≥1 attribute-operation GUID — without one, the Create button in the UI stays disabled).
- Stored in `dbo.enquiry` (`query_xml`, `query_sql`, `prop_meta_json`, `param_layout_xml`, `author_flag`) and `dbo.enquiry_layout` (`container_definition`). `author_flag=1` = shipped by iplicit (must **Copy** before editing); `author_flag=0` = tenant-custom, editable directly.
- Export/import is a clipboard envelope: `{"type":"DbEnquiry","description","exportDate","data": base64(utf8(model json))}`. Import opens an **unsaved** "Create new enquiry" form — nothing is written to the tenant until the user clicks **Create**. This makes it safe to hand over freely: nothing lands until they approve it.
- Naming: `Description` is the enquiry's display name; `Group` buckets it in the enquiry menu (`GL`, `Sale`, `Purchase`, `AR`, `AP`, `Bank`, etc. — matches the module it belongs to). Field names are PascalCase and match the PropMetaJson key exactly; SQL columns underneath stay `snake_case`.
- Formatting convention seen everywhere: 3-space indent in QueryXml, `Field`/`Source`/`Param` each on one line, attributes in a fixed order (`Name`, `Source`, `Type`, `Sql`, `FilterOperator`, `FilterArgument`, `FilterOr`, `Filter`, `Output`, `OrderIndex`). PropMetaJson and ContainerDefinition are both pretty-printed JSON *strings* embedded inside the outer compact JSON — the outer envelope has no whitespace, the embedded strings do. Match this when handwriting one; it isn't required for the import to work, but it's what "real" exports look like.
- **`dac_*` views, not base tables, are the principal (first) source whenever one exists** (`dac_gl`, `dac_doc_base`, `dac_legal_entity`). They silently apply the logged-in user's legal-entity access control; querying the base table instead leaks rows across entities the user shouldn't see.

## 2. Schema knowledge

**GL lines — `dac_gl`** (alias commonly `g`): `id`, `amount` (base currency), `currency_amount`, `currency`, `base_currency`, `account_id`, `period_id`, `period_date`, `post_date`, `trans_date`, `doc_id`, `doc_no`, `doc_type_id`, `contact_account_id`, `project_id`, `product_id`, `legal_entity_id`, `tax_code_id`, `description`, `invoice_no`, `trans_no`, `trans_line_no`, `attribute_id`, `bank_account_id`, `last_modified`, `last_modified_by`.

Analysis-dimension codes (Department, CostCentre, Fund, Project, Resource, Location, Activity, Intercon, Country, Income Type…) are **not** columns on `dac_gl` itself — they come from `LEFT JOIN [generated].[crv_gl] cg ON cg.id = g.id` (a materialized "pivot" of the tenant's custom analytic attributes). Same pattern for documents: `crv_doc_base`, `crv_doc_detail`.

**Documents — `dac_doc_base`** (alias `db`): `id`, `doc_no`, `doc_date`, `due_date`, `tax_date`, `status`, `net_amount`/`tax_amount`/`gross_amount` (base) + `*_currency_amount`, `currency`, `base_currency`, `contact_account_id`, `doc_type_id`, `doc_class`, `period_id`, `legal_entity_id`, `project_id`, `their_doc_no`, `their_ref`, `order_no`, `description`, `created_by`, `created_date`, plus boolean helper columns `status_is_draft`/`status_is_posted`/`status_is_abandoned`/`status_is_dispute`/`status_is_closed`.

**Document lines — `doc_detail`**: `doc_id`, `product_id`, `description`, `quantity`, `net_amount`/`tax_amount`/`gross_amount` (+ `*_currency_amount`), `tax_code_id`, `period_id`, `order_index`.

**Sign convention:** always multiply document amounts by `doc_type.mul_control` so credit notes/negatives come out correctly — never trust the raw stored sign on its own for a "by document type" report.

**`doc_type`** flags used constantly in joins/filters: `is_sale`, `is_purchase`, `is_credit_note`, `is_gl`, `has_outstandings`, `is_cb`, `doc_class`, `attribute_id`, `mul_control`.

**Outstanding/aged debt:** `doc_outstanding` (PK = doc id; `cur_outs_amount`, `posted_outs_amount`, `mul_control`), `doc_allocation (doc_id, alloc_doc_id, amount)`. Aged reports use table-valued functions: `dbo.GetAgedDebt(@col,@to_date)` / `dbo.GetAgedCreditors(@col,@to_date)`, bucketed with `CROSS APPLY dbo.GetIntervalRange(@IntervalId, <days>)` giving `range`/`range_index`.

**Status helpers** (scalar functions, take the raw `status` bitmask column): `StatusIsDraft`, `StatusIsPosted`, `StatusIsAbandoned`, `StatusIsDisputed`, `StatusIsReversed`, `StatusIsOutstanding`, `StatusIsClosed`, `StatusIsPendingAuth`, `StatusIsApproved`, `StatusIsRejected`, `StatusIsWrittenOff`.

**Contacts:** `contact_account` (`code`, `description`, `contact_classification_id`, `parent_contact_account_id`); `contact_customer` / `contact_supplier` share the same `id` and add `credit_limit`, `pay_term_id`, `contact_group_customer_id` / `contact_group_supplier_id`, `is_hold`, `is_stop`.

**Chart of accounts / periods:** `account` (`code`, `description`, `name`, `account_type`, `coa_group_id`, flags `ar_flag`/`ap_flag`/`cb_flag`/`control_flag`/`tax_flag`) → `coa_group`; `period` (`code`, `date_from`, `date_to`, `financial_year_id`, `is_bf`/`is_cf`/`is_adjustment`) → `financial_year` (`code`, `description`, `date_from`, `date_to`, `financial_year_group_id`, `previous_financial_year_id`) → `financial_year_group`.

**Other reference tables:** `legal_entity` (`code`,`description`,`currency`), `project`, `department`, `cost_centre`, `product` (`code`,`description`), `tax_code`, `bank_account`, `bank_transaction`, `resource`, `user_account`, `budget2`/`budget2_key`/`budget2_value(budget_key_id, period_id, amount)`, `credit_control_note`.

**Standard join fan-out for a GL enquiry** (this exact chain appears across dozens of enquiries): `g (dac_gl) → a (account) → le (legal_entity) → p (period) → fy (financial_year) → cg (crv_gl, left) → db (doc_base, left) → dt (doc_type) → ca (contact_account, left) → cs/cc (contact_supplier/customer, left) → prod (product, left) → proj (project, left)`.

**When unsure of a column,** query `INFORMATION_SCHEMA.COLUMNS` (and `sys.objects` / `sys.parameters` for functions) through the same preview-runner mechanism (§ Validation) rather than guessing.

## 3. Filters, parameters and prompts

Every `<Param>` becomes one input on the enquiry's parameter panel and is available as `@Name` inside `<Field>` filters.

```xml
<Param Name="LegalEntityId" ValueType="Text|Guid|Date|DateTime|Bit|Int32|Decimal"
       Setting="&lt;Setting Attribute=&quot;LegalEntity&quot; .../&gt;"
       Mandatory="True" Default="#today" Caption="Legal entity" Presenter="MultiGit" OrderIndex="0" Help="…"/>
```

- `Setting` is itself XML, HTML-entity-escaped, describing a catalog picker: `<Setting Attribute="LegalEntity|Customer|Supplier|ContactAccount|Account|Period|FinancialYear|FinancialYearGroup|DocType|Project|Department|CostCentre|Product|TaxCode|Currency|BankAccount|CoaGroup|ContactGroupCustomer|ContactClassification" ValueMember="ObjectId|Code" AllowClosed="True" Catalog="…" Filter="Extra.ar_flag=1"/>`. `Setting="false"` = plain scalar param (Date, Text, etc.), no picker.
- **Cascading pickers** use a nested `<Binding Name="OtherParamName" ValueType="…" PropertyName="…"/>` inside `Setting`, and a matching `Catalog=` name that iplicit resolves relative to that binding. Real cascade catalogs: `PeriodsForFYG_FY_LE`, `LegalEntitiesForFinancialGroup`, `FinancialYearGroupForLegalEntity`, `FinancialYearsForGroupOrDefaults`.
- Department/CostCentre-type params usually use `ValueMember="Code"` (they're text codes on `crv_gl`, not GUIDs) rather than `ObjectId`.
- **Default tokens:** `#today`, `#now`, `#fin_year`, `#def_financial_year_group`, `#def_legal_entity`, `#def_cur_code`, `#def_exchange_rate_type`, `#user`, `#ago(7d)`, plain literals, and the sentinel GUID `20000000-0000-0000-0000-000000000000` (means "current financial year", paired with `dbo.FinancialYearOrDefaultWithLegalEntity(@FinancialYear,@FinancialYearGroup,@LegalEntity)`).
- **The optional multi-select filter idiom** — appears on almost every dimension filter — is always a pair: `FilterOperator="In" FilterArgument="@X" FilterOr="@X is null"`. This is what makes a filter *optional*: SQL Server would otherwise evaluate `column IN (NULL)` as never-true when the user leaves the picker empty.
- **Date range idiom:** `FilterOperator="Between" FilterArgument="ISNULL(@DateFrom,{0}) AND ISNULL(@DateTo,{0})"` where `{0}` substitutes the field's own SQL — again so an empty bound doesn't exclude everything.
- A raw predicate that isn't tied to one param goes on `Filter="…"` directly on the `<Field>` (escaped `&quot;`), e.g. `Filter="[g].[period_date] &gt;= ISNULL(@PeriodDateFrom,[g].[period_date])"`.
- `ParamLayoutXml` default across virtually every enquiry: `<AutoPanel ItemWidth="380" ItemPadding="4,2,4,2" />`.

## 4. Calculated columns, aggregation, grouping, ordering

- `Type="Column"` — a plain passthrough of `Source.Sql`.
- `Type="Expression"` — any computed SQL: `CASE`, `FORMAT()`, string concatenation, scalar function calls. No `Source` needed if the SQL is self-contained (references sources by alias directly).
- `Type="Summary"` — an aggregate (`SUM`, `COUNT`, `MAX`, etc.). **Any field NOT marked Summary or Expression-without-aggregation becomes an implicit GROUP BY key** — the builder derives the GROUP BY from "everything that isn't a Summary field," so if a report unexpectedly groups too finely, the fix is almost always "one of your Column fields shouldn't be visible/output at that grain."
- `Type="Constant"` — a scalar subquery independent of the row set, e.g. `(select top 1 description from financial_year where id=@FinancialYear)`.
- `Output="False"` — filter-only field: contributes a WHERE predicate but never appears in the result set or the GROUP BY. Used for row-eligibility checks like `NotAbandoned`.
- Quarter/period bucketing is always done as a `CASE` on the last two characters of a period code, e.g. `CASE WHEN RIGHT([p].[code],2) IN ('01','02','03') THEN 'Q1' … END`.
- Ordering: `<Query OrderBy="…">` takes a raw ORDER BY clause at the query level; layouts additionally have their own `sortBy` for grid display, which is independent (the query's OrderBy affects what SQL Server returns before grouping; the layout's `sortBy` affects on-screen row order after the grid groups/pivots).

## 5. Advanced patterns

- **Subqueries / correlated scalars:** `Type="Constant"` fields, or inline `(SELECT …)` inside an `Type="Expression"` field's `Sql`.
- **Table-valued functions as a source:** `<Source Name="r" Type="Sql" Sql="select * from [dbo].[GetAgedDebt](@p_aged_date_column,@p_to_date) r" JoinType="Principal"/>` — used for the built-in aged-debt/creditor functions, and for any bespoke multi-statement logic that's easier to push into a SQL function than express as joins.
- **CROSS/OUTER APPLY:** valid `JoinType` values include `OuterApply`/`CrossApply` alongside `InnerJoin`/`LeftJoin` — used for per-row correlated table functions (e.g. `GetIntervalRange` for aging buckets).
- **UNION / UNION ALL:** additional `<Select Name="X" Union="UnionAll|Union">` blocks after the first. Every unioned Select must output the *same field names, in the same order*, as the first — there's no positional flexibility.
- **Filters on aggregated data (HAVING-equivalent):** the engine doesn't expose a literal `HAVING` clause in the XML grammar; the workaround seen in practice is either (a) wrap the aggregated Select as a subquery `Source Type="Sql"` and filter the outer Select on the aggregate alias, or (b) push the threshold into the grid layer via a groupData aggregator and let the user filter/sort interactively rather than server-side.
- **Multi-currency:** always carry both the base-currency field (`Amount`/`NetAmount`, no suffix) and the currency-native field (`CurrencyAmount`), plus `Currency` and `BaseCurrency` text columns — PropMetaJson's `amount` viewType needs `currencyMember` pointing at whichever of those two decides the symbol/precision shown, and that member field must be listed in `includes` (grid) or the value won't resolve.

## 6. Report-style vs. list-style enquiries

| | List enquiry | Report/pivot enquiry |
|---|---|---|
| Typical principal source | `dac_doc_base`, `dac_gl`, `contact_account` | `dac_gl` joined through `crv_gl`/`account`/`period` |
| Fields | Mostly `Column`/`Expression`, few or no `Summary` | Heavy use of `Summary` fields (sums), few raw columns |
| Layout | Flat `columns` list, no `groupRows`/`groupColumns` | `groupRows` (row hierarchy) + `groupColumns` (pivot axis, e.g. period/month/legal entity) + `groupData` (the aggregated cell) |
| `hierarchy` key | Absent | Present when rows follow a saved tree (e.g. "Standard chart of accounts", "Standard Balance Sheet tree") — **only use this when the row grouping genuinely follows that tree's structure**; bolting an unrelated row-grouping field (e.g. Department) in front of a tree-driven `AccountId` group breaks the grid and returns no data (confirmed empirically) |
| `detail` block | Not needed | Defines the drill-down grid shown when a user expands a pivoted cell — usually the same field set as the flat/list version of the same data |
| Typical `Group` value | Matches the document type's module (`Sale`, `Purchase`, `AR`) | `GL` |

## 7. Decision tree — plain English → build plan

1. **What's the grain of one output row?** A GL posting → `dac_gl` principal. A document (invoice/order/journal header) → `dac_doc_base` principal. A document line → `doc_detail` joined to its header. A balance/summary by some dimension → `dac_gl` + `Summary` fields, no document join needed unless a document-level attribute (doc no, contact) is wanted alongside the total.
2. **Does it need to respect legal-entity security?** Always, unless it's a pure reference-data lookup (e.g. product list) — use the `dac_*` view, not the base table.
3. **What dimensions is it sliced/filtered by?** Standard business dims → check whether they're base-table columns (`account_id`, `contact_account_id`, `project_id`, `legal_entity_id`, `period_id` are directly on `dac_gl`/`dac_doc_base`) or custom analytic dims (Department, CostCentre, Fund, Resource, Location, Activity, Intercon, Country, IncomeType) → those need the `crv_gl`/`crv_doc_base` left join.
4. **Does the user want to filter by something on a related entity** (customer group, tax code, doc type flag)? Join that table and filter there — don't try to filter GL by a column that only exists after a join, without adding the join.
5. **Is it a total/summary, or a list of transactions?** Summary → mark the amount field(s) `Type="Summary"`, everything else becomes an implicit grouping key — keep that set as small as makes sense for the grain requested. List → all `Column`/`Expression`, no `Summary`.
6. **What does the user want to slice by interactively** (pivot columns) vs. **filter down before running** (params)? Recurring, "always narrow it first" dimensions (legal entity, date range, currency) → params. "Compare across these" dimensions (department, month, legal entity) → layout `groupRows`/`groupColumns`, not query params — the same query can support several tabs/layouts pivoting differently.
7. **Does the request reference document status** ("outstanding", "posted only", "excluding drafts")? Use the relevant `StatusIsX` scalar function as an `Output="False"` filter field, or `has_outstandings`/`doc_outstanding` for aged/open-item reporting.
8. **Does it need a running total, ranking, or period-over-period comparison?** These live in the layout (`groupColumns` pivoted by period, `groupData` aggregator), not in the SQL — the query stays a flat aggregate-by-dimension result and the grid does the shaping.
9. **Which permission/module does this belong to?** Pick the nearest `RequiredPermissions` entry from the table in § 8's generator (`GeneralLedger.*` for GL, `SaleInvoice.Enquiry`/`Customer.Enquiry` for sales, etc.) — omitting this leaves **Create** disabled with no visible error, the single most common reason a generated enquiry "doesn't work."

## 8. SQL/enquiry generation template

Use `enqgen.py` (below) rather than hand-assembling the XML/JSON — it gets attribute escaping, `$id` numbering, and the base64 envelope right every time.

```python
"""Build an iplicit enquiry export (paste via Enquiries > ⋮ > Import from clipboard)."""
import json, base64, datetime
from xml.sax.saxutils import escape

def setting(attribute=None, value_member="ObjectId", allow_closed=True, catalog=None, filter=None, display_member=None, bindings=()):
    a = []
    if attribute: a.append(f'Attribute="{attribute}"')
    if catalog: a.append(f'Catalog="{catalog}"')
    if value_member: a.append(f'ValueMember="{value_member}"')
    if display_member: a.append(f'DisplayMember="{display_member}"')
    if allow_closed: a.append('AllowClosed="True"')
    if filter: a.append('Filter="' + escape(filter, {'"': '&quot;'}) + '"')
    if bindings:
        inner = "".join(f'\n  <Binding Name="{n}" ValueType="{t}" PropertyName="{p}"/>' for n, t, p in bindings)
        return f'<Setting {" ".join(a)}>{inner}\n</Setting>'
    return f'<Setting {" ".join(a)} />'

def param(name, caption, value_type="Text", presenter="MultiGit", setting_xml="false", default=None, mandatory=False, help=None):
    return dict(name=name, caption=caption, value_type=value_type, presenter=presenter, setting=setting_xml, default=default, mandatory=mandatory, help=help)

def src(name, sql, type="Table", join="Principal", on=None):
    return dict(name=name, sql=sql, type=type, join=join, on=on)

def fld(name, sql, source=None, type=None, op=None, arg=None, orr=None, output=True, filter=None):
    if type is None: type = "Column" if source else "Expression"
    return dict(name=name, sql=sql, source=source, type=type, op=op, arg=arg, orr=orr, output=output, filter=filter)

def multi_filter(name, sql, source, param):
    """Standard optional multi-select filter: In @param, or @param is null."""
    return fld(name, sql, source, op="In", arg=f"@{param}", orr=f"@{param} is null")

def _esc(v): return escape(str(v), {'"': '&quot;', '\n': '&#xA;', '\r': '&#xD;', '\t': '&#x9;'})
def _a(k, v): return f' {k}="{_esc(v)}"' if v is not None else ''

def query_xml(params, selects, order_by=None):
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

def meta(name, label, data_type="text", view_type="text", width=100, **settings):
    m = {"label": label, "defaultWidth": width, "visible": True, "dataType": data_type, "viewType": view_type, "name": name}
    if settings: m["settings"] = settings
    return m

PERM = {
  "GeneralLedger.Enquiry": "693B164B-B59F-4946-97B7-CD01465847A7",
  "GeneralLedger.TrialBalance": "57257282-A05B-49EA-A625-1AEE2BF5F941",
  "GeneralLedger.ProfitLoss": "FC25F7A9-2A3C-471A-8A4E-6DD29434F3D9",
  "GeneralLedger.BalanceSheet": "F4EB155F-D660-46B2-A84E-47395EFD2A82",
  "GeneralLedger.FinancialStatements": "1245D473-C508-4301-95A2-AE6A46D547C3",
  "Customer.Enquiry": "DC6FF301-E2D6-4933-8CEF-3347F7DDD177",
  "Supplier.Enquiry": "9B4A71B5-8D55-420F-A876-4F8DF2C1E7BE",
  "SaleInvoice.Enquiry": "39E3B643-9552-457D-B402-82C2E9DB6B71",
  "PurchaseInvoice.Enquiry": "CF0EF798-1361-4D9D-8B8A-8CB7AFD2CA33",
  "PurchaseOrder.Enquiry": "DF4241B0-213E-47F9-971B-9CDDDA30FB90",
  "AR.Enquiry": "F15CFADC-7A9F-4443-8492-A8A1581B0D5F",
  "AR.CreditControl": "614BDC2F-13EC-455D-B0CE-504AE574ED03",
  "DocBase.Enquiry": "8891D6F9-6D92-4612-B367-D526C57F5A8D",
  "Account.Enquiry": "BC44A19C-6115-4449-8947-20BE34F68B1A",
  "BankReconciliation.Enquiry": "A879D371-33DA-4C5E-AF3B-E66FAFA28275",
  "Cashbook.Enquiry": "C212B965-02C9-4A27-A8C4-F9869D4ADC84",
  "Receipt.Enquiry": "DCC5113B-808E-4669-94F2-D2EC5D01AE56",
  "Payment.Enquiry": "EB62FCA0-71A2-4894-B652-400214654700",
  "VatReturn.Enquiry": "8E603BD5-2DAC-4359-9639-79B0DC3B020A",
  "ManualJournal.Enquiry": "20DF7F94-FC51-4A48-8D65-9D88F7075954",
  "BudgetForecast.Enquiry": "AF31AA72-1F3D-4352-9216-F4849A2B5166",
  "Project.FinancialStatements": "F20AAECE-BAF9-45B8-A87F-866EA8717E66",
  "UserAccount.Enquiry": "C421DF21-BE87-4533-86EE-7400480E9CB5",
  "TimesheetDoc.Enquiry": "015EFA02-F4D0-4FCA-83F0-1928BEEB948D",
}

def m_catalog(name, label, attribute, width=150, **kw): return meta(name, label, "guid", "catalog", width, attribute=attribute, **kw)
def m_amount(name, label, currency_member="BaseCurrency", width=110): return meta(name, label, "decimal", "amount", width, currencyMember=currency_member)
def m_date(name, label, width=95): return meta(name, label, "date", "date", width)
def m_text(name, label, width=120): return meta(name, label, "text", "text", width)
def m_link(name, label, id_member="DocId", attribute_member="Attribute", width=130): return meta(name, label, "text", "link", width, idMember=id_member, attributeMember=attribute_member)
def m_status(name="Status", label="Status"): return meta(name, label, "int64", "status", 22)
def m_int(name, label, width=80): return meta(name, label, "int32", "integer", width)
def m_bit(name, label, width=60): return meta(name, label, "bit", "checkbox", width)

def layout(description, columns, group_rows=None, group_columns=None, group_data=None, includes=None, widths=None,
           sort_by=None, group_rows_expand=None, detail=None, extra=None):
    g = {"columns": columns}
    if group_rows: g["groupRows"] = group_rows
    if group_columns: g["groupColumns"] = group_columns
    if group_data: g["groupData"] = group_data
    if includes: g["includes"] = includes
    if widths: g["widths"] = widths
    if sort_by: g["sortBy"] = sort_by
    if group_rows_expand is not None: g["groupRowsExpand"] = group_rows_expand
    if detail: g["detail"] = detail
    if extra: g.update(extra)
    return {"description": description, "def": json.dumps({"layout": {"grid": g}}, indent=2)}

def build(description, group, qxml, propmeta, layouts, permissions=(), auto_refresh=False, param_layout='<AutoPanel ItemWidth="380" ItemPadding="4,2,4,2" />'):
    model = {
        "$id": "1", "LinkedAttributes": [], "SharedWith": [],
        "EnquiryLayouts": [{"$id": str(i + 2), "Code": "JsonLayout", "ContainerDefinition": l["def"], "Description": l["description"], "OrderIndex": i}
                           for i, l in enumerate(layouts)],
        "RequiredPermissions": [{"$id": str(100 + i), "AttributeOperationId": pid.lower()} for i, pid in enumerate(permissions)], "AnalyticGroups": [],
        "AutoRefresh": auto_refresh, "Description": description, "Group": group,
        "ParamLayoutXml": param_layout, "PreferReplica": True,
        "PropMetaJson": json.dumps(propmeta, indent=2), "QueryXml": qxml,
    }
    data = base64.b64encode(json.dumps(model, ensure_ascii=False).encode("utf-8")).decode()
    env = {"type": "DbEnquiry", "description": description,
           "exportDate": datetime.datetime.now().strftime("%d/%m/%Y %H:%M"), "data": data}
    return json.dumps(env, indent=2), model
```

## 9. Validation checklist

Run through this before handing an enquiry over:

- [ ] Principal source is a `dac_*` view where one exists (not the base table), for legal-entity security.
- [ ] Every optional dimension filter uses the `FilterOperator="In" FilterArgument="@X" FilterOr="@X is null"` pair (not a bare `In`, which excludes everything when the param is empty).
- [ ] Every date-range filter uses `ISNULL(@From,{0}) AND ISNULL(@To,{0})`, not a bare `Between @From AND @To`.
- [ ] At least one `RequiredPermissions` entry is set — otherwise Create silently stays disabled.
- [ ] Amount fields carry the sign correctly — document amounts multiplied by `mul_control` where credit notes/negatives matter.
- [ ] Every field intended to show in the grid is NOT accidentally forcing a finer GROUP BY than intended (check for stray `Column`/`Expression` fields that aren't `Summary` and aren't needed at the display grain).
- [ ] `amount` viewType columns have their `currencyMember` field present in the layout's `includes` — otherwise the currency symbol/precision won't resolve.
- [ ] Analytic dimensions (Department, CostCentre, etc.) are pulled from the `crv_gl`/`crv_doc_base` join, not assumed to be columns on `dac_gl`/`dac_doc_base` directly.
- [ ] If using a saved row `hierarchy` (a coa/BS/PL tree), the layout's `groupRows` is *only* the field that tree is built on (typically `AccountId`) — don't add another field in front of it; that combination returns no data.
- [ ] Every `<Select>` in a union outputs the same field names, same order, as the first.
- [ ] Import the JSON once via **Enquiries > ⋮ > Import from clipboard**, confirm the preview grid actually returns rows with realistic parameter defaults, *before* telling the user it's done.
- [ ] `Description` and `Group` are set to something a user would recognise in the enquiry menu — don't leave a generic placeholder name.

### Live validation trick (needs a browser session, e.g. Claude in Chrome, on the sandbox tab)

Install this hook, add a throwaway `Sql` source (`select 1 as x`) so Preview is clickable, then override the query and click **Preview data**:

```js
window.__resp=[];(()=>{const oo=XMLHttpRequest.prototype.open,os=XMLHttpRequest.prototype.send;
XMLHttpRequest.prototype.open=function(m,u,...r){this.__u=String(u).split('?')[0];return oo.call(this,m,u,...r)};
XMLHttpRequest.prototype.send=function(b){if(this.__u&&/queryXml$/.test(this.__u)&&typeof b==='string'&&window.__ovr){const o=JSON.parse(b);o.QueryXml=window.__ovr;o.Take=window.__take||200;b=JSON.stringify(o);window.__ovr=null}
this.addEventListener('load',()=>window.__resp.push({u:this.__u,t:this.responseText}));return os.call(this,b)}})();
```
Then `window.__ovr = <QueryXml string>` and click Preview. `JSON.parse(window.__resp.pop().t)` returns `{QuerySql, Data:{columns,data}}` or a SQL error — the fastest way to catch a bad join/filter before handing the enquiry over. This same mechanism is how the schema knowledge in this document was originally verified against 640 real definitions, and it's the fast alternative to a Playwright PC-scrape if you ever want the raw corpus of every enquiry's SQL for archival (two `SELECT * FROM dbo.enquiry` / `dbo.enquiry_layout` queries, not a UI walk of every enquiry).

## 10. Example mappings (plain English → pattern)

| Request | Pattern |
|---|---|
| "Sales by customer by month" | `dac_doc_base` + `doc_type` (is_sale), `Summary` on net amount, layout `groupRows:["ContactAccountId"]`, `groupColumns:[{"field":"Month","total":true}]` — *tested end-to-end.* |
| "Balance sheet by department then nominal" | `dac_gl` + `crv_gl` (Department) + `account`, two-level `groupRows:["Department","AccountId"]`, **no** `hierarchy` (conflicts with the multi-level row group), `groupData` sum on `Amount`. |
| "Who last touched this GL account (chart of accounts), not the transaction" | Join `account` (alias `a`) directly and pull `a.last_modified_by`/`a.last_modified` — do **not** use `dac_gl.last_modified_by`, which is the *posting's* audit stamp, not the account master record's. |
| "AR aged debt by customer" | `dbo.GetAgedDebt(@col,@to_date)` as principal `Sql` source, `CROSS APPLY dbo.GetIntervalRange(...)` for buckets, group by `ContactAccountId` + `range`. |
| "Trial balance for a period" | `dac_gl` + `account` + `period`, `Summary` sum on `Amount`, filter `period_id` via the `PeriodsForFYG_FY_LE` cascade catalog off Legal Entity/Financial Year params. |
| "Overdue purchase invoices" | `dac_doc_base` + `doc_type` (is_purchase), join `doc_outstanding`, filter `due_date < @AsOfDate` and `cur_outs_amount <> 0`. |
| "GL detail for one nominal, with cost centre" | `dac_gl` + `crv_gl` (CostCentre) + `account`, flat list layout (no groupRows), filtered on `AccountId` via the standard `In @X OR @X is null` idiom. |
| "Top 10 customers by revenue this year" | `dac_doc_base` (is_sale), `Summary` sum on net amount grouped by `ContactAccountId`, `OrderBy` descending on the summary alias, `Take`/layout row limit for the top-N (SQL-level TOP isn't exposed per-group; do the ranking in the grid or a wrapping `Sql` source). |
| "Sales tax return figures" | `dac_gl`/`dac_doc_base` joined to `tax_code`, filtered to the VAT return period, commonly built as a `Sql` source wrapping the standard VAT calculation rather than reproduced inline. |
| "Bank reconciliation outstanding items" | `bank_transaction` + `bank_account`, filtered on reconciliation status flags. |
| "Profit & loss by month, current year" | `dac_gl` + `account` (P&L account_type), `hierarchy` = the P&L tree, `groupColumns` pivoted by `Month`/`PeriodId`. |
| "Documents last modified by a given user" | `dac_doc_base` filtered on `created_by`/`last_modified_by` via a `UserAccount` catalog param, `ValueMember="Code"`. |
| "Manual journals posted in a date range" | `dac_gl` filtered `doc_type_id` to the manual-journal type, date range on `post_date` via the ISNULL idiom. |
| "Customer statement (all open items)" | `dac_doc_base` + `doc_outstanding`, filtered `contact_account_id = @Customer`, `has_outstandings=1` doc types only. |
| "Budget vs actual by cost centre" | `budget2_value` joined to `budget2_key` and `period`, unioned or joined against the equivalent `dac_gl` actuals aggregate on the same keys. |
| "Purchase orders not yet fully received" | `dac_doc_base` (is_purchase, PO doc type) joined to a receipt-quantity aggregate on `doc_detail`, filtered where received < ordered. |
| "Intercompany balances between legal entities" | `dac_gl` + `crv_gl` (Intercon dimension), grouped by `LegalEntityId` and `Intercon`. |
| "Credit notes issued this quarter" | `dac_doc_base` + `doc_type` (`is_credit_note=1`), `Quarter` computed via the `RIGHT(period.code,2)` CASE pattern, base amount with `mul_control` applied. |
| "Resource utilisation / timesheet report" | `TimesheetDoc.Enquiry` permission family, principal on the timesheet document table joined to `resource` and `project`. |

---
*Built from the sandbox's real definitions and one live end-to-end test; extend it (§10 especially) every time a new enquiry is built and confirmed working — see `IPLICIT_ENQUIRY_QUICK_SKILL.md` for the condensed version to paste into Project Instructions.*
