#!/usr/bin/env python3
"""Safe Python server runtime upgrade planner and precheck.

This tool never installs packages, replaces interpreters, edits services, or restarts
production workloads. It inventories the current runtime, validates repository Python
sources, checks the requested target series, and generates upgrade/rollback evidence.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent


def configure_utf8() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            try:
                reconfigure(encoding="utf-8")
            except (OSError, ValueError):
                pass


def parse_version(value: str) -> tuple[int, ...]:
    parts = value.strip().lstrip("v").split(".")
    if len(parts) not in (2, 3) or any(not p.isdigit() for p in parts):
        raise ValueError("version must be MAJOR.MINOR or MAJOR.MINOR.PATCH")
    return tuple(int(p) for p in parts)


def version_text(parts: tuple[int, ...]) -> str:
    return ".".join(str(p) for p in parts)


def target_matches(current: tuple[int, int, int], target: tuple[int, ...]) -> bool:
    return current[: len(target)] == target


def compare_series(current: tuple[int, int, int], target: tuple[int, ...]) -> str:
    current_series = current[:2]
    target_series = target[:2]
    if target_series > current_series:
        return "UPGRADE"
    if target_series < current_series:
        return "DOWNGRADE"
    if len(target) == 3:
        if target[2] > current[2]:
            return "PATCH_UPGRADE"
        if target[2] < current[2]:
            return "PATCH_DOWNGRADE"
    return "CURRENT"


def tracked_python_files(root: Path) -> list[Path]:
    proc = subprocess.run(["git", "ls-files", "-z", "*.py"], cwd=root, capture_output=True)
    if proc.returncode == 0:
        return [root / raw.decode("utf-8") for raw in proc.stdout.split(b"\0") if raw]
    return sorted(root.rglob("*.py"))


def compile_sources(root: Path) -> dict[str, Any]:
    failures: list[dict[str, str]] = []
    files = tracked_python_files(root)
    for path in files:
        rel = path.relative_to(root).as_posix()
        try:
            source = path.read_text(encoding="utf-8")
            compile(source, rel, "exec")
        except (OSError, UnicodeDecodeError, SyntaxError) as exc:
            failures.append({"path": rel, "error": str(exc)})
    return {"count": len(files), "failures": failures, "status": "PASS" if not failures else "FAIL"}


def command_result(command: list[str], timeout: int = 20) -> dict[str, Any]:
    try:
        proc = subprocess.run(command, text=True, capture_output=True, timeout=timeout)
        return {
            "command": command,
            "exit_code": proc.returncode,
            "stdout": proc.stdout.strip(),
            "stderr": proc.stderr.strip(),
            "status": "PASS" if proc.returncode == 0 else "WARN",
        }
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"command": command, "exit_code": None, "stdout": "", "stderr": str(exc), "status": "WARN"}


def disk_free_mb(path: Path) -> int:
    return int(shutil.disk_usage(path).free / (1024 * 1024))


def os_release() -> str:
    if os.name == "nt":
        return platform.platform()
    path = Path("/etc/os-release")
    if path.is_file():
        values: dict[str, str] = {}
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            if "=" in line:
                key, value = line.split("=", 1)
                values[key] = value.strip().strip('"')
        return values.get("PRETTY_NAME") or values.get("NAME") or platform.platform()
    return platform.platform()


def executable_probe(name: str) -> dict[str, Any]:
    path = shutil.which(name)
    if not path:
        return {"requested": name, "path": None, "version": None, "status": "NOT_INSTALLED"}
    result = command_result([path, "--version"])
    text = result["stdout"] or result["stderr"]
    return {"requested": name, "path": path, "version": text, "status": "AVAILABLE" if result["exit_code"] == 0 else "ERROR"}


def build_steps(target: str, target_executable: str, service: str | None) -> tuple[list[str], list[str]]:
    service_text = service or "<service-name>"
    if os.name == "nt":
        upgrade = [
            "1. 현재 Python 경로, 서비스 실행 계정, 가상환경, requirements를 백업/기록",
            f"2. Python {target} 계열을 기존 런타임과 side-by-side로 설치",
            f"3. `{target_executable} --version`으로 목표 런타임 확인",
            f"4. `{target_executable} -m venv <new-venv>`로 신규 가상환경 생성",
            "5. 신규 venv에서 의존성 설치 후 `python -m pip check` 수행",
            "6. `python -m compileall -q .` 및 unittest/functional 검증",
            f"7. Windows Service `{service_text}`의 Python/venv 경로를 승인 절차 후 전환",
            "8. 서비스 상태·로그·배치·SLA 지표를 관찰 후 변경 완료 판정",
        ]
        rollback = [
            f"1. Windows Service `{service_text}`를 이전 Python/venv 경로로 되돌림",
            "2. 이전 서비스 설정과 환경변수를 복원",
            "3. 서비스 시작 후 Health Check/로그/배치 정상 여부 확인",
            "4. 신규 런타임은 즉시 삭제하지 않고 원인분석 완료 후 정리",
        ]
    else:
        upgrade = [
            "1. 현재 Python 경로, systemd ExecStart, 가상환경, requirements를 백업/기록",
            f"2. Python {target} 계열을 기존 런타임과 side-by-side로 설치",
            f"3. `{target_executable} --version`으로 목표 런타임 확인",
            f"4. `{target_executable} -m venv <new-venv>`로 신규 가상환경 생성",
            "5. 신규 venv에서 의존성 설치 후 `python -m pip check` 수행",
            "6. `python -m compileall -q .` 및 unittest/functional 검증",
            f"7. systemd `{service_text}`의 ExecStart를 승인 절차 후 신규 venv로 전환하고 daemon-reload",
            "8. 서비스 상태·journal·배치·SLA 지표를 관찰 후 변경 완료 판정",
        ]
        rollback = [
            f"1. systemd `{service_text}` ExecStart를 이전 Python/venv 경로로 복원",
            "2. daemon-reload 후 이전 서비스 구성으로 재기동",
            "3. Health Check/로그/배치 정상 여부 확인",
            "4. 신규 런타임은 원인분석 완료 전까지 제거하지 않음",
        ]
    return upgrade, rollback


def evaluate(target_value: str, target_executable: str, min_free_mb: int, service: str | None) -> dict[str, Any]:
    target = parse_version(target_value)
    current = (sys.version_info.major, sys.version_info.minor, sys.version_info.micro)
    source = compile_sources(ROOT)
    free_mb = disk_free_mb(ROOT)
    probe = executable_probe(target_executable)
    direction = compare_series(current, target)

    blockers: list[str] = []
    warnings: list[str] = []
    if target[0] != 3:
        blockers.append("지원 정책상 Python 3 계열만 허용합니다.")
    if direction in {"DOWNGRADE", "PATCH_DOWNGRADE"}:
        blockers.append("목표 버전이 현재 런타임보다 낮습니다. downgrade는 별도 변경 승인이 필요합니다.")
    if source["status"] != "PASS":
        blockers.append("저장소 Python source compile precheck가 실패했습니다.")
    if free_mb < min_free_mb:
        blockers.append(f"가용 디스크 {free_mb}MB가 최소 기준 {min_free_mb}MB보다 작습니다.")
    if probe["status"] != "AVAILABLE":
        warnings.append("목표 Python 실행파일이 현재 서버에 없습니다. side-by-side 설치 후 strict precheck를 다시 수행하십시오.")
    if direction == "UPGRADE":
        warnings.append("minor feature upgrade이므로 표준 라이브러리 변경·deprecated API·C extension 호환성을 반드시 재검증해야 합니다.")

    upgrade_steps, rollback_steps = build_steps(version_text(target), target_executable, service)
    status = "BLOCKED" if blockers else ("READY" if probe["status"] == "AVAILABLE" else "PLAN_READY")
    return {
        "status": status,
        "safe_mode": True,
        "changes_applied": False,
        "current": {
            "version": platform.python_version(),
            "executable": sys.executable,
            "implementation": platform.python_implementation(),
            "virtualenv": sys.prefix != getattr(sys, "base_prefix", sys.prefix),
        },
        "target": {"requested": target_value, "series": ".".join(map(str, target[:2])), "executable": probe},
        "direction": direction,
        "platform": {"system": platform.system(), "release": os_release(), "architecture": platform.machine()},
        "prechecks": {
            "source_compile": source,
            "disk_free_mb": free_mb,
            "minimum_free_mb": min_free_mb,
            "pip_check_current": command_result([sys.executable, "-m", "pip", "check"]),
        },
        "blockers": blockers,
        "warnings": warnings,
        "upgrade_steps": upgrade_steps,
        "rollback_steps": rollback_steps,
    }


def render_markdown(result: dict[str, Any]) -> str:
    current = result["current"]
    target = result["target"]
    lines = [
        "# Python Server Upgrade Readiness",
        "",
        "> 이 도구는 **계획/사전검증 전용**이며 Python 설치, 서비스 설정 변경, 재기동을 수행하지 않습니다.",
        "",
        "## 판정",
        "",
        f"- 상태: **{result['status']}**",
        f"- 현재 Python: **{current['version']}**",
        f"- 목표 Python: **{target['requested']}**",
        f"- 변경 방향: **{result['direction']}**",
        f"- 목표 실행파일: **{target['executable']['status']}**",
        f"- Source compile: **{result['prechecks']['source_compile']['status']}** ({result['prechecks']['source_compile']['count']} files)",
        f"- 가용 디스크: **{result['prechecks']['disk_free_mb']} MB**",
        f"- 실제 변경 수행: **아니오**",
        "",
        "## Blockers",
        "",
    ]
    lines += [f"- {x}" for x in result["blockers"]] or ["- 없음"]
    lines += ["", "## Warnings", ""]
    lines += [f"- {x}" for x in result["warnings"]] or ["- 없음"]
    lines += ["", "## Upgrade Plan", ""] + [f"- {x}" for x in result["upgrade_steps"]]
    lines += ["", "## Rollback Plan", ""] + [f"- {x}" for x in result["rollback_steps"]]
    lines += ["", "## 안전 원칙", "", "- 기존 Python을 덮어쓰지 않고 side-by-side 설치를 전제로 합니다.", "- 신규 venv에서 검증 후 서비스 경로만 승인 절차에 따라 전환합니다.", "- Post Check 실패 시 즉시 이전 런타임/venv 경로로 rollback합니다.", "- 이 저장소의 CI에서는 실제 서버 Python 설치/삭제/서비스 재기동을 절대 수행하지 않습니다.", ""]
    return "\n".join(lines)


def main() -> int:
    configure_utf8()
    parser = argparse.ArgumentParser(description="Python 서버 런타임 업그레이드 사전점검/계획 생성기")
    parser.add_argument("--target", required=True, help="목표 Python 버전/계열 (예: 3.14 또는 3.14.7)")
    parser.add_argument("--target-executable", default=None, help="목표 Python 명령 (기본: pythonMAJOR.MINOR)")
    parser.add_argument("--service", default=None, help="전환 대상 서비스 이름(계획 표시용, 실제 변경하지 않음)")
    parser.add_argument("--min-free-mb", type=int, default=512)
    parser.add_argument("--strict-target-installed", action="store_true", help="목표 실행파일이 없으면 BLOCKED 처리")
    parser.add_argument("--report", default="python-upgrade-report.md")
    parser.add_argument("--json-report", default="python-upgrade-report.json")
    args = parser.parse_args()

    try:
        target = parse_version(args.target)
    except ValueError as exc:
        parser.error(str(exc))
    target_executable = args.target_executable or f"python{target[0]}.{target[1]}"
    result = evaluate(args.target, target_executable, args.min_free_mb, args.service)
    if args.strict_target_installed and result["target"]["executable"]["status"] != "AVAILABLE":
        result["blockers"].append("strict mode: 목표 Python 실행파일을 찾을 수 없습니다.")
        result["status"] = "BLOCKED"

    (ROOT / args.report).write_text(render_markdown(result), encoding="utf-8")
    (ROOT / args.json_report).write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        f"Python 업그레이드 점검: current={result['current']['version']} target={args.target} "
        f"compile={result['prechecks']['source_compile']['status']} status={result['status']} changes_applied=false"
    )
    return 2 if result["status"] == "BLOCKED" else 0


if __name__ == "__main__":
    raise SystemExit(main())
