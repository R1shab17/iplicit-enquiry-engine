"""
Mutation testing harness: take every REAL enquiry in generated/*/*.json,
apply one small, meaning-changing edit at a time (mirroring a known or
discovered failure mode), and confirm enquiry_validator.py still catches
it. This is deliberately built on real, already-valid enquiries rather
than randomly generated nonsense (docs/PROJECT_AUDIT.md #9 / the
brief's "generate mutations based on real valid enquiries, not random
noise") — the goal is finding validator blind spots, not fuzzing crashes.

Each mutation function takes a decoded model dict, mutates it in place,
and returns True if it found something to mutate (False lets the harness
skip files where the mutation doesn't apply — e.g. you can't strip a
union's field-name parity from an enquiry with no union).
"""
import base64
import glob
import json
import os
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from enquiry_validator import validate_file

REPO_ROOT = os.path.join(os.path.dirname(__file__), "..")
GENERATED_FILES = sorted(glob.glob(os.path.join(REPO_ROOT, "generated", "*", "*.json")))


def load_model(path):
    with open(path, encoding="utf-8") as f:
        env = json.load(f)
    return json.loads(base64.b64decode(env["data"]).decode("utf-8"))


def write_mutant(model):
    data = base64.b64encode(json.dumps(model, ensure_ascii=False).encode("utf-8")).decode()
    env = {"type": "DbEnquiry", "description": model.get("Description", "mutant"),
           "exportDate": "01/01/2026 00:00", "data": data}
    fd, path = tempfile.mkstemp(suffix=".json")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(env, f)
    return path


# ---------------------------------------------------------------- mutations

def strip_permissions(model):
    if not model.get("RequiredPermissions"):
        return False
    model["RequiredPermissions"] = []
    return True


def break_first_in_filter_null_safety(model):
    root = ET.fromstring(model["QueryXml"])
    for f in root.iter("Field"):
        if f.get("FilterOperator") == "In" and f.get("FilterOr"):
            del f.attrib["FilterOr"]
            model["QueryXml"] = ET.tostring(root, encoding="unicode")
            return True
    return False


def break_first_between_filter_null_safety(model):
    root = ET.fromstring(model["QueryXml"])
    for f in root.iter("Field"):
        if f.get("FilterOperator") == "Between" and "isnull(" in (f.get("FilterArgument") or "").lower():
            f.set("FilterArgument", "@DateFrom AND @DateTo")
            model["QueryXml"] = ET.tostring(root, encoding="unicode")
            return True
    return False


def dangle_a_source_reference(model):
    root = ET.fromstring(model["QueryXml"])
    for f in root.iter("Field"):
        if f.get("Source"):
            f.set("Source", f.get("Source") + "_ghost")
            model["QueryXml"] = ET.tostring(root, encoding="unicode")
            return True
    return False


def remove_a_declared_param(model):
    """Every param left in this library after the engine-hardening fixes is
    actually referenced somewhere, so removing any one of them should trip
    the undeclared-reference check — this mutation doubles as a check that
    those fixes stuck."""
    root = ET.fromstring(model["QueryXml"])
    params = root.findall("Param")
    if not params:
        return False
    root.remove(params[0])
    model["QueryXml"] = ET.tostring(root, encoding="unicode")
    return True


def add_an_unused_param(model):
    root = ET.fromstring(model["QueryXml"])
    ghost = ET.SubElement(root, "Param")
    ghost.set("Name", "GhostParam")
    ghost.set("ValueType", "Text")
    ghost.set("Caption", "Ghost")
    ghost.set("Presenter", "Text")
    model["QueryXml"] = ET.tostring(root, encoding="unicode")
    return True


def corrupt_a_union_field_name(model):
    root = ET.fromstring(model["QueryXml"])
    unioned = [s for s in root.findall("Select") if s.get("Union")]
    if not unioned:
        return False
    fields = unioned[0].findall("Field")
    if not fields:
        return False
    fields[0].set("Name", fields[0].get("Name") + "Ghost")
    model["QueryXml"] = ET.tostring(root, encoding="unicode")
    return True


def orphan_a_propmeta_entry(model):
    try:
        meta = json.loads(model["PropMetaJson"])
    except Exception:
        return False
    meta["GhostField"] = {"label": "Ghost", "defaultWidth": 100, "visible": True,
                           "dataType": "text", "viewType": "text", "name": "GhostField"}
    model["PropMetaJson"] = json.dumps(meta)
    return True


