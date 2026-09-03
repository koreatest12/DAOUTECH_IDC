#!/usr/bin/env python3
"""
백업 검증 — 매니페스트 대조

"백업 잡이 성공했다"는 것과 "복구할 수 있는 파일이 있다"는 것은 다르다.
잡은 성공으로 끝났는데 파일이 0바이트이거나, 어제 것이 그대로 남아 있고
오늘 것이 없는 경우를 여러 번 봤다. 그래서 네 가지를 따로 본다.

    존재    — 있어야 할 파일이 실제로 있는가
    크기    — 최소 기대 크기를 넘는가 (0바이트, 중단된 파일 걸러내기)
    신선도  — 몇 시간 안에 만들어진 것인가 (어제 파일 재사용 걸러내기)
    무결성  — SHA-256이 기록과 일치하는가

첫 실행 때 --record로 기준 해시를 만들고, 이후 실행에서 대조한다.

사용법
    python3 backup_verify.py manifest.json --record
    python3 backup_verify.py manifest.json
    python3 backup_verify.py manifest.json --skip-hash    # 대용량일 때
"""

import argparse
import hashlib
import json
import os
import sys
import time
from datetime import datetime

SAMPLE = {
    "base_dir": "/backup/20260902",
    "max_age_hours": 26,
    "files": [
        {"name": "DB_FULL.bak", "min_mb": 1024},
        {"name": "APP_CONF.zip", "min_mb": 1},
        {"name": "WEB_LOGS.tar.gz", "min_mb": 10}
    ]
}


def sha256(path, chunk=1 << 20):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            block = f.read(chunk)
            if not block:
                break
            h.update(block)
    return h.hexdigest()


def human(nbytes):
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if nbytes < 1024 or unit == "TB":
            return f"{nbytes:,.1f} {unit}"
        nbytes /= 1024
    return f"{nbytes:.1f} TB"


def verify(entry, base, max_age, record, skip_hash):
    """반환값: (상태, 사유)  상태는 OK / WARN / FAIL"""
    path = os.path.join(base, entry["name"])

    if not os.path.exists(path):
        return "FAIL", "파일 없음"

    size = os.path.getsize(path)
    min_bytes = int(entry.get("min_mb", 0)) * 1024 * 1024
    if size == 0:
        return "FAIL", "0바이트"
    if min_bytes and size < min_bytes:
        return "FAIL", f"{human(size)} — 기대 최소 {entry['min_mb']}MB 미달"

    age_h = (time.time() - os.path.getmtime(path)) / 3600
    stale = age_h > max_age

    if skip_hash:
        note = f"{human(size)} · {age_h:.1f}시간 전"
        return ("WARN", note + " — 신선도 초과") if stale else ("OK", note + " · 해시 생략")

    digest = sha256(path)
    if record:
        entry["sha256"] = digest
        return "OK", f"{human(size)} · 기준 해시 기록"

    expected = entry.get("sha256")
    if not expected:
        entry["sha256"] = digest
        return "WARN", f"{human(size)} · 기준 해시가 없어 이번 값을 기록"
    if expected != digest:
        return "FAIL", f"해시 불일치 (기대 {expected[:12]}… / 실제 {digest[:12]}…)"

    note = f"{human(size)} · 해시 일치 · {age_h:.1f}시간 전"
    return ("WARN", note + " — 신선도 초과") if stale else ("OK", note)


def main():
    ap = argparse.ArgumentParser(description="백업 파일 검증")
    ap.add_argument("manifest", help="매니페스트 JSON 경로")
    ap.add_argument("--record", action="store_true", help="현재 해시를 기준으로 기록")
    ap.add_argument("--skip-hash", action="store_true", help="해시 계산 생략")
    ap.add_argument("--init", action="store_true", help="예시 매니페스트를 만들고 종료")
    args = ap.parse_args()

    if args.init:
        with open(args.manifest, "w", encoding="utf-8") as f:
            json.dump(SAMPLE, f, ensure_ascii=False, indent=2)
        print(f"예시 매니페스트를 만들었습니다: {args.manifest}")
        return 0

    try:
        with open(args.manifest, encoding="utf-8") as f:
            m = json.load(f)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"매니페스트를 읽지 못했습니다: {exc}", file=sys.stderr)
        return 2

    base = m.get("base_dir", ".")
    max_age = float(m.get("max_age_hours", 26))
    files = m.get("files", [])

    print(f"\n검증 대상: {base}")
    print(f"기준 시각: {datetime.now():%Y-%m-%d %H:%M:%S} · 신선도 상한 {max_age:.0f}시간")
    print("=" * 78)

    counts = {"OK": 0, "WARN": 0, "FAIL": 0}
    for entry in files:
        try:
            status, note = verify(entry, base, max_age, args.record, args.skip_hash)
        except OSError as exc:
            status, note = "FAIL", f"읽기 실패: {exc}"
        counts[status] += 1
        print(f"  [{status:<4}] {entry['name']:<28} {note}")

    if args.record or any(e.get("sha256") for e in files):
        try:
            with open(args.manifest, "w", encoding="utf-8") as f:
                json.dump(m, f, ensure_ascii=False, indent=2)
        except OSError as exc:
            print(f"매니페스트 갱신 실패: {exc}", file=sys.stderr)

    print("-" * 78)
    print(f"정상 {counts['OK']} · 주의 {counts['WARN']} · 실패 {counts['FAIL']}")

    if counts["FAIL"]:
        print("복구에 쓸 수 없는 파일이 있습니다. 백업 잡 로그를 확인하십시오.")
        return 2
    if counts["WARN"]:
        print("확인이 필요한 항목이 있습니다.")
        return 1
    print("모든 백업 파일이 기준을 만족합니다.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
