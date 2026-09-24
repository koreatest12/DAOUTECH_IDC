from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

import execute_repo


def rec(target: str, status: str = "OK") -> dict:
    return {"target": target, "status": status}


class CoverageGateTests(unittest.TestCase):
    def test_all_tracked_files_covered(self):
        tracked = ["a.py", "b.html", "c.json", "README.md", "tests/test_x.py", "image.png"]
        records = [rec("a.py#init"), rec("b.html#browser"), rec("c.json"), rec("README.md"), rec("tests#unittest")]
        gate = execute_repo.coverage_gate(records, tracked)
        self.assertEqual(gate["status"], "OK")
        self.assertIn("covered=5/5", gate["evidence"])

    def test_missing_file_blocks_gate(self):
        gate = execute_repo.coverage_gate([rec("a.py")], ["a.py", "new_tool.py"])
        self.assertEqual(gate["status"], "ERROR")
        self.assertIn("new_tool.py", gate["evidence"])

    def test_failed_unittest_does_not_cover_test_files(self):
        gate = execute_repo.coverage_gate([rec("tests#unittest", "ERROR")], ["tests/test_x.py"])
        self.assertEqual(gate["status"], "ERROR")

    def test_every_repository_file_is_classified(self):
        for rel in execute_repo.tracked_files():
            if rel.endswith((".py", ".html")):
                self.assertTrue(execute_repo.is_runnable(rel), rel)
            elif not rel.endswith((".png", ".jpg", ".svg", ".ico")):
                self.assertTrue(execute_repo.is_data(rel), f"unclassified tracked file: {rel}")


class DataValidationTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self._orig = execute_repo.ROOT
        execute_repo.ROOT = self.root

    def tearDown(self):
        execute_repo.ROOT = self._orig
        self._tmp.cleanup()

    def status_of(self, name: str, text: str) -> str:
        (self.root / name).write_text(text, encoding="utf-8")
        return execute_repo.run_data([name])[0]["status"]

    def test_valid_json(self):
        self.assertEqual(self.status_of("ok.json", '{"a": 1}'), "OK")

    def test_invalid_json(self):
        self.assertEqual(self.status_of("bad.json", '{"a": 1,}'), "ERROR")

    def test_yaml_tab_indentation(self):
        self.assertEqual(self.status_of("ok.yml", "a:\n  b: 1\n"), "OK")
        self.assertEqual(self.status_of("bad.yml", "a:\n\tb: 1\n"), "ERROR")

    def test_empty_text(self):
        self.assertEqual(self.status_of("empty.md", "  \n"), "ERROR")


class TargetSelectionTests(unittest.TestCase):
    def test_group_targets_are_listed(self):
        for group in ("scenarios", "pipeline", "tests", "data"):
            self.assertIn(group, execute_repo.TARGETS)
            self.assertEqual(execute_repo.selected(group), [])

    def test_all_includes_every_tool_and_simulator(self):
        self.assertEqual(execute_repo.selected("all"), [*execute_repo.PYTHON_TOOLS, *execute_repo.HTML_FILES])


if __name__ == "__main__":
    unittest.main()
