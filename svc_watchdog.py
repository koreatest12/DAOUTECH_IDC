#!/usr/bin/env python3
"""
서비스 워치독 — 정지 감지, 재기동, 상한 관리

무조건 재기동하는 워치독은 위험하다. 근본 원인이 남아 있는데 계속 살려
두면 문제가 감춰지고, 재기동 자체가 부하가 되어 다른 서비스까지 흔든다.
그래서 세 가지 제동을 걸었다.

    1. 백오프    — 재기동 간격을 5초 → 15초 → 45초로 늘린다
    2. 상한      — 창(기본 1시간) 안에서 3회를 넘으면 재기동을 멈춘다
    3. 포기 통지 — 상한에 걸리면 사람이 봐야 한다고 기록하고 종료 코드 2

상태는 파일에 남긴다. 스크립트가 죽어도 재기동 횟수가 초기화되지 않아야
상한이 의미를 가진다.

사용법
    python3 svc_watchdog.py nginx sshd
    python3 svc_watchdog.py nginx --max-restarts 2 --window 1800
    python3 svc_watchdog.py nginx --dry-run
"""

import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
import time
from datetime import datetime

WIN = platform.system() == "Windows"
BACKOFF = (5, 15, 45)


def run(cmd, timeout=30):
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return p.returncode, (p.stdout or "").strip()
    except (OSError, subprocess.SubprocessError) as exc:
        return 1, str(exc)


def is_running(name):
    if WIN:
        rc, out = run(["powershell", "-NoProfile", "-Command",
                       f"(Get-Service -Name '{name}' -ErrorAction SilentlyContinue).Status"])
        return out == "Running", out or "서비스 없음"
    if shutil.which("systemctl"):
        rc, out = run(["systemctl", "is-active", name])
        return rc == 0, out or "unknown"
    rc, _ = run(["pgrep", "-x", name])
    return rc == 0, "구동 중" if rc == 0 else "프로세스 없음"


def start(name):
    if WIN:
        return run(["powershell", "-NoProfile", "-Command", f"Start-Service -Name '{name}'"])
    if shutil.which("systemctl"):
        return run(["systemctl", "start", name])
    return 1, "재기동 방법을 찾지 못했습니다"


def load_state(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}


def save_state(path, state):
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=1)
    except OSError as exc:
        print(f"상태 저장 실패: {exc}", file=sys.stderr)


def recent(times, window):
    now = time.time()
    return [t for t in times if now - t <= window]


def log(msg):
    print(f"{datetime.now():%H:%M:%S}  {msg}")


def watch(name, state, args):
    """반환값: 0 정상 / 1 재기동 성공 / 2 조치 필요"""
    entry = state.setdefault(name, {"restarts": []})
    entry["restarts"] = recent(entry["restarts"], args.window)

    alive, detail = is_running(name)
    if alive:
        log(f"{name:<18} 정상 ({detail})")
        return 0

    log(f"{name:<18} 정지 감지 ({detail})")

    if len(entry["restarts"]) >= args.max_restarts:
        oldest = datetime.fromtimestamp(min(entry["restarts"]))
        log(f"{name:<18} 재기동 상한 {args.max_restarts}회 도달 "
            f"(최초 {oldest:%H:%M} 이후). 자동 재기동을 멈춥니다.")
        log(f"{name:<18} 사람의 확인이 필요합니다 — 로그와 자원 상태를 먼저 보십시오.")
        return 2

    if args.dry_run:
        log(f"{name:<18} 재기동 대상 (dry-run이라 실행하지 않음)")
        return 1

    for attempt, wait in enumerate(BACKOFF, 1):
        rc, out = start(name)
        entry["restarts"].append(time.time())
        time.sleep(wait)
        alive, detail = is_running(name)
        if alive:
            log(f"{name:<18} 재기동 성공 ({attempt}회차, {wait}초 대기 후 확인)")
            return 1
        log(f"{name:<18} {attempt}회차 실패 — {out or detail}")
        if len(entry["restarts"]) >= args.max_restarts:
            break

    log(f"{name:<18} 재기동 실패. 조치가 필요합니다.")
    return 2


def main():
    ap = argparse.ArgumentParser(description="서비스 감시 및 재기동")
    ap.add_argument("services", nargs="+", help="감시할 서비스 이름")
    ap.add_argument("--state", default="./watchdog_state.json", help="상태 파일 경로")
    ap.add_argument("--max-restarts", type=int, default=3, help="창 안에서 허용할 재기동 횟수")
    ap.add_argument("--window", type=int, default=3600, help="상한 판정 창(초)")
    ap.add_argument("--dry-run", action="store_true", help="감지만 하고 재기동하지 않음")
    args = ap.parse_args()

    state = load_state(args.state)
    worst = 0
    for name in args.services:
        worst = max(worst, watch(name, state, args))
    save_state(args.state, state)

    print("-" * 60)
    if args.dry_run:
        print({0: "모든 서비스가 정상입니다.",
               1: "정지된 서비스가 있습니다. dry-run이라 재기동하지 않았습니다.",
               2: "재기동 상한에 걸린 서비스가 있습니다."}[worst])
    else:
        print({0: "모든 서비스가 정상입니다.",
               1: "정지된 서비스를 재기동했습니다. 원인 확인이 필요합니다.",
               2: "자동 조치로 해결되지 않았습니다."}[worst])
    sys.exit(worst)


if __name__ == "__main__":
    main()
