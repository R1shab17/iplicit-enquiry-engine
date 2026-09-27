"""
Decode a DbEnquiry export envelope (or an already-loaded model dict) into
the same structured shape enqgen.py builds from: params, selects
(sources + fields), layouts, and permissions.

Used by enquiry_validator.py to check structure, and — the other direction
from enqgen.py — for round-tripping a real enquiry export dropped into
corpus/real_enquiries/, so it can be diffed field-for-field against a
generated one (see docs/ARCHITECTURE.md).

Nothing here talks to a live iplicit tenant; it only decodes JSON/XML
already on disk.
"""
import json
import base64
import xml.etree.ElementTree as ET

from ir import Enquiry


class ParseError(Exception):
    pass


def load_envelope(path):
    """Read a DbEnquiry export file and return (envelope_dict, model_dict)."""
    with open(path, encoding="utf-8") as f:
        env = json.load(f)
    return env, decode_model(env)


def decode_model(env):
    """Decode the base64 `data` field of an envelope dict into the model dict."""
    try:
        raw = base64.b64decode(env["data"])
    except Exception as e:
        raise ParseError(f"could not base64-decode envelope 'data': {e}")
    try:
        return json.loads(raw.decode("utf-8"))
    except Exception as e:
        raise ParseError(f"decoded envelope data is not valid JSON: {e}")


def parse_query_xml(qxml):
    """Parse QueryXml into an ElementTree root. Raises ParseError on
    malformed XML rather than returning None, so callers don't need to
    remember to check."""
    try:
        return ET.fromstring(qxml)
    except ET.ParseError as e:
        raise ParseError(f"QueryXml is not well-formed XML: {e}")


def params_of(root):
    """List of dicts, one per <Param>, with its raw attributes."""
    return [p.attrib for p in root.findall("Param")]


def selects_of(root):
    """List of dicts, one per <Select>, each:
        {"name": str, "union": str|None, "element": Element,
         "sources": [Element, ...], "fields": [Element, ...]}
    Elements are kept (not just attrib dicts) so callers can still use
    ElementTree accessors like .get() with defaults.
    """
    out = []
    for sel in root.findall("Select"):
        out.append({
            "name": sel.get("Name"),
            "union": sel.get("Union"),
            "element": sel,
            "sources": sel.findall("Source"),
            "fields": sel.findall("Field"),
        })
    return out


def output_field_names(select):
    """Names of a parsed select's fields where Output != 'False'."""
    return [f.get("Name") for f in select["fields"] if f.get("Output") != "False"]


def principal_source(select):
    """The Source with JoinType=Principal, or the first Source if none is marked."""
    sources = select["sources"]
    return next((s for s in sources if s.get("JoinType") == "Principal"), sources[0] if sources else None)


def prop_meta_of(model):
    """Decode PropMetaJson into a dict. Raises ParseError if invalid."""
    try:
        return json.loads(model["PropMetaJson"])
    except Exception as e:
        raise ParseError(f"PropMetaJson is not valid JSON: {e}")


def layouts_of(model):
    """List of dicts, one per EnquiryLayouts entry:
        {"description": str, "grid": dict}
    Raises ParseError if any ContainerDefinition is invalid JSON.
    """
    out = []
    for entry in model.get("EnquiryLayouts", []):
        desc = entry.get("Description", "?")
        try:
            cd = json.loads(entry["ContainerDefinition"])
        except Exception as e:
            raise ParseError(f"layout '{desc}': ContainerDefinition is not valid JSON: {e}")
        out.append({"description": desc, "grid": cd.get("layout", {}).get("grid", {})})
    return out


def permissions_of(model):
    """List of AttributeOperationId strings required by this enquiry."""
    return [p.get("AttributeOperationId") for p in model.get("RequiredPermissions", [])]


def parse(path_or_env):
    """Top-level convenience: given a file path or an already-loaded envelope
    dict, return a fully structured dict:
        {"env": ..., "model": ..., "query_root": Element,
         "params": [...], "selects": [...], "prop_meta": {...},
         "layouts": [...], "permissions": [...], "ir": Enquiry}
    Raises ParseError on any structural problem, with a message identifying
    which part failed. `ir` is the typed src/ir.py Enquiry built from the
    same data — prefer it for any new cross-reference logic (see
    docs/PROJECT_AUDIT.md #9).
    """
    if isinstance(path_or_env, str):
        env, model = load_envelope(path_or_env)
    else:
        env = path_or_env
        model = decode_model(env)

    query_root = parse_query_xml(model.get("QueryXml", ""))
    parsed = {
        "env": env,
        "model": model,
        "query_root": query_root,
        "params": params_of(query_root),
        "selects": selects_of(query_root),
        "prop_meta": prop_meta_of(model),
        "layouts": layouts_of(model),
        "permissions": permissions_of(model),
    }
    parsed["ir"] = Enquiry.from_parsed(parsed)
    return parsed
