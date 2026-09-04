#!/usr/bin/env python3
"""Calculate service availability and allowed downtime for common SLA targets."""

from __future__ import annotations

import argparse
from dataclasses import dataclass


@dataclass(frozen=True)
class SLAResult:
    target: float
    period_minutes: float
    allowed_downtime: float
    actual_downtime: float
    actual_availability: float
    passed: bool


def allowed_downtime_minutes(target_percent: float, period_minutes: float) -> float:
    return period_minutes * (1.0 - target_percent / 100.0)


def availability_percent(period_minutes: float, downtime_minutes: float) -> float:
    if period_minutes <= 0:
        raise ValueError("period_minutes must be positive")
    downtime = min(max(downtime_minutes, 0.0), period_minutes)
    return (period_minutes - downtime) / period_minutes * 100.0


def evaluate(target: float, period_minutes: float, actual_downtime: float) -> SLAResult:
    allowed = allowed_downtime_minutes(target, period_minutes)
    actual = availability_percent(period_minutes, actual_downtime)
    return SLAResult(target, period_minutes, allowed, actual_downtime, actual, actual_downtime <= allowed + 1e-9)


def period_to_minutes(days: float) -> float:
    if days <= 0:
        raise ValueError("days must be positive")
    return days * 24.0 * 60.0


def main() -> int:
    ap = argparse.ArgumentParser(description="SLA 가용성/허용 장애시간 계산")
    ap.add_argument("--days", type=float, default=30.0, help="평가 기간(일)")
    ap.add_argument("--downtime", type=float, default=0.0, help="실제 장애시간(분)")
    ap.add_argument("--targets", type=float, nargs="*", default=[99.9, 99.95, 99.99], help="SLA 목표 퍼센트")
    args = ap.parse_args()
    try:
        period = period_to_minutes(args.days)
    except ValueError as exc:
        ap.error(str(exc))
    print(f"평가 기간: {args.days:g}일 ({period:,.0f}분) · 실제 장애 {args.downtime:.1f}분")
    print("=" * 78)
    print(f"{'SLA':>9}{'허용 장애':>16}{'실제 가용성':>18}{'판정':>12}")
    worst = 0
    for target in args.targets:
        if not (0 < target <= 100):
            print(f"잘못된 SLA 목표: {target}")
            worst = 2
            continue
        r = evaluate(target, period, args.downtime)
        verdict = "PASS" if r.passed else "FAIL"
        print(f"{target:>8.3f}%{r.allowed_downtime:>14.2f}분{r.actual_availability:>17.5f}%{verdict:>12}")
        if not r.passed:
            worst = max(worst, 1)
    return worst


if __name__ == "__main__":
    raise SystemExit(main())
