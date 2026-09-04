#!/usr/bin/env python3
"""Forecast CPU, memory and disk threshold dates from simple daily history."""

from __future__ import annotations

import argparse
import json
import math
import sys
from datetime import date, timedelta
from pathlib import Path

METRICS = ("cpu", "memory", "disk")
DEFAULT_THRESHOLDS = {"cpu": 80.0, "memory": 85.0, "disk": 90.0}


def slope_per_day(rows: list[dict], metric: str) -> float | None:
    points = [(date.fromisoformat(str(r["date"])), float(r[metric])) for r in rows if metric in r]
    if len(points) < 3:
        return None
    points.sort(key=lambda x: x[0])
    base = points[0][0]
    xs = [(d - base).days for d, _ in points]
    ys = [v for _, v in points]
    mx, my = sum(xs) / len(xs), sum(ys) / len(ys)
    denom = sum((x - mx) ** 2 for x in xs)
    if denom == 0:
        return None
    return sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / denom


def days_to_threshold(current: float, slope: float | None, threshold: float) -> float | None:
    if current >= threshold:
        return 0.0
    if slope is None or slope <= 0.001:
        return None
    return max(0.0, (threshold - current) / slope)


def analyze(rows: list[dict], thresholds: dict[str, float] | None = None) -> list[dict]:
    if not rows:
        return []
    thresholds = thresholds or DEFAULT_THRESHOLDS
    ordered = sorted(rows, key=lambda r: str(r["date"]))
    latest = ordered[-1]
    result = []
    for metric in METRICS:
        if metric not in latest:
            continue
        current = float(latest[metric])
        slope = slope_per_day(ordered, metric)
        threshold = float(thresholds[metric])
        days = days_to_threshold(current, slope, threshold)
        eta = None if days is None else (date.fromisoformat(str(latest["date"])) + timedelta(days=math.ceil(days))).isoformat()
        status = "CRIT" if current >= threshold else "WARN" if days is not None and days <= 30 else "OK"
        result.append({"metric": metric, "current": current, "slope_per_day": slope, "threshold": threshold, "days_to_threshold": days, "eta": eta, "status": status})
    return result


def render(rows: list[dict], result: list[dict]) -> str:
    lines = ["# Capacity Planning 결과", "", f"- 입력 이력: **{len(rows)}일**", "", "| 상태 | 자원 | 현재 | 증가/일 | 임계치 | 예상 |", "|---|---|---:|---:|---:|---|"]
    for item in result:
        slope = "—" if item["slope_per_day"] is None else f"{item['slope_per_day']:+.2f}%"
        if item["days_to_threshold"] is None:
            eta = "증가 추세 없음/데이터 부족"
        elif item["days_to_threshold"] == 0:
            eta = "이미 임계 초과"
        else:
            eta = f"{math.ceil(item['days_to_threshold'])}일 후 ({item['eta']})"
        lines.append(f"| {item['status']} | {item['metric']} | {item['current']:.1f}% | {slope} | {item['threshold']:.1f}% | {eta} |")
    return "\n".join(lines) + "\n"


def sample() -> list[dict]:
    return [
        {"date":"2026-08-31","cpu":46.0,"memory":63.0,"disk":72.0},
        {"date":"2026-09-01","cpu":48.0,"memory":64.5,"disk":73.1},
        {"date":"2026-09-02","cpu":51.0,"memory":66.0,"disk":74.2},
        {"date":"2026-09-03","cpu":53.0,"memory":67.2,"disk":75.1},
        {"date":"2026-09-04","cpu":55.0,"memory":68.3,"disk":76.0}
    ]


def main() -> int:
    ap = argparse.ArgumentParser(description="CPU/메모리/디스크 Capacity Planning")
    ap.add_argument("input", nargs="?", help="일별 자원 이력 JSON 배열")
    ap.add_argument("--output", default="capacity-report.md")
    ap.add_argument("--init", action="store_true", help="예시 이력 생성")
    ap.add_argument("--cpu", type=float, default=DEFAULT_THRESHOLDS["cpu"])
    ap.add_argument("--memory", type=float, default=DEFAULT_THRESHOLDS["memory"])
    ap.add_argument("--disk", type=float, default=DEFAULT_THRESHOLDS["disk"])
    args = ap.parse_args()
    if args.init:
        path = Path(args.input or "capacity-sample.json")
        path.write_text(json.dumps(sample(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"예시 이력 생성: {path}")
        return 0
    if not args.input:
        ap.error("input JSON 파일이 필요합니다.")
    try:
        rows = json.loads(Path(args.input).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"입력 오류: {exc}", file=sys.stderr)
        return 2
    if not isinstance(rows, list):
        print("입력 JSON은 배열이어야 합니다.", file=sys.stderr)
        return 2
    try:
        result = analyze(rows, {"cpu": args.cpu, "memory": args.memory, "disk": args.disk})
    except (KeyError, ValueError, TypeError) as exc:
        print(f"이력 형식 오류: {exc}", file=sys.stderr)
        return 2
    text = render(rows, result)
    Path(args.output).write_text(text, encoding="utf-8")
    print(text)
    return 1 if any(x["status"] == "CRIT" for x in result) else 0


if __name__ == "__main__":
    raise SystemExit(main())
