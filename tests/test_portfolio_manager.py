import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("portfolio_manager", ROOT / "tools" / "portfolio_manager.py")
MOD = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MOD)


class PortfolioManagerTests(unittest.TestCase):
    def setUp(self):
        self.catalog = {
            "domains": [
                {"id": "docs", "name": "Docs", "categories": ["documentation"], "interview_focus": "explain docs"},
                {"id": "ops", "name": "Ops", "categories": ["python-cli"], "interview_focus": "explain ops"},
            ],
            "readiness_requirements": {
                "documentation": ["README.md"],
                "automation": ["tool.py"],
                "release": ["release.yml"],
            },
            "upgrade_backlog": [
                {"id": "B", "priority": "P1", "objective": "later", "exit_criteria": "done", "target": "ops"},
                {"id": "A", "priority": "P0", "objective": "first", "exit_criteria": "done", "target": "docs"},
            ],
            "interview_question_bank": ["question"],
        }
        self.manifest = {
            "files": [
                {"path": "README.md", "category": "documentation", "purpose": "readme"},
                {"path": "tool.py", "category": "python-cli", "purpose": "tool"},
                {"path": "release.yml", "category": "documentation", "purpose": "release"},
            ]
        }

    def test_ready_when_all_tracked_and_classified(self):
        result = MOD.evaluate(self.manifest, self.catalog, {"README.md", "tool.py", "release.yml"})
        self.assertEqual(result["status"], "READY")
        self.assertEqual(result["score"], 100)
        self.assertEqual(result["unregistered"], [])
        self.assertEqual(result["unknown_categories"], [])

    def test_unregistered_file_blocks(self):
        result = MOD.evaluate(self.manifest, self.catalog, {"README.md", "tool.py", "release.yml", "new.py"})
        self.assertEqual(result["status"], "BLOCKED")
        self.assertIn("new.py", result["unregistered"])

    def test_unknown_category_blocks(self):
        manifest = json.loads(json.dumps(self.manifest))
        manifest["files"][1]["category"] = "mystery"
        result = MOD.evaluate(manifest, self.catalog, {"README.md", "tool.py", "release.yml"})
        self.assertEqual(result["status"], "BLOCKED")
        self.assertIn("mystery", result["unknown_categories"])

    def test_backlog_is_priority_sorted(self):
        result = MOD.evaluate(self.manifest, self.catalog, {"README.md", "tool.py", "release.yml"})
        self.assertEqual([x["id"] for x in result["backlog"]], ["A", "B"])

    def test_render_reports_contain_key_sections(self):
        result = MOD.evaluate(self.manifest, self.catalog, {"README.md", "tool.py", "release.yml"})
        self.assertIn("면접 대비", MOD.render_readiness(result))
        self.assertIn("전체 기능 인벤토리", MOD.render_inventory(result))
        self.assertIn("업그레이드", MOD.render_upgrade_plan(result))


if __name__ == "__main__":
    unittest.main()
