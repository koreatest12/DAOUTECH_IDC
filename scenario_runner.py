#!/usr/bin/env python3
"""IDC 운영 시나리오를 결정적으로 분석하고 기대 결과를 검증합니다."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any

SEVERITY = {"INFO": 0, "WARN": 1, "CRIT": 2, "SEV3": 3, "SEV2": 4, "SEV1": 5}


def configure_console() -> None:
    """Windows 기본 cp1252 콘솔에서도 한국어 결과를 안전하게 출력합니다."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            try:
                reconfigure(encoding="utf-8", errors="replace")
            except (OSError, ValueError):
                pass


@dataclass
class ScenarioResult:
    scenario_id: str
    title: str
    status: str
    root_cause: str
    severity: str
    affected_count: int
    elapsed_minutes: float
    sla_minutes: float
    sla_risk: str
    blocked_services: list[str]
    validation_errors: list[str]


def load(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError("scenario root must be an object")
    return data


def event_map(data: dict[str, Any]) -> dict[str, dict[str, Any]]:
    events = data.get("events", [])
    if not isinstance(events, list) or not events:
        raise ValueError("events must be a non-empty list")
    result: dict[str, dict[str, Any]] = {}
    for event in events:
        if not isinstance(event, dict) or not event.get("id"):
            raise ValueError("every event requires id")
        key = str(event["id"])
        if key in result:
            raise ValueError(f"duplicate event id: {key}")
        result[key] = event
    return result


def validate_dependencies(events: dict[str, dict[str, Any]]) -> list[str]:
    errors: list[str] = []
    for eid, event in events.items():
        parent = event.get("depends_on")
        if parent and parent not in events:
            errors.append(f"{eid}: unknown dependency {parent}")
    return errors


def descendants(events: dict[str, dict[str, Any]], root: str) -> set[str]:
    found: set[str] = set()
    changed = True
    while changed:
        changed = False
        for eid, event in events.items():
            parent = event.get("depends_on")
            if eid in found:
                continue
            if parent == root or parent in found:
                found.add(eid)
                changed = True
    return found


def root_candidates(events: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    roots = [e for e in events.values() if not e.get("depends_on")]
    return sorted(
        roots,
        key=lambda e: (
            SEVERITY.get(str(e.get("severity", "INFO")).upper(), 0),
            len(descendants(events, str(e["id"]))),
            -float(e.get("minute", 0)),
        ),
        reverse=True,
    )


def sla_risk(elapsed: float, sla: float) -> str:
    if sla <= 0:
        return "N/A"
    ratio = elapsed / sla
    if ratio >= 1:
        return "BREACHED"
    if ratio >= 0.8:
        return "HIGH"
    if ratio >= 0.5:
        return "MEDIUM"
    return "LOW"


def analyze(data: dict[str, Any]) -> ScenarioResult:
    events = event_map(data)
    errors = validate_dependencies(events)
    roots = root_candidates(events)
    if not roots:
        raise ValueError("at least one root event is required")

    root = roots[0]
    root_id = str(root["id"])
    affected = descendants(events, root_id)
    affected.add(root_id)
    severity = str(root.get("severity", "INFO")).upper()
    elapsed = float(data.get("elapsed_minutes", 0))
    sla = float(data.get("sla_minutes", 0))

    blocked = sorted({
        str(event.get("component", eid))
        for eid, event in events.items()
        if eid in affected and str(event.get("state", "")).upper() in {"FAILED", "BLOCKED", "DEGRADED"}
    })

    expected = data.get("expected", {}) if isinstance(data.get("expected", {}), dict) else {}
    if expected.get("root_cause") and str(expected["root_cause"]) != root_id:
        errors.append(f"root cause expected={expected['root_cause']} actual={root_id}")
    if expected.get("severity") and str(expected["severity"]).upper() != severity:
        errors.append(f"severity expected={expected['severity']} actual={severity}")
    if expected.get("sla_risk") and str(expected["sla_risk"]).upper() != sla_risk(elapsed, sla):
        errors.append(f"sla_risk expected={expected['sla_risk']} actual={sla_risk(elapsed, sla)}")
    min_affected = expected.get("min_affected")
    if min_affected is not None and len(affected) < int(min_affected):
        errors.append(f"affected expected>={min_affected} actual={len(affected)}")

    return ScenarioResult(
        scenario_id=str(data.get("id", "unknown")),
        title=str(data.get("title", "Untitled scenario")),
        status="PASS" if not errors else "FAIL",
        root_cause=root_id,
        severity=severity,
        affected_count=len(affected),
        elapsed_minutes=elapsed,
        sla_minutes=sla,
        sla_risk=sla_risk(elapsed, sla),
        blocked_services=blocked,
        validation_errors=errors,
    )


def scenario_files(path: Path) -> list[Path]:
    if path.is_file():
        return [path]
    if path.is_dir():
        return sorted(p for p in path.glob("*.json") if p.is_file())
    raise FileNotFoundError(path)


def render(results: list[ScenarioResult]) -> str:
    failed = sum(r.status == "FAIL" for r in results)
    lines = [
        "# IDC 운영 시나리오 검증",
        "",
        f"- 시나리오: **{len(results)}개**",
        f"- 실패: **{failed}개**",
        f"- 최종 상태: **{'PASS' if not failed else 'FAIL'}**",
        "",
        "| 상태 | 시나리오 | Root Cause | 심각도 | 영향 | SLA 위험 |",
        "|---|---|---|---|---:|---|",
    ]
    for r in results:
        lines.append(
            f"| {r.status} | {r.scenario_id} · {r.title} | `{r.root_cause}` | {r.severity} | {r.affected_count} | {r.sla_risk} |"
        )
        if r.validation_errors:
            for err in r.validation_errors:
                lines.append(f"\n> `{r.scenario_id}` 검증 오류: {err}")
    lines += [
        "",
        "## 판정 원칙",
        "",
        "- 의존성이 없는 이벤트를 Root Cause 후보로 보고 심각도·후행 영향 범위·발생 시점을 함께 비교합니다.",
        "- Root Cause의 후행 이벤트를 재귀적으로 추적해 영향 범위를 계산합니다.",
        "- 경과시간/SLA 비율로 LOW·MEDIUM·HIGH·BREACHED를 판정합니다.",
        "- 각 JSON의 `expected`와 실제 계산 결과를 대조하므로 시나리오 변경 시 회귀 오류를 탐지합니다.",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    configure_console()
    ap = argparse.ArgumentParser(description="IDC 운영 시나리오 결정적 실행·검증")
    ap.add_argument("path", nargs="?", default="scenarios", help="시나리오 JSON 또는 디렉터리")
    ap.add_argument("--report", default="scenario-report.md")
    ap.add_argument("--json-report", default="scenario-report.json")
    args = ap.parse_args()

    try:
        files = scenario_files(Path(args.path))
        if not files:
            raise ValueError("scenario file not found")
        results = [analyze(load(path)) for path in files]
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"시나리오 실행 실패: {exc}", file=sys.stderr)
        return 2

    Path(args.report).write_text(render(results), encoding="utf-8")
    payload = {
        "status": "PASS" if all(r.status == "PASS" for r in results) else "FAIL",
        "count": len(results),
        "results": [asdict(r) for r in results],
    }
    Path(args.json_report).write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"시나리오 검증 완료: {len(results)}개 / 실패 {sum(r.status == 'FAIL' for r in results)}개")
    print(f"결과: {payload['status']}")
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
