#!/usr/bin/env python3
"""Correlate noisy infrastructure alerts into likely incidents using deterministic rules."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

SEVERITY = {"INFO": 0, "WARN": 1, "CRIT": 2, "CRITICAL": 2}
ROOT_METRICS = {"disk", "filesystem", "network", "service", "cpu", "memory"}


def parse_time(value: str) -> datetime:
    return datetime.fromisoformat(value)


def normalize_alert(item: dict) -> dict:
    return {
        "time": str(item.get("time", "1970-01-01T00:00:00")),
        "host": str(item.get("host", "unknown")),
        "metric": str(item.get("metric", "unknown")).lower(),
        "severity": str(item.get("severity", "WARN")).upper(),
        "message": str(item.get("message", "")),
        "service": str(item.get("service", "")),
        "upstream": str(item.get("upstream", "")),
    }


def root_key(alert: dict) -> str:
    if alert["upstream"]:
        return f"{alert['upstream']}::dependency"
    metric = alert["metric"] if alert["metric"] in ROOT_METRICS else "service"
    return f"{alert['host']}::{metric}"


def correlate(alerts: list[dict], window_minutes: int = 10) -> list[dict]:
    normalized = sorted((normalize_alert(x) for x in alerts), key=lambda x: parse_time(x["time"]))
    incidents: list[dict] = []
    window = timedelta(minutes=window_minutes)
    for alert in normalized:
        ts = parse_time(alert["time"])
        key = root_key(alert)
        target = None
        for incident in reversed(incidents):
            if incident["root_key"] == key and ts - parse_time(incident["last_time"]) <= window:
                target = incident
                break
        if target is None:
            target = {
                "root_key": key,
                "first_time": alert["time"],
                "last_time": alert["time"],
                "severity": alert["severity"],
                "alerts": [],
                "hosts": [],
            }
            incidents.append(target)
        target["alerts"].append(alert)
        target["last_time"] = alert["time"]
        target["hosts"] = sorted(set(target["hosts"] + [alert["host"]]))
        if SEVERITY.get(alert["severity"], 1) > SEVERITY.get(target["severity"], 1):
            target["severity"] = alert["severity"]

    for incident in incidents:
        host, metric = incident["root_key"].split("::", 1)
        incident["root_cause_candidate"] = (
            f"{host} 상위 의존성 장애" if metric == "dependency" else f"{host} {metric} 이상"
        )
        incident["alert_count"] = len(incident["alerts"])
    return incidents


def render(incidents: list[dict], total: int) -> str:
    lines = [
        "# 알람 상관분석 결과", "",
        f"- 원본 알람: **{total}건**",
        f"- 상관분석 후 Incident: **{len(incidents)}건**",
        f"- 중복/연관 알람 감소: **{max(total-len(incidents), 0)}건**", "",
        "| 심각도 | Incident 후보 | 알람 | 영향 Host | 시간 범위 |",
        "|---|---|---:|---|---|",
    ]
    for inc in incidents:
        lines.append(
            f"| {inc['severity']} | {inc['root_cause_candidate']} | {inc['alert_count']} | "
            f"{', '.join(inc['hosts'])} | {inc['first_time']} ~ {inc['last_time']} |"
        )
    return "\n".join(lines) + "\n"


def sample() -> list[dict]:
    return [
        {"time":"2026-09-04T02:13:00","host":"DB01","metric":"disk","severity":"CRIT","message":"/u01 97%"},
        {"time":"2026-09-04T02:14:00","host":"APP01","metric":"service","severity":"WARN","message":"response slow","upstream":"DB01"},
        {"time":"2026-09-04T02:15:00","host":"BATCH01","metric":"service","severity":"WARN","message":"job delay","upstream":"DB01"},
        {"time":"2026-09-04T02:16:00","host":"WEB01","metric":"service","severity":"WARN","message":"latency","upstream":"DB01"},
        {"time":"2026-09-04T03:02:00","host":"FW01","metric":"network","severity":"CRIT","message":"packet drop"}
    ]


def main() -> int:
    ap = argparse.ArgumentParser(description="IDC/NOC 알람 중복 제거 및 Incident 상관분석")
    ap.add_argument("input", nargs="?", help="알람 JSON 배열 파일")
    ap.add_argument("--window", type=int, default=10, help="같은 Incident로 묶을 시간 창(분)")
    ap.add_argument("--output", default="alert-correlation.md")
    ap.add_argument("--json-output", default="alert-correlation.json")
    ap.add_argument("--init", action="store_true", help="예시 입력 JSON 생성")
    args = ap.parse_args()
    if args.init:
        path = Path(args.input or "alerts-sample.json")
        path.write_text(json.dumps(sample(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"예시 입력 생성: {path}")
        return 0
    if not args.input:
        ap.error("input JSON 파일이 필요합니다.")
    try:
        data = json.loads(Path(args.input).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"입력 오류: {exc}", file=sys.stderr)
        return 2
    if not isinstance(data, list):
        print("입력 JSON은 배열이어야 합니다.", file=sys.stderr)
        return 2
    try:
        incidents = correlate(data, args.window)
    except (ValueError, TypeError) as exc:
        print(f"알람 시간/필드 오류: {exc}", file=sys.stderr)
        return 2
    Path(args.output).write_text(render(incidents, len(data)), encoding="utf-8")
    Path(args.json_output).write_text(json.dumps(incidents, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(render(incidents, len(data)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
