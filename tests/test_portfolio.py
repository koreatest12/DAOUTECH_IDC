from __future__ import annotations

import json
import tempfile
import unittest
from datetime import date
from pathlib import Path

import alert_correlator
import backup_verify
import capacity_planner
import cert_expiry
import disk_forecast
import healthcheck
import incident_report
import log_analyzer
import sla_calculator
import svc_watchdog


class ExistingToolTests(unittest.TestCase):
    def test_log_normalization_collapses_variable_fields(self):
        a = log_analyzer.normalize("2026-09-04T03:14:15 ERROR app[123] failed from 10.0.0.1 /var/tmp/a 99")
        b = log_analyzer.normalize("2026-09-04T03:14:16 ERROR app[456] failed from 10.0.0.2 /var/tmp/b 100")
        self.assertEqual(a, b)

    def test_log_hour_bucket(self):
        self.assertEqual(log_analyzer.hour_min("2026-09-04T03:47:01 ERROR sample"), "03:40")

    def test_disk_forecast_slope(self):
        entries = [
            {"d": "2026-09-01", "p": 70.0},
            {"d": "2026-09-02", "p": 71.5},
            {"d": "2026-09-03", "p": 73.0},
        ]
        self.assertAlmostEqual(disk_forecast.slope_per_day(entries), 1.5, places=3)
        self.assertAlmostEqual(disk_forecast.days_to(73.0, 1.5, 90.0), 17.0 / 1.5, places=3)

    def test_watchdog_recent_window(self):
        import time
        now = time.time()
        kept = svc_watchdog.recent([now - 10, now - 1000], 60)
        self.assertEqual(len(kept), 1)

    def test_backup_sha256(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "a.bin"
            path.write_bytes(b"abc")
            self.assertEqual(backup_verify.sha256(path), "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad")

    def test_cert_target_parser(self):
        self.assertEqual(cert_expiry.parse_target("example.com"), ("example.com", 443))
        self.assertEqual(cert_expiry.parse_target("https://example.com:8443/path"), ("example.com", 8443))

    def test_health_config_merge(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "cfg.json"
            path.write_text(json.dumps({"cpu_warn": 77}), encoding="utf-8")
            cfg = healthcheck.load_config(str(path))
            self.assertEqual(cfg["cpu_warn"], 77)
            self.assertIn("mem_warn", cfg)


class NewToolTests(unittest.TestCase):
    def test_incident_duration(self):
        self.assertEqual(incident_report.duration_minutes("2026-09-04T02:13:00", "2026-09-04T02:41:00"), 28)

    def test_incident_report_contains_handover(self):
        text = incident_report.build_report(incident_report.sample())
        self.assertIn("교대 인수인계", text)
        self.assertIn("배치 지연 연쇄", text)

    def test_alert_correlation_reduces_noise(self):
        data = alert_correlator.sample()
        incidents = alert_correlator.correlate(data, 10)
        self.assertLess(len(incidents), len(data))
        self.assertTrue(any(x["alert_count"] >= 2 for x in incidents))

    def test_capacity_slope_and_eta(self):
        rows = capacity_planner.sample()
        slope = capacity_planner.slope_per_day(rows, "disk")
        self.assertIsNotNone(slope)
        result = capacity_planner.analyze(rows)
        disk = next(x for x in result if x["metric"] == "disk")
        self.assertGreater(disk["days_to_threshold"], 0)

    def test_capacity_threshold_already_exceeded(self):
        self.assertEqual(capacity_planner.days_to_threshold(91.0, 1.0, 90.0), 0.0)

    def test_sla_allowed_downtime(self):
        period = 30 * 24 * 60
        self.assertAlmostEqual(sla_calculator.allowed_downtime_minutes(99.9, period), 43.2, places=1)

    def test_sla_evaluation(self):
        period = sla_calculator.period_to_minutes(30)
        self.assertTrue(sla_calculator.evaluate(99.95, period, 20).passed)
        self.assertFalse(sla_calculator.evaluate(99.99, period, 20).passed)

    def test_availability_bounds(self):
        self.assertEqual(sla_calculator.availability_percent(100, 0), 100.0)
        self.assertEqual(sla_calculator.availability_percent(100, 200), 0.0)


if __name__ == "__main__":
    unittest.main()
