"""
Enquiry Diff: semantic comparison of two DbEnquiry export files.

Usage:
    python3 enquiry_diff.py <a>.json <b>.json

Built for two situations (docs/PROJECT_AUDIT.md #9 item 5): comparing a
generated draft against a real export once one is available in
corpus/real_enquiries/, and comparing two generated drafts against each
other (e.g. before/after a build_library.py edit). Textual diff of the raw
base64 envelope or even the decoded JSON is nearly useless here — field
order, whitespace, and $id counters shift for reasons that have nothing to
do with meaning. This walks the same src/ir.py structures
enquiry_validator.py uses and reports differences by name, not by line.
"""
import sys

from enquiry_parser import parse, ParseError


def _index_by(items, key):
    return {key(i): i for i in items if key(i) is not None}


def diff_params(a_params, b_params):
    a = _index_by(a_params, lambda p: p.name)
    b = _index_by(b_params, lambda p: p.name)
    added = sorted(set(b) - set(a))
    removed = sorted(set(a) - set(b))
    changed = []
    for name in sorted(set(a) & set(b)):
        pa, pb = a[name], b[name]
        for attr in ("caption", "value_type", "presenter", "default", "mandatory", "setting"):
            va, vb = getattr(pa, attr), getattr(pb, attr)
            if va != vb:
                changed.append((name, attr, va, vb))
    return {"added": added, "removed": removed, "changed": changed}


def diff_fields(a_fields, b_fields):
    a = _index_by(a_fields, lambda f: f.name)
    b = _index_by(b_fields, lambda f: f.name)
    added = sorted(set(b) - set(a))
    removed = sorted(set(a) - set(b))
    changed = []
    for name in sorted(set(a) & set(b)):
        fa, fb = a[name], b[name]
        for attr in ("sql", "source", "type", "op", "arg", "orr", "output", "filter"):
            va, vb = getattr(fa, attr), getattr(fb, attr)
            if va != vb:
                changed.append((name, attr, va, vb))
    return {"added": added, "removed": removed, "changed": changed}


def diff_sources(a_sources, b_sources):
    a = _index_by(a_sources, lambda s: s.name)
    b = _index_by(b_sources, lambda s: s.name)
    added = sorted(set(b) - set(a))
    removed = sorted(set(a) - set(b))
    changed = []
    for name in sorted(set(a) & set(b)):
        sa, sb = a[name], b[name]
        for attr in ("sql", "type", "join", "on"):
            va, vb = getattr(sa, attr), getattr(sb, attr)
            if va != vb:
                changed.append((name, attr, va, vb))
    return {"added": added, "removed": removed, "changed": changed}


def diff_selects(a_selects, b_selects):
    """Selects are compared positionally (by index) — a union's Select
    order is meaningful (the first Select sets the field-name contract the
    rest must match), so reordering IS a real change, unlike params/fields/
    sources within a Select, which are compared by name."""
    results = []
    n = max(len(a_selects), len(b_selects))
    for i in range(n):
        sa = a_selects[i] if i < len(a_selects) else None
        sb = b_selects[i] if i < len(b_selects) else None
        if sa is None:
            results.append({"index": i, "status": "added", "name": sb.name})
            continue
        if sb is None:
            results.append({"index": i, "status": "removed", "name": sa.name})
            continue
        results.append({
            "index": i,
            "status": "compared",
            "name_a": sa.name, "name_b": sb.name,
            "union_a": sa.union, "union_b": sb.union,
            "sources": diff_sources(sa.sources, sb.sources),
            "fields": diff_fields(sa.fields, sb.fields),
        })
    return results


def diff_layouts(a_layouts, b_layouts):
    a = _index_by(a_layouts, lambda l: l.description)
    b = _index_by(b_layouts, lambda l: l.description)
    added = sorted(set(b) - set(a))
    removed = sorted(set(a) - set(b))
    changed = []
    for desc in sorted(set(a) & set(b)):
        la, lb = a[desc], b[desc]
        for attr in ("columns", "group_rows", "group_columns", "group_data", "includes", "hierarchy"):
            va, vb = getattr(la, attr), getattr(lb, attr)
            if va != vb:
                changed.append((desc, attr, va, vb))
    return {"added": added, "removed": removed, "changed": changed}


