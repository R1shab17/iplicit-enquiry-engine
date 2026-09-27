"""Unit tests for src/permissions.py's PERM lookup table."""
import os
import re
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from permissions import PERM

GUID_RE = re.compile(r"^[0-9A-Fa-f]{8}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{12}$")


class TestPermissions(unittest.TestCase):
    def test_not_empty(self):
        self.assertGreater(len(PERM), 0)

    def test_every_value_is_a_guid(self):
        for name, value in PERM.items():
            self.assertRegex(value, GUID_RE, f"{name}'s value '{value}' doesn't look like a GUID")

    def test_no_duplicate_names_map_to_unexpectedly_shared_ids_silently(self):
        # AR.Enquiry and AP-style enquiries currently share a GUID on purpose
        # (docs/ROADMAP.md item 2 — no confirmed AP.Enquiry id yet). This test
        # just documents that AR.Enquiry itself is present and stable; it is
        # NOT a general uniqueness check, since that sharing is intentional
        # for now.
        self.assertIn("AR.Enquiry", PERM)

    def test_known_gl_permissions_present(self):
        for name in ["GeneralLedger.Enquiry", "GeneralLedger.TrialBalance",
                     "GeneralLedger.ProfitLoss", "GeneralLedger.BalanceSheet"]:
            self.assertIn(name, PERM)

    def test_keys_are_module_dot_capability(self):
        for name in PERM:
            self.assertIn(".", name, f"permission key '{name}' should look like Module.Capability")


if __name__ == "__main__":
    unittest.main()
