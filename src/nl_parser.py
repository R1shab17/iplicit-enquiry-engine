"""
A rule-based, keyword-matching prototype that turns a plain-English request
for a GL enquiry into an EnquirySpec (src/spec.py).

Read that word again: **rule-based keyword matching, not natural language
understanding.** This is a fixed vocabulary lookup (docs/ROADMAP.md item 10
called it a "heuristic/keyword-based nl_parser.py prototype" deliberately,
to avoid overstating what it does). It will:

  - recognize a small, fixed set of dimension/measure/filter phrases
    (src/spec.py's KNOWN_DIMENSIONS/KNOWN_MEASURES/KNOWN_FILTERS) anywhere
    in the sentence, case-insensitively;
  - silently miss anything phrased differently ("split by" instead of "by",
    a dimension it doesn't know about, a filter it doesn't recognize);
  - never infer intent beyond that vocabulary — an unrecognized noun is
    just dropped, not guessed at.

Always read `spec.notes` (and, after compiling, compiler.py's own warnings)
before trusting what this produces — this is meant to save typing for the
common case, not to replace understanding what enquiry you're actually
asking for. It has no connection to any actual NLP/ML model.
"""
import re

from spec import EnquirySpec, KNOWN_DIMENSIONS, KNOWN_MEASURES, KNOWN_FILTERS

_MONTHLY_RE = re.compile(r"\bby month\b|\bmonthly\b|\bper month\b")


def parse(text: str) -> EnquirySpec:
    """Best-effort keyword extraction. Never raises on unrecognized input —
    an empty/unmatched sentence just produces a thin spec with a note
    explaining why, so the caller (or compiler.py) can decide what to do
    rather than have this module silently invent something plausible."""
    t = (text or "").lower()
    notes = []

    dimensions = []
    for phrase, column in KNOWN_DIMENSIONS.items():
        if phrase in t and column not in dimensions:
            dimensions.append(column)

    measures = [m for m in KNOWN_MEASURES if m in t]
    # "net balance" also contains "balance"/"net" as substrings of the
    # dedicated KNOWN_MEASURES entries above — dedupe by mapped meaning,
    # not surface phrase, since compiler.py treats them identically anyway.
    if "net balance" in measures:
        measures = [m for m in measures if m not in ("net", "balance")] + ["net balance"]

    filters = []
    for phrase, param_name in KNOWN_FILTERS.items():
        if phrase in t and param_name not in filters:
            filters.append(param_name)
    if "financial year" in t and "financial year group" in t:
        notes.append("Saw both 'financial year' and 'financial year group' — only FinancialYear "
                     "is recognized as a filter; a financial-year-group cascading picker needs a "
                     "hand-written build script (see src/build_library.py's FinancialYearGroupId example).")

    pivot_by_month = bool(_MONTHLY_RE.search(t))

    # Simplifying assumption, stated in EnquirySpec's own docstring: group by
    # whatever dimensions were named. This is the right reading for "GL by
    # department and cost centre" but not for every possible phrasing.
    group_by = list(dimensions)

    if not dimensions and not measures:
        notes.append("No recognized dimension or measure keywords found in the request — "
                      "this spec is too thin to compile into a meaningful enquiry as-is; "
                      "treat this as a starting point, not a finished spec.")

    return EnquirySpec(
        module="GL",  # the only module src/compiler.py currently supports
        description=(text or "").strip() or "Compiled GL enquiry",
        dimensions=dimensions,
        measures=measures,
        filters=filters,
        group_by=group_by,
        pivot_by_month=pivot_by_month,
        notes=notes,
    )