def reintroduce_hierarchy_grouprows_conflict(model):
    for entry in model.get("EnquiryLayouts", []):
        try:
            cd = json.loads(entry["ContainerDefinition"])
        except Exception:
            continue
        grid = cd.get("layout", {}).get("grid", {})
        group_rows = grid.get("groupRows") or []
        if len(group_rows) >= 1 and not grid.get("hierarchy"):
            grid["groupRows"] = list(group_rows) + [{"field": "GhostDimension", "sticky": True}]
            grid["hierarchy"] = {"treeId": "00000000-0000-0000-0000-000000000000",
                                  "name": "Standard Balance Sheet tree", "other": "Other"}
            entry["ContainerDefinition"] = json.dumps({"layout": {"grid": grid}})
            return True
    return False


def strip_currency_member_from_includes(model):
    try:
        meta = json.loads(model["PropMetaJson"])
    except Exception:
        return False
    amount_cols = [k for k, v in meta.items() if v.get("viewType") == "amount"]
    if not amount_cols:
        return False
    for entry in model.get("EnquiryLayouts", []):
        try:
            cd = json.loads(entry["ContainerDefinition"])
        except Exception:
            continue
        grid = cd.get("layout", {}).get("grid", {})
        includes = grid.get("includes") or []
        removed = False
        for col in amount_cols:
            cm = (meta[col].get("settings") or {}).get("currencyMember")
            if cm and cm in includes:
                includes.remove(cm)
                removed = True
        if removed:
            grid["includes"] = includes
            entry["ContainerDefinition"] = json.dumps({"layout": {"grid": grid}})
            return True
    return False


# ---------------------------------------------------------------- harness

class MutationTestCase(unittest.TestCase):
    def run_mutation(self, mutate_fn, expect_substring):
        tested = 0
        for path in GENERATED_FILES:
            model = load_model(path)
            if not mutate_fn(model):
                continue
            tested += 1
            mutant_path = write_mutant(model)
            try:
                issues = validate_file(mutant_path)
                self.assertTrue(
                    any(expect_substring in m for m in issues),
                    f"mutating {os.path.basename(path)} with {mutate_fn.__name__} "
                    f"did not trip a message containing {expect_substring!r}; got: {issues}",
                )
            finally:
                os.unlink(mutant_path)
        self.assertGreater(
            tested, 0,
            f"{mutate_fn.__name__} never found anything to mutate across "
            f"{len(GENERATED_FILES)} generated/*/*.json files — is the mutation still applicable?",
        )
        return tested


class TestMutations(MutationTestCase):
    def test_stripping_permissions_is_always_caught(self):
        n = self.run_mutation(strip_permissions, "RequiredPermissions is empty")
        self.assertEqual(n, len(GENERATED_FILES), "every real enquiry declares at least one permission")

    def test_breaking_in_filter_null_safety_is_caught(self):
        self.run_mutation(break_first_in_filter_null_safety, "FilterOperator=In without")

    def test_breaking_between_filter_null_safety_is_caught(self):
        self.run_mutation(break_first_between_filter_null_safety, "FilterOperator=Between without ISNULL")

    def test_dangling_source_reference_is_caught(self):
        self.run_mutation(dangle_a_source_reference, "isn't declared as a <Source>")

    def test_removing_a_declared_param_is_caught(self):
        self.run_mutation(remove_a_declared_param, "is declared")  # matches the undeclared-reference message

    def test_adding_an_unused_param_is_caught(self):
        n = self.run_mutation(add_an_unused_param, "is declared but never used")
        self.assertEqual(n, len(GENERATED_FILES), "this mutation applies unconditionally to every file")

    def test_corrupting_a_union_field_name_is_caught(self):
        self.run_mutation(corrupt_a_union_field_name, "does not match first Select's field list")

    def test_orphaning_a_propmeta_entry_is_caught(self):
        n = self.run_mutation(orphan_a_propmeta_entry, "dead metadata")
        self.assertEqual(n, len(GENERATED_FILES), "this mutation applies unconditionally to every file")

    def test_reintroducing_hierarchy_grouprows_conflict_is_caught(self):
        self.run_mutation(reintroduce_hierarchy_grouprows_conflict, "combines a saved hierarchy")

    def test_stripping_currency_member_from_includes_is_caught(self):
        self.run_mutation(strip_currency_member_from_includes, "needing currencyMember")


if __name__ == "__main__":
    unittest.main()
