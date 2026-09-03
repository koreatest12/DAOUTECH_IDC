#!/usr/bin/env python3
"""
로그 분석기 — 오류 유형별 집계와 급증 구간 탐지

교대 근무 중 로그를 눈으로 훑으면 건수가 많은 오류만 보이고, 평소보다
갑자기 늘어난 오류는 놓치기 쉽다. 이 스크립트는 두 가지를 함께 본다.

    1. 오류 유형별 건수  — 무엇이 많이 나는가
    2. 시간대별 분포     — 언제 평소보다 많이 났는가

가변 부분(타임스탬프, PID, IP, 경로, 숫자)을 치환해 같은 원인의 로그를
하나의 유형으로 묶는다. 이 정규화가 없으면 같은 오류가 수백 개의 서로
다른 문자열로 흩어져 집계가 무의미해진다.

사용법
    python3 log_analyzer.py /var/log/messages
    python3 log_analyzer.py /var/log/secure --level ERROR --top 15
    python3 log_analyzer.py app.log --sigma 2.5
"""

import argparse
import re
import sys
from collections import Counter, defaultdict

LEVELS = ("EMERG", "ALERT", "CRIT", "FATAL", "ERROR", "ERR", "WARN", "WARNING")

# 시:분 추출 — syslog(Sep  2 03:14:15)와 ISO(2026-09-02T03:14:15) 모두 대응
TIME_RE = re.compile(r"(?:^\w{3}\s+\d{1,2}\s+|^\d{4}-\d{2}-\d{2}[T ])(\d{2}):(\d{2})")

# 가변 요소 치환 규칙 — 순서가 중요하다(IP를 먼저 잡아야 숫자 규칙에 먹히지 않는다)
NORMALIZE = [
    (re.compile(r"\b\d{1,3}(?:\.\d{1,3}){3}(?::\d+)?\b"), "<ip>"),
    (re.compile(r"\b[0-9a-fA-F]{2}(?::[0-9a-fA-F]{2}){5}\b"), "<mac>"),
    (re.compile(r"\b[0-9a-fA-F]{8}-(?:[0-9a-fA-F]{4}-){3}[0-9a-fA-F]{12}\b"), "<uuid>"),
    (re.compile(r"(?<=\[)\d+(?=\])"), "<pid>"),
    (re.compile(r"\b/[^\s:]{4,}"), "<path>"),
    (re.compile(r"\b0x[0-9a-fA-F]+\b"), "<hex>"),
    (re.compile(r"\b\d+\b"), "<n>"),
]


def normalize(line):
    text = line.strip()
    text = re.sub(r"^\w{3}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2}\s+\S+\s+", "", text)
    text = re.sub(r"^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}\S*\s+", "", text)
    for pattern, token in NORMALIZE:
        text = pattern.sub(token, text)
    return text[:150]


def hour_min(line):
    m = TIME_RE.search(line)
    return f"{m.group(1)}:{m.group(2)[0]}0" if m else None


def analyze(path, wanted, sigma):
    kinds = Counter()
    samples = {}
    buckets = defaultdict(int)
    total = matched = 0

    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            for line in f:
                total += 1
                upper = line.upper()
                if not any(lv in upper for lv in wanted):
                    continue
                matched += 1
                key = normalize(line)
                kinds[key] += 1
                samples.setdefault(key, line.strip())
                slot = hour_min(line)
                if slot:
                    buckets[slot] += 1
    except OSError as exc:
        print(f"로그를 읽지 못했습니다: {exc}", file=sys.stderr)
        return None

    return {"total": total, "matched": matched, "kinds": kinds,
            "samples": samples, "buckets": buckets, "sigma": sigma}


def spikes(buckets, sigma):
    """10분 단위 건수의 평균 + sigma×표준편차를 넘는 구간을 급증으로 본다."""
    if len(buckets) < 4:
        return []
    values = list(buckets.values())
    mean = sum(values) / len(values)
    var = sum((v - mean) ** 2 for v in values) / len(values)
    sd = var ** 0.5
    if sd == 0:
        return []
    cut = mean + sigma * sd
    found = [(slot, n, (n - mean) / sd) for slot, n in buckets.items() if n > cut]
    return sorted(found, key=lambda x: -x[1]), mean, sd


def bar(n, peak, width=28):
    return "█" * max(1, round(n / peak * width)) if n else ""


def report(res, top):
    print(f"\n전체 {res['total']:,}행 중 대상 {res['matched']:,}행")
    if not res["matched"]:
        print("해당 수준의 로그가 없습니다.")
        return 0

    print(f"\n오류 유형 상위 {top}개")
    print("-" * 76)
    peak = res["kinds"].most_common(1)[0][1]
    for kind, n in res["kinds"].most_common(top):
        share = n / res["matched"] * 100
        print(f"{n:>6,}건 {share:>5.1f}%  {bar(n, peak, 16):<16} {kind}")

    print(f"\n서로 다른 유형: {len(res['kinds']):,}개")

    result = spikes(res["buckets"], res["sigma"])
    if not result:
        print("\n급증 구간: 판단할 만큼 데이터가 모이지 않았습니다.")
        return 0

    found, mean, sd = result
    print(f"\n시간대별 분포 (10분 단위, 평균 {mean:.1f}건 · 표준편차 {sd:.1f})")
    print("-" * 76)
    top_slot = max(res["buckets"].values())
    for slot in sorted(res["buckets"]):
        n = res["buckets"][slot]
        mark = "  ← 급증" if any(s == slot for s, _, _ in found) else ""
        print(f"{slot}  {n:>5,}건  {bar(n, top_slot):<28}{mark}")

    if found:
        print(f"\n급증 구간 {len(found)}개 — 평균 대비 {res['sigma']}배 표준편차 초과")
        for slot, n, z in found:
            print(f"  {slot}  {n:,}건 (z={z:.1f})")
            sample_key = max(
                (k for k in res["kinds"]),
                key=lambda k: res["kinds"][k])
            print(f"      대표 로그: {res['samples'][sample_key][:110]}")
        return 1
    return 0


def main():
    ap = argparse.ArgumentParser(description="로그 오류 집계 및 급증 탐지")
    ap.add_argument("logfile", help="분석할 로그 파일")
    ap.add_argument("--level", nargs="*", default=None,
                    help=f"대상 수준 (기본: {' '.join(LEVELS)})")
    ap.add_argument("--top", type=int, default=10, help="표시할 유형 수")
    ap.add_argument("--sigma", type=float, default=2.0, help="급증 판정 기준")
    args = ap.parse_args()

    wanted = tuple(x.upper() for x in args.level) if args.level else LEVELS
    res = analyze(args.logfile, wanted, args.sigma)
    if res is None:
        sys.exit(2)
    sys.exit(report(res, args.top))


if __name__ == "__main__":
    main()
