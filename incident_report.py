#!/usr/bin/env python3
"""Generate an incident report and shift-handover summary from structured input."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

SEVERITY_ORDER = {"INFO": 0, "MINOR": 1, "MAJOR": 2, "CRITICAL": 3}


def normalize_severity(value: str) -> str:
    value = value.strip().upper()
    return value if value in SEVERITY_ORDER else "MAJOR"


def duration_minutes(start: str, end: str) -> int | None:
    try:
        a = datetime.fromisoformat(start)
        b = datetime.fromisoformat(end)
    except ValueError:
        return None
    return max(0, int((b - a).total_seconds() // 60))


def build_report(data: dict) -> str:
    title = data.get("title") or "IDC 운영 장애"
    severity = normalize_severity(str(data.get("severity", "MAJOR")))
    started = str(data.get("started_at", "미입력"))
    ended = str(data.get("ended_at", "미입력"))
    duration = duration_minutes(started, ended) if started != "미입력" and ended != "미입력" else None
    timeline = data.get("timeline") or []
    actions = data.get("actions") or []
    followups = data.get("followups") or []

    lines = [
        f"# 장애 보고서 — {title}", "",
        "## 요약", "",
        f"- 심각도: **{severity}**",
        f"- 발생: **{started}**",
        f"- 종료: **{ended}**",
        f"- 장애 시간: **{duration if duration is not None else '계산 불가'}{'분' if duration is not None else ''}**",
        f"- 영향: {data.get('impact', '미입력')}",
        f"- 원인: {data.get('root_cause', '조사 중')}", "",
        "## 타임라인", "",
    ]
    if timeline:
        for item in timeline:
            lines.append(f"- `{item.get('time', '-')}` {item.get('event', '')}")
    else:
        lines.append("- 타임라인 미입력")
    lines += ["", "## 조치", ""]
    if actions:
        lines.extend(f"- {x}" for x in actions)
    else:
        lines.append("- 조치 내역 미입력")
    lines += ["", "## 재발 방지 / 후속 확인", ""]
    if followups:
        lines.extend(f"- [ ] {x}" for x in followups)
    else:
        lines.append("- [ ] 후속 항목 미입력")
    lines += ["", "## 교대 인수인계", "",
              f"- 현재 상태: {data.get('current_status', '확인 필요')}",
              f"- 다음 확인 시각: {data.get('next_check', '미정')}",
              f"- 에스컬레이션/연락: {data.get('escalation', '필요 시 담당자 확인')}", ""]
    return "\n".join(lines)


def sample() -> dict:
    return {
        "title": "배치 지연 연쇄",
        "severity": "MAJOR",
        "started_at": "2026-09-04T02:13:00",
        "ended_at": "2026-09-04T02:41:00",
        "impact": "일부 후행 배치 지연, 온라인 서비스 직접 중단 없음",
        "root_cause": "처리량 급증으로 APP 커넥션 풀이 배치와 온라인 사이에서 경합",
        "timeline": [
            {"time": "02:13", "event": "배치 지연 알람 발생"},
            {"time": "02:16", "event": "APP CPU/커넥션 사용량 확인"},
            {"time": "02:24", "event": "후행 영향 범위와 마감시간 확인"},
            {"time": "02:31", "event": "우선순위 조정 후 재처리"},
            {"time": "02:41", "event": "후행 정상화 확인"}
        ],
        "actions": ["후행 영향 범위를 확인", "지연 Job 우선순위를 조정", "재처리 후 마감시간 재계산"],
        "followups": ["처리량 급증 임계치 알람 기준 검토", "인수인계 양식에 마감 영향 항목 유지"],
        "current_status": "정상화, 모니터링 중",
        "next_check": "03:30",
        "escalation": "재발 시 APP/배치 담당 동시 에스컬레이션"
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="장애 보고서 및 교대 인수인계 Markdown 생성")
    ap.add_argument("input", nargs="?", help="장애 JSON 입력 파일")
    ap.add_argument("--output", default="incident-report.md", help="출력 Markdown 파일")
    ap.add_argument("--init", action="store_true", help="예시 JSON을 생성하고 종료")
    args = ap.parse_args()

    if args.init:
        path = Path(args.input or "incident-sample.json")
        path.write_text(json.dumps(sample(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"예시 입력 생성: {path}")
        return 0
    if not args.input:
        ap.error("input JSON 파일이 필요합니다. --init으로 예시를 만들 수 있습니다.")
    try:
        data = json.loads(Path(args.input).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"입력 파일을 읽지 못했습니다: {exc}", file=sys.stderr)
        return 2
    if not isinstance(data, dict):
        print("입력 JSON의 최상위는 object여야 합니다.", file=sys.stderr)
        return 2
    report = build_report(data)
    Path(args.output).write_text(report, encoding="utf-8")
    print(report)
    print(f"\n저장: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
