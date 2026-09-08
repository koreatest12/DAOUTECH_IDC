from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

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

    def test_runtime_root_rejects_repository_root(self) -> None:
        with self.assertRaises(ValueError):
            upgrade.safe_runtime_root(".")

    def test_requirements_parser_ignores_comments(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "requirements.txt"
            path.write_text("# comment\n\n", encoding="utf-8")
            self.assertFalse(upgrade.requirements_have_packages(path))
            path.write_text("# comment\nrequests==2.32.0\n", encoding="utf-8")
            self.assertTrue(upgrade.requirements_have_packages(path))

    def test_runtime_pointer_switch_and_rollback(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "runtime"
            old = upgrade.pointer_payload(
                "3.12.14",
                sys.executable,
                managed=False,
                release_dir=None,
            )
            new = upgrade.pointer_payload(
                "3.14.7",
                sys.executable,
                managed=True,
                release_dir=str(root / "release"),
            )
            upgrade.write_json_atomic(root / "current.json", old)
            upgrade.switch_pointer(root, new)

            current = json.loads((root / "current.json").read_text(encoding="utf-8"))
            previous = json.loads((root / "previous.json").read_text(encoding="utf-8"))
            self.assertEqual(current["version"], "3.14.7")
            self.assertEqual(previous["version"], "3.12.14")

            result = upgrade.rollback_runtime(root)
            self.assertEqual(result["status"], "ROLLED_BACK")
            restored = json.loads((root / "current.json").read_text(encoding="utf-8"))
            self.assertEqual(restored["version"], "3.12.14")

    def test_probe_current_python(self) -> None:
        probe = upgrade.executable_probe(sys.executable)
        self.assertEqual(probe["status"], "AVAILABLE")
        self.assertIsNotNone(probe["version_tuple"])

    def test_command_result_decodes_utf8_output(self) -> None:
        result = upgrade.command_result(
            [
                sys.executable,
                "-c",
                "import sys; sys.stdout.buffer.write('한글 UTF-8 출력\\n'.encode('utf-8'))",
            ]
        )
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["stdout"], "한글 UTF-8 출력")
        self.assertEqual(result["stderr"], "")


if __name__ == "__main__":
    unittest.main()
