"""
EnquirySpec: a structured, intermediate stop between "a sentence describing
a report" and enqgen.py's build functions.

Why this exists now and not earlier (docs/PROJECT_AUDIT.md #9, item 7 /
docs/ROADMAP.md item 10): building a natural-language front end on top of
the old ad-hoc dicts (before src/ir.py existed) would have meant redoing it
once a typed representation existed anyway. This module, src/nl_parser.py,
and src/compiler.py are that front end, built now that the IR/validator/
doctor are in place to check whatever comes out the other end.

Scope, stated plainly rather than oversold: this pipeline currently
recognizes and compiles GL-grain enquiries only (a single Select over
dac_gl + the standard join fan-out, optionally grouped by one or more
confirmed crv_gl dimension columns, with a balance/amount measure). It does
not attempt documents, AR/AP, unions, hierarchies, or table-valued-function
sources — those still need a hand-written build script, exactly as every
other enquiry in generated/ does today. Nothing here talks to a live
iplicit tenant, and nothing here bypasses enquiry_validator.py /
enquiry_doctor.py — nl_parser.py's output still needs both before it's
trusted, same as any hand-written script.
"""
from dataclasses import dataclass, field
from typing import List

# Recognized dimension phrases -> the crv_gl column name they resolve to
# (docs/SCHEMA.md's "Analytic-dimension views" section — these are the only
# dimension names actually confirmed to exist on crv_gl). Anything not in
# this map is left unrecognized rather than guessed at.
KNOWN_DIMENSIONS = {
    "department": "Department",
    "cost centre": "CostCentre",
    "cost center": "CostCentre",
    "fund": "Fund",
    "resource": "Resource",
    "location": "Location",
    "activity": "Activity",
    "intercompany": "Intercon",
    "intercon": "Intercon",
    "country": "Country",
    "income type": "IncomeType",
}

# Recognized measure phrases. Only "balance"/"net"/"amount" compile to a
# real column (dac_gl.amount) — src/compiler.py flags anything else
# (e.g. "debit", "credit") as unconfirmed rather than fabricating a split
# that doesn't exist as a separate column on dac_gl.
KNOWN_MEASURES = {"balance", "net balance", "net", "amount", "debit", "credit"}

# Recognized filter phrases -> the Param name compile_spec() will declare.
KNOWN_FILTERS = {
    "legal entity": "LegalEntityId",
    "period": "PeriodId",
    "financial year": "FinancialYear",
    "date range": "DateRange",
}


@dataclass
class EnquirySpec:
    """The output of src/nl_parser.py and the input to src/compiler.py.

    module      -- only "GL" is compiled today (src/compiler.py raises
                   NotImplementedError for anything else).
    description -- becomes the enquiry's Description.
    dimensions  -- crv_gl column names (values from KNOWN_DIMENSIONS) to
                   include as output columns.
    measures    -- raw measure phrases as recognized (values from
                   KNOWN_MEASURES) — compiler.py decides how/whether each
                   compiles to a real field.
    filters     -- Param names (values from KNOWN_FILTERS) to declare.
    group_by    -- subset of `dimensions` to use as groupRows. Defaults to
                   all of `dimensions` (src/nl_parser.py's simplifying
                   assumption: "show me X by Y" is read as "group by Y").
    pivot_by_month -- whether a monthly groupColumns pivot was requested.
    notes       -- the parser's own honesty trail: ambiguities, unrecognized
                   input, or assumptions made while building this spec. Not
                   the same as compiler.py's own warnings (returned
                   separately by compile_spec()) — these are about what the
                   *parser* couldn't resolve; compiler.py's are about what
                   the *compiler* couldn't confirm against known schema.
    """
    module: str
    description: str
    dimensions: List[str] = field(default_factory=list)
    measures: List[str] = field(default_factory=list)
    filters: List[str] = field(default_factory=list)
    group_by: List[str] = field(default_factory=list)
    pivot_by_month: bool = False
    notes: List[str] = field(default_factory=list)
