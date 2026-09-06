from __future__ import annotations

import sys
import unittest

import python_server_upgrade as upgrade


class PythonServerUpgradeTests(unittest.TestCase):
    def test_parse_version_accepts_series_and_patch(self) -> None:
        self.assertEqual(upgrade.parse_version("3.14"), (3, 14))
        self.assertEqual(upgrade.parse_version("v3.14.7"), (3, 14, 7))

    def test_parse_version_rejects_invalid_value(self) -> None:
        with self.assertRaises(ValueError):
            upgrade.parse_version("3")

    def test_compare_series_detects_forward_upgrade(self) -> None:
        self.assertEqual(upgrade.compare_series((3, 12, 14), (3, 14)), "UPGRADE")

    def test_target_matches_series(self) -> None:
        current = (sys.version_info.major, sys.version_info.minor, sys.version_info.micro)
        self.assertTrue(upgrade.target_matches(current, current[:2]))

    def test_upgrade_and_rollback_plans_are_present(self) -> None:
        upgrade_steps, rollback_steps = upgrade.build_steps("3.14", "python3.14", "portfolio-api")
        self.assertGreaterEqual(len(upgrade_steps), 8)
        self.assertGreaterEqual(len(rollback_steps), 4)
        self.assertTrue(any("side-by-side" in step for step in upgrade_steps))


if __name__ == "__main__":
    unittest.main()