def diff_permissions(a_perms, b_perms):
    a, b = set(a_perms), set(b_perms)
    return {"added": sorted(b - a), "removed": sorted(a - b)}


def diff(path_a, path_b):
    """Returns a structured dict covering description/group, params,
    selects (sources+fields per select), layouts, and permissions."""
    parsed_a = parse(path_a)
    parsed_b = parse(path_b)
    ir_a, ir_b = parsed_a["ir"], parsed_b["ir"]

    return {
        "description": (ir_a.description, ir_b.description),
        "group": (ir_a.group, ir_b.group),
        "params": diff_params(ir_a.params, ir_b.params),
        "selects": diff_selects(ir_a.selects, ir_b.selects),
        "layouts": diff_layouts(ir_a.layouts, ir_b.layouts),
        "permissions": diff_permissions(ir_a.permissions, ir_b.permissions),
    }


def _format_group(title, g, empty_ok=True):
    lines = []
    if g["added"]:
        lines.append(f"  + added: {g['added']}")
    if g["removed"]:
        lines.append(f"  - removed: {g['removed']}")
    if g.get("changed"):
        for entry in g["changed"]:
            *key_parts, va, vb = entry
            key = "/".join(str(k) for k in key_parts)
            lines.append(f"  ~ changed {key}: {va!r} -> {vb!r}")
    if not lines and empty_ok:
        return ""
    return f"{title}\n" + "\n".join(lines) + "\n" if lines else ""


def format_diff(d) -> str:
    lines = []
    if d["description"][0] != d["description"][1]:
        lines.append(f"Description: {d['description'][0]!r} -> {d['description'][1]!r}")
    if d["group"][0] != d["group"][1]:
        lines.append(f"Group: {d['group'][0]!r} -> {d['group'][1]!r}")

    lines.append(_format_group("PARAMS", d["params"]))

    for sel in d["selects"]:
        if sel["status"] == "added":
            lines.append(f"SELECT[{sel['index']}]: added (name={sel['name']!r})")
            continue
        if sel["status"] == "removed":
            lines.append(f"SELECT[{sel['index']}]: removed (name={sel['name']!r})")
            continue
        sources_txt = _format_group(f"SELECT[{sel['index']}] SOURCES", sel["sources"])
        fields_txt = _format_group(f"SELECT[{sel['index']}] FIELDS", sel["fields"])
        if sel["name_a"] != sel["name_b"]:
            lines.append(f"SELECT[{sel['index']}] name: {sel['name_a']!r} -> {sel['name_b']!r}")
        if sel["union_a"] != sel["union_b"]:
            lines.append(f"SELECT[{sel['index']}] union: {sel['union_a']!r} -> {sel['union_b']!r}")
        if sources_txt:
            lines.append(sources_txt.rstrip())
        if fields_txt:
            lines.append(fields_txt.rstrip())

    layouts_txt = _format_group("LAYOUTS", d["layouts"])
    if layouts_txt:
        lines.append(layouts_txt.rstrip())

    perms_txt = _format_group("PERMISSIONS", d["permissions"])
    if perms_txt:
        lines.append(perms_txt.rstrip())

    body = "\n".join(l for l in lines if l)
    return body if body else "No semantic differences found."


def main(argv):
    if len(argv) != 3:
        print(__doc__)
        return 1
    path_a, path_b = argv[1], argv[2]
    try:
        d = diff(path_a, path_b)
    except ParseError as e:
        print(f"Could not parse one of the files: {e}")
        return 1
    print(f"--- {path_a}")
    print(f"+++ {path_b}")
    print()
    print(format_diff(d))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
