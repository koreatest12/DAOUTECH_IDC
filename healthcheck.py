#!/usr/bin/env python3
"""
서버 헬스체크 — IDC 상면 운영용 일상 점검 스크립트

점검 항목
    1. 호스트 정보와 업타임
    2. CPU 부하 (1분 평균을 코어 수로 정규화)
    3. 메모리 사용률
    4. 파일시스템별 사용률
    5. 지정 서비스/프로세스 구동 여부
    6. 대상지 네트워크 도달성
    7. 메모리 상위 프로세스

설계 의도
    - 표준 라이브러리만 사용한다. 점검 대상 서버에 패키지를 설치할 수 없는
      경우가 많고, 설치를 요구하는 순간 점검이 밀리기 때문이다.
    - 결과를 화면과 날짜별 로그 파일에 동시에 남긴다. 나중에 "그때 상태가
      어땠는지"를 확인할 수 없으면 점검한 의미가 없다.
    - 종료 코드로 결과를 알린다. cron이나 작업 스케줄러가 판단할 수 있어야
      사람이 매번 열어보지 않아도 된다.
        0 = 정상   1 = 주의 (임계치 초과)   2 = 조치 필요 (점검 실패)

사용법
    python3 healthcheck.py
    python3 healthcheck.py --config check.json
    python3 healthcheck.py --quiet          # 로그 파일에만 기록
"""

import argparse
import json
import os
import platform
import shutil
import socket
import subprocess
import sys
from datetime import datetime

# ── 기본 임계치 ────────────────────────────────────────────────
DEFAULT = {
    "cpu_warn": 80,           # 코어당 부하 백분율
    "mem_warn": 85,
    "disk_warn": 85,
    "disk_crit": 92,
    "services": [],           # 예: ["sshd", "nginx", "crond"]
    "ping_targets": [],       # 예: ["10.20.0.1", "8.8.8.8"]
    "log_dir": "./healthcheck_logs",
}

WIN = platform.system() == "Windows"

OK, WARN, CRIT, INFO = "OK", "WARN", "CRIT", "INFO"
_RANK = {OK: 0, INFO: 0, WARN: 1, CRIT: 2}


class Report:
    """점검 결과를 모으고 최종 종료 코드를 계산한다."""

    def __init__(self, quiet=False):
        self.lines = []
        self.worst = 0
        self.quiet = quiet

    def add(self, level, item, detail):
        self.worst = max(self.worst, _RANK[level])
        line = f"  [{level:<4}] {item:<22} {detail}"
        self.lines.append(line)
        if not self.quiet:
            print(line)

    def head(self, text):
        line = f"\n{text}\n" + "-" * 68
        self.lines.append(line)
        if not self.quiet:
            print(line)

    def text(self):
        return "\n".join(self.lines)


