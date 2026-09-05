from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import scenario_runner
from tools import portfolio_report


class ScenarioRunnerTests(unittest.TestCase):
    def test_all_repository_scenarios_pass(self):
        files = scenario_runner.scenario_files(Path("scenarios"))
        self.assertGreaterEqual(len(files), 5)
        results = [scenario_runner.analyze(scenario_runner.load(path)) for path in files]
        self.assertTrue(all(result.status == "PASS" for result in results))

    def test_dependency_validation_detects_unknown_parent(self):
        events = {
            "a": {"id": "a", "depends_on": "missing"},
        }
        errors = scenario_runner.validate_dependencies(events)
        self.assertEqual(len(errors), 1)
        self.assertIn("unknown dependency", errors[0])

    def test_descendants_are_recursive(self):
        events = {
            "a": {"id": "a"},
            "b": {"id": "b", "depends_on": "a"},
            "c": {"id": "c", "depends_on": "b"},
        }
        self.assertEqual(scenario_runner.descendants(events, "a"), {"b", "c"})

    def test_sla_risk_boundaries(self):
        self.assertEqual(scenario_runner.sla_risk(10, 60), "LOW")
        self.assertEqual(scenario_runner.sla_risk(30, 60), "MEDIUM")
        self.assertEqual(scenario_runner.sla_risk(50, 60), "HIGH")
        self.assertEqual(scenario_runner.sla_risk(60, 60), "BREACHED")


class PortfolioReportTests(unittest.TestCase):
    def test_render_contains_key_sections(self):
        review = {"files": [{"path": "a"}], "issues": []}
        execution = {"files": [{"status": "OK"}], "submission_checks": []}
        functional = {"status": "PASS", "records": [{"status": "OK"}]}
        summary = {"status": "READY"}
        scenarios = {
            "status": "PASS",
            "results": [{
                "status": "PASS", "scenario_id": "SCN-X", "title": "test",
                "root_cause": "root", "severity": "SEV2", "sla_risk": "LOW"
            }],
        }
        page = portfolio_report.render(review, execution, functional, summary, scenarios)
        self.assertIn("Quality Report", page)
        self.assertIn("Scenario Validation", page)
        self.assertIn("SCN-X", page)
        self.assertIn("READY", page)

    def test_report_load_tolerates_missing_file(self):
        with tempfile.TemporaryDirectory() as td:
            missing = Path(td) / "missing.json"
            self.assertEqual(portfolio_report.load(str(missing)), {})

    def test_report_load_reads_json(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "a.json"
            path.write_text(json.dumps({"status": "PASS"}), encoding="utf-8")
            self.assertEqual(portfolio_report.load(str(path))["status"], "PASS")


if __name__ == "__main__":
    unittest.main()
