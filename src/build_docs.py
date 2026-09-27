#!/usr/bin/env python3
"""
Regenerate the pattern catalogue's outputs from generated/: docs/PATTERNS.md
(human-readable) and patterns/*.json (machine-readable, one file per
pattern kind, for anything that wants to query the catalogue directly
rather than re-deriving it — e.g. tests/test_patterns.py).

Run this after adding or changing anything in generated/:

    python3 src/build_docs.py

Everything it writes is derived from src/patterns.py's build_catalogue(),
which parses the real generated/*.json files — never hand-maintained, so
these outputs can't silently drift from what's actually confirmed.
"""
import json
import os

import patterns

DOCS_DIR = os.path.join(os.path.dirname(__file__), "..", "docs")
PATTERNS_DIR = os.path.join(os.path.dirname(__file__), "..", "patterns")


def _entries(store):
    """store: {key: (pattern, modules_set)} -> a JSON-serializable list,
    each entry the pattern's own fields plus a sorted `modules` list."""
    out = []
    for pattern, modules in store.values():
        entry = dict(pattern.__dict__)
        entry["confirmed_via"] = list(pattern.confirmed_via)
        entry["modules"] = sorted(modules)
        out.append(entry)
    out.sort(key=lambda e: -len(e["confirmed_via"]))
    return out


def write_json_catalogue(cat: patterns.Catalogue, out_dir: str = PATTERNS_DIR):
    os.makedirs(out_dir, exist_ok=True)
    files = {
        "joins.json": _entries(cat.joins),
        "fields.json": _entries(cat.fields),
        "filter_idioms.json": _entries(cat.filter_idioms),
        "params.json": _entries(cat.params),
        "layouts.json": _entries(cat.layouts),
        "permissions.json": _entries(cat.permissions),
    }
    written = []
    for name, data in files.items():
        path = os.path.join(out_dir, name)
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"files_scanned": list(cat.files_scanned), "entries": data}, f, indent=2)
            f.write("\n")
        written.append(path)
    return written


def write_markdown(cat: patterns.Catalogue, out_path: str = None):
    out_path = out_path or os.path.join(DOCS_DIR, "PATTERNS.md")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(patterns.render_markdown(cat))
        f.write("\n")
    return out_path


def main():
    cat = patterns.build_catalogue()
    md_path = write_markdown(cat)
    json_paths = write_json_catalogue(cat)
    print(f"Scanned {len(cat.files_scanned)} enquiries.")
    print(f"Wrote {md_path}")
    for p in json_paths:
        print(f"Wrote {p}")


if __name__ == "__main__":
    main()
