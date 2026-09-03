#!/usr/bin/env python3
"""
디스크 임계 도달 예측

디스크 경보는 90%를 넘은 뒤에 울린다. 그 시점에는 이미 야간이고, 지울
것을 찾거나 증설을 요청할 시간이 없다. 이 스크립트는 매일 사용률을
기록해 두고 추세선으로 임계 도달 시점을 미리 계산한다.

    1회 실행 → 현재 사용률을 이력 파일에 추가
    이력 3회 이상 → 최소제곱 직선으로 일일 증가율 산출 → 임계 도달일 예측

이력은 JSON 한 파일에 쌓는다. 별도 DB나 수집 서버 없이 cron 한 줄로
동작해야 실제로 매일 돌아가기 때문이다.

사용법
    python3 disk_forecast.py                       # 전체 마운트 지점
    python3 disk_forecast.py / /data --threshold 90
    python3 disk_forecast.py --history /var/tmp/disk.json --alert-days 14
"""

import argparse
import json
import os
import shutil
import socket
import sys
from datetime import date, timedelta

SKIP_FS = {
    "proc", "sysfs", "devtmpfs", "tmpfs", "cgroup", "cgroup2", "overlay",
    "squashfs", "devpts", "mqueue", "debugfs", "tracefs", "securityfs",
    "pstore", "bpf", "configfs", "hugetlbfs", "fusectl", "nsfs", "autofs",
    "binfmt_misc", "ramfs",
}


def mount_points():
    if os.name == "nt":
        import string
        return [f"{d}:\\" for d in string.ascii_uppercase
                if os.path.exists(f"{d}:\\")]
    points, seen = [], set()
    try:
        with open("/proc/mounts") as f:
            for line in f:
                parts = line.split()
                if len(parts) >= 3 and parts[2] not in SKIP_FS and parts[1] not in seen:
                    seen.add(parts[1])
                    points.append(parts[1])
    except OSError:
        pass
    return points or ["/"]


def load(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}


def save(path, data):
    try:
        directory = os.path.dirname(os.path.abspath(path))
        if directory:
            os.makedirs(directory, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=1)
    except OSError as exc:
        print(f"이력 저장 실패: {exc}", file=sys.stderr)


def record(history, point, pct, free_gib):
    entries = history.setdefault(point, [])
    today = date.today().isoformat()
    entries[:] = [e for e in entries if e["d"] != today]
    entries.append({"d": today, "p": round(pct, 2), "f": round(free_gib, 1)})
    entries.sort(key=lambda e: e["d"])
    del entries[:-180]          # 최근 180일만 유지
    return entries


def slope_per_day(entries):
    """최소제곱 직선의 기울기(%/일)를 구한다. 표본이 적으면 None."""
    if len(entries) < 3:
        return None
    base = date.fromisoformat(entries[0]["d"])
    xs = [(date.fromisoformat(e["d"]) - base).days for e in entries]
    ys = [e["p"] for e in entries]
    n = len(xs)
    mx = sum(xs) / n
    my = sum(ys) / n
    denom = sum((x - mx) ** 2 for x in xs)
    if denom == 0:
        return None
    return sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / denom


def days_to(pct, slope, target):
    if slope is None or slope <= 0.001 or pct >= target:
        return None
    return (target - pct) / slope


def main():
    ap = argparse.ArgumentParser(description="디스크 임계 도달 예측")
    ap.add_argument("paths", nargs="*", help="점검할 경로 (생략 시 전체 마운트)")
    ap.add_argument("--history", default="./disk_history.json", help="이력 파일 경로")
    ap.add_argument("--threshold", type=float, default=90.0, help="임계 사용률 %%")
    ap.add_argument("--alert-days", type=int, default=30,
                    help="임계 도달까지 이 일수 이내면 경고")
    args = ap.parse_args()

    history = load(args.history)
    targets = args.paths or mount_points()
    worst = 0

    print(f"{socket.gethostname()} · {date.today()} · 임계 {args.threshold:.0f}%")
    print("=" * 78)
    print(f"{'경로':<26}{'사용률':>8}{'여유':>11}{'증가/일':>10}{'임계 도달':>16}")
    print("-" * 78)

    for point in targets:
        try:
            usage = shutil.disk_usage(point)
        except OSError:
            print(f"{point:<26}{'확인 불가':>8}")
            worst = max(worst, 1)
            continue

        pct = usage.used / usage.total * 100 if usage.total else 0
        free_gib = usage.free / 2 ** 30
        entries = record(history, point, pct, free_gib)
        slope = slope_per_day(entries)
        left = days_to(pct, slope, args.threshold)

        if pct >= args.threshold:
            eta, level = "이미 초과", 2
        elif left is None:
            eta = "증가 없음" if slope is not None else f"이력 {len(entries)}일"
            level = 0
        else:
            when = date.today() + timedelta(days=int(left))
            eta = f"{int(left)}일 후 {when:%m-%d}"
            level = 1 if left <= args.alert_days else 0

        rate = f"{slope:+.2f}%" if slope is not None else "—"
        mark = "  ●" if level == 2 else "  ▲" if level == 1 else ""
        print(f"{point:<26}{pct:>7.1f}%{free_gib:>9.1f}G{rate:>10}{eta:>16}{mark}")
        worst = max(worst, level)

    save(args.history, history)
    print("-" * 78)
    print({0: "임계 도달이 임박한 파일시스템은 없습니다.",
           1: f"{args.alert_days}일 이내 임계 도달이 예상되는 파일시스템이 있습니다.",
           2: "임계를 이미 초과한 파일시스템이 있습니다."}[worst])
    print(f"이력: {args.history}")
    sys.exit(worst)


if __name__ == "__main__":
    main()