# ── 개별 점검 ──────────────────────────────────────────────────
def check_host(rep):
    rep.head("호스트")
    rep.add(INFO, "호스트명", socket.gethostname())
    rep.add(INFO, "OS", f"{platform.system()} {platform.release()}")
    rep.add(INFO, "점검 시각", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    up = uptime_seconds()
    if up is None:
        rep.add(INFO, "업타임", "확인 불가")
    else:
        d, rem = divmod(int(up), 86400)
        h, rem = divmod(rem, 3600)
        rep.add(INFO, "업타임", f"{d}일 {h}시간 {rem // 60}분")


def uptime_seconds():
    if not WIN:
        try:
            with open("/proc/uptime") as f:
                return float(f.read().split()[0])
        except OSError:
            return None
    out = run_ps("(Get-Date) - (Get-CimInstance Win32_OperatingSystem).LastBootUpTime "
                 "| Select-Object -ExpandProperty TotalSeconds")
    try:
        return float(out.strip())
    except (TypeError, ValueError):
        return None


def check_cpu(rep, cfg):
    rep.head("CPU")
    cores = os.cpu_count() or 1
    if WIN:
        out = run_ps("(Get-CimInstance Win32_Processor | "
                     "Measure-Object -Property LoadPercentage -Average).Average")
        try:
            pct = float(out.strip())
        except (TypeError, ValueError):
            rep.add(WARN, "CPU 사용률", "측정 실패")
            return
        rep.add(WARN if pct >= cfg["cpu_warn"] else OK, "CPU 사용률", f"{pct:.0f}%")
        return

    try:
        load1, load5, load15 = os.getloadavg()
    except (OSError, AttributeError):
        rep.add(WARN, "로드 애버리지", "측정 실패")
        return

    pct = load1 / cores * 100
    level = WARN if pct >= cfg["cpu_warn"] else OK
    rep.add(level, "로드 애버리지",
            f"{load1:.2f} / {load5:.2f} / {load15:.2f}  (코어 {cores}개, 환산 {pct:.0f}%)")


def check_memory(rep, cfg):
    rep.head("메모리")
    if WIN:
        out = run_ps("$o=Get-CimInstance Win32_OperatingSystem; "
                     "'{0} {1}' -f $o.TotalVisibleMemorySize,$o.FreePhysicalMemory")
        try:
            total_kb, free_kb = (float(x) for x in out.split())
        except (TypeError, ValueError):
            rep.add(WARN, "메모리", "측정 실패")
            return
        used_pct = (total_kb - free_kb) / total_kb * 100
        rep.add(WARN if used_pct >= cfg["mem_warn"] else OK, "물리 메모리",
                f"{used_pct:.0f}% 사용 ({(total_kb - free_kb) / 1048576:.1f} / "
                f"{total_kb / 1048576:.1f} GiB)")
        return

    info = {}
    try:
        with open("/proc/meminfo") as f:
            for line in f:
                k, _, v = line.partition(":")
                info[k] = float(v.strip().split()[0])   # kB
    except OSError:
        rep.add(WARN, "메모리", "/proc/meminfo 읽기 실패")
        return

    total = info.get("MemTotal", 0)
    avail = info.get("MemAvailable", info.get("MemFree", 0))
    if not total:
        rep.add(WARN, "메모리", "총량 확인 불가")
        return

    used_pct = (total - avail) / total * 100
    rep.add(WARN if used_pct >= cfg["mem_warn"] else OK, "물리 메모리",
            f"{used_pct:.0f}% 사용 ({(total - avail) / 1048576:.1f} / {total / 1048576:.1f} GiB)")

    sw_total = info.get("SwapTotal", 0)
    if sw_total:
        sw_used = (sw_total - info.get("SwapFree", 0)) / sw_total * 100
        rep.add(WARN if sw_used >= 50 else OK, "스왑", f"{sw_used:.0f}% 사용")


def check_disks(rep, cfg):
    rep.head("파일시스템")
    for mount in mount_points():
        try:
            usage = shutil.disk_usage(mount)
        except OSError:
            continue
        pct = usage.used / usage.total * 100 if usage.total else 0
        level = CRIT if pct >= cfg["disk_crit"] else WARN if pct >= cfg["disk_warn"] else OK
        rep.add(level, mount,
                f"{pct:.0f}% 사용 · 여유 {usage.free / 2**30:.1f} GiB / "
                f"{usage.total / 2**30:.1f} GiB")


def mount_points():
    if WIN:
        out = run_ps("(Get-PSDrive -PSProvider FileSystem).Root")
        return [d.strip() for d in (out or "").splitlines() if d.strip()]

    seen, points = set(), []
    try:
        with open("/proc/mounts") as f:
            for line in f:
                parts = line.split()
                if len(parts) < 3:
                    continue
                dev, point, fstype = parts[0], parts[1], parts[2]
                if fstype in ("proc", "sysfs", "devtmpfs", "tmpfs", "cgroup", "cgroup2",
                              "overlay", "squashfs", "devpts", "mqueue", "debugfs",
                              "tracefs", "securityfs", "pstore", "bpf", "configfs",
                              "hugetlbfs", "fusectl", "nsfs", "autofs", "binfmt_misc"):
                    continue
                if point in seen:
                    continue
                seen.add(point)
                points.append(point)
    except OSError:
        points = ["/"]
    return points or ["/"]


def check_services(rep, cfg):
    names = cfg.get("services") or []
    if not names:
        return
    rep.head("서비스")
    for name in names:
        rep.add(*service_state(name))


def service_state(name):
    if WIN:
        out = run_ps(f"(Get-Service -Name '{name}' -ErrorAction SilentlyContinue).Status")
        state = (out or "").strip()
        if not state:
            return CRIT, name, "서비스를 찾을 수 없음"
        return (OK if state == "Running" else CRIT), name, state

    if shutil.which("systemctl"):
        rc, out = run(["systemctl", "is-active", name])
        state = out.strip() or "unknown"
        return (OK if rc == 0 else CRIT), name, state

    rc, _ = run(["pgrep", "-x", name])
    return (OK if rc == 0 else CRIT), name, "구동 중" if rc == 0 else "프로세스 없음"


def check_network(rep, cfg):
    targets = cfg.get("ping_targets") or []
    if not targets:
        return
    rep.head("네트워크 도달성")
    flag = "-n" if WIN else "-c"
    for host in targets:
        rc, _ = run(["ping", flag, "2", host])
        rep.add(OK if rc == 0 else CRIT, host, "응답" if rc == 0 else "무응답")


def check_top_processes(rep, limit=5):
    rep.head(f"메모리 상위 프로세스 {limit}개")
    if WIN:
        out = run_ps(f"Get-Process | Sort-Object WS -Descending | Select-Object -First {limit} "
                     "| ForEach-Object {{ '{0} {1:N0}' -f $_.ProcessName, ($_.WS/1MB) }}")
        rows = [ln.rsplit(" ", 1) for ln in (out or "").splitlines() if ln.strip()]
        for name, mb in rows:
            rep.add(INFO, name[:22], f"{mb} MiB")
        return

    rc, out = run(["ps", "-eo", "rss,comm", "--sort=-rss"])
    if rc != 0:
        rep.add(INFO, "프로세스", "조회 실패")
        return
    for line in out.splitlines()[1:limit + 1]:
        rss, _, comm = line.strip().partition(" ")
        try:
            mib = int(rss) / 1024
        except ValueError:
            continue
        rep.add(INFO, comm.strip()[:22], f"{mib:,.0f} MiB")


# ── 실행 보조 ──────────────────────────────────────────────────
def run(cmd):
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        return p.returncode, p.stdout
    except (OSError, subprocess.SubprocessError):
        return 1, ""


def run_ps(script):
    rc, out = run(["powershell", "-NoProfile", "-NonInteractive", "-Command", script])
    return out if rc == 0 else None


def write_log(cfg, body):
    directory = cfg.get("log_dir") or "."
    try:
        os.makedirs(directory, exist_ok=True)
        path = os.path.join(directory, f"health_{datetime.now():%Y%m%d}.log")
        with open(path, "a", encoding="utf-8") as f:
            f.write(f"\n{'=' * 68}\n{datetime.now():%Y-%m-%d %H:%M:%S} "
                    f"{socket.gethostname()}\n{'=' * 68}\n{body}\n")
        return path
    except OSError as exc:
        print(f"로그 기록 실패: {exc}", file=sys.stderr)
        return None


def load_config(path):
    cfg = dict(DEFAULT)
    if path:
        try:
            with open(path, encoding="utf-8") as f:
                cfg.update(json.load(f))
        except (OSError, json.JSONDecodeError) as exc:
            print(f"설정 파일을 읽지 못해 기본값으로 진행합니다: {exc}", file=sys.stderr)
    return cfg


def main():
    ap = argparse.ArgumentParser(description="서버 헬스체크")
    ap.add_argument("--config", help="JSON 설정 파일 경로")
    ap.add_argument("--quiet", action="store_true", help="로그 파일에만 기록")
    args = ap.parse_args()

    cfg = load_config(args.config)
    rep = Report(quiet=args.quiet)

    check_host(rep)
    check_cpu(rep, cfg)
    check_memory(rep, cfg)
    check_disks(rep, cfg)
    check_services(rep, cfg)
    check_network(rep, cfg)
    check_top_processes(rep)

    verdict = {0: "정상", 1: "주의 항목 있음", 2: "조치 필요"}[rep.worst]
    rep.head("결과")
    rep.add(OK if rep.worst == 0 else WARN if rep.worst == 1 else CRIT, "종합", verdict)

    path = write_log(cfg, rep.text())
    if path and not args.quiet:
        print(f"\n로그: {path}")

    sys.exit(rep.worst)


if __name__ == "__main__":
    main()
