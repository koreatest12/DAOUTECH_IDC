#!/usr/bin/env python3
"""Python server/application runtime upgrade manager.

Default mode is read-only precheck and planning. `--apply --confirm APPLY` performs a
real managed application-runtime cutover: it requires a side-by-side target Python,
creates an immutable venv release, runs compile/unit/functional/scenario validation,
then atomically switches a stable runtime pointer. The OS/system Python interpreter is
never overwritten or deleted. `--rollback --confirm ROLLBACK` restores the previous
managed runtime pointer.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
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
    return {
        "count": len(files),
        "failures": failures,
        "status": "PASS" if not failures else "FAIL",
    }


def command_result(
    command: list[str],
    timeout: int = 60,
    cwd: Path | None = None,
    pass_codes: set[int] | None = None,
) -> dict[str, Any]:
    pass_codes = pass_codes or {0}
    started = time.perf_counter()
    try:
        proc = subprocess.run(
            command,
            cwd=cwd or ROOT,
            text=True,
            capture_output=True,
            timeout=timeout,
        )
        return {
            "command": command,
            "exit_code": proc.returncode,
            "stdout": proc.stdout.strip(),
            "stderr": proc.stderr.strip(),
            "status": "PASS" if proc.returncode in pass_codes else "FAIL",
            "duration_ms": int((time.perf_counter() - started) * 1000),
        }
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {
            "command": command,
            "exit_code": None,
            "stdout": "",
            "stderr": str(exc),
            "status": "FAIL",
            "duration_ms": int((time.perf_counter() - started) * 1000),
        }


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
    candidate = Path(name).expanduser()
    if candidate.is_file():
        path = str(candidate.resolve())
    else:
        path = shutil.which(name)
    if not path:
        return {
            "requested": name,
            "path": None,
            "version": None,
            "version_tuple": None,
            "status": "NOT_INSTALLED",
        }

    result = command_result([path, "--version"], timeout=20)
    text = result["stdout"] or result["stderr"]
    parsed: tuple[int, ...] | None = None
    if result["status"] == "PASS":
        chunks = text.split()
        if len(chunks) >= 2:
            try:
                parsed = parse_version(chunks[1])
            except ValueError:
                parsed = None
    return {
        "requested": name,
        "path": path,
        "version": text,
        "version_tuple": list(parsed) if parsed else None,
        "status": "AVAILABLE" if result["status"] == "PASS" and parsed else "ERROR",
    }


def build_steps(target: str, target_executable: str, service: str | None) -> tuple[list[str], list[str]]:
    service_text = service or "<service-name>"
    upgrade = [
        "1. 현재 Python 경로, 서비스 실행 계정, 가상환경, requirements를 백업/기록",
        f"2. Python {target}을 기존 시스템 Python과 side-by-side로 준비",
        f"3. `{target_executable} --version`으로 목표 런타임 확인",
        "4. immutable release 디렉터리에 신규 venv 생성",
        "5. 신규 venv에서 requirements 설치 및 `python -m pip check` 수행",
        "6. compileall, unittest, functional, scenario 회귀검증 수행",
        "7. 검증 성공 후 stable runtime pointer(`current.json` + launcher)를 신규 venv로 원자적 전환",
        f"8. 서비스 `{service_text}`가 stable launcher를 사용한다면 신규 runtime으로 기동/관찰",
        "9. Post Check 실패 시 이전 runtime pointer로 즉시 rollback",
    ]
    rollback = [
        "1. 저장된 `previous.json`의 이전 Python/venv 경로 확인",
        "2. stable runtime pointer와 launcher를 이전 실행파일로 원자적 복원",
        f"3. 서비스 `{service_text}`가 stable launcher를 사용한다면 이전 runtime으로 재기동",
        "4. Health Check/로그/배치/SLA 정상 여부 확인",
        "5. 실패한 신규 runtime은 원인분석 전까지 보존하고 임의 삭제하지 않음",
    ]
    return upgrade, rollback


def evaluate(
    target_value: str,
    target_executable: str,
    min_free_mb: int,
    service: str | None,
) -> dict[str, Any]:
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
        warnings.append(
            "목표 Python 실행파일이 현재 서버에 없습니다. side-by-side 설치 후 strict precheck를 다시 수행하십시오."
        )
    elif probe["version_tuple"]:
        actual = tuple(int(x) for x in probe["version_tuple"])
        if not target_matches(actual, target):
            blockers.append(
                f"목표 실행파일 버전 {version_text(actual)}이 요청 버전 {target_value}과 일치하지 않습니다."
            )

    if direction == "UPGRADE":
        warnings.append(
            "minor feature upgrade이므로 표준 라이브러리 변경·deprecated API·C extension 호환성을 반드시 재검증해야 합니다."
        )

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
        "target": {
            "requested": target_value,
            "series": ".".join(map(str, target[:2])),
            "executable": probe,
        },
        "direction": direction,
        "platform": {
            "system": platform.system(),
            "release": os_release(),
            "architecture": platform.machine(),
        },
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


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def safe_runtime_root(value: str) -> Path:
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = ROOT / path
    path = path.resolve()
    if path == ROOT or path.parent == path:
        raise ValueError("runtime root must be a dedicated directory")
    return path


def runtime_python_path(venv_dir: Path) -> Path:
    return venv_dir / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def requirements_have_packages(path: Path) -> bool:
    if not path.is_file():
        return False
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        text = line.strip()
        if text and not text.startswith("#"):
            return True
    return False


def read_json(path: Path) -> dict[str, Any] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else None
    except (OSError, json.JSONDecodeError):
        return None


def write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temp, path)


def pointer_payload(
    version: str,
    executable: str,
    *,
    managed: bool,
    release_dir: str | None,
) -> dict[str, Any]:
    return {
        "version": version,
        "executable": executable,
        "managed": managed,
        "release_dir": release_dir,
        "updated_at": now_utc(),
    }


def write_launcher(runtime_root: Path, executable: str) -> str:
    runtime_root.mkdir(parents=True, exist_ok=True)
    if os.name == "nt":
        launcher = runtime_root / "current-python.cmd"
        temp = runtime_root / ".current-python.cmd.tmp"
        temp.write_text(f'@"{executable}" %*\r\n', encoding="utf-8")
        os.replace(temp, launcher)
        return str(launcher)

    launcher = runtime_root / "current-python"
    temp = runtime_root / ".current-python.tmp"
    try:
        temp.unlink()
    except FileNotFoundError:
        pass
    os.symlink(executable, temp)
    os.replace(temp, launcher)
    return str(launcher)


def switch_pointer(runtime_root: Path, new_pointer: dict[str, Any]) -> dict[str, Any]:
    current_path = runtime_root / "current.json"
    previous_path = runtime_root / "previous.json"
    previous = read_json(current_path)
    if not previous:
        previous = pointer_payload(
            platform.python_version(),
            sys.executable,
            managed=False,
            release_dir=None,
        )
    write_json_atomic(previous_path, previous)
    write_json_atomic(current_path, new_pointer)
    write_launcher(runtime_root, str(new_pointer["executable"]))
    return previous


def rollback_runtime(runtime_root: Path) -> dict[str, Any]:
    current_path = runtime_root / "current.json"
    previous_path = runtime_root / "previous.json"
    current = read_json(current_path)
    previous = read_json(previous_path)
    if not previous:
        return {
            "status": "BLOCKED",
            "changes_applied": False,
            "message": "previous.json이 없어 rollback할 runtime이 없습니다.",
        }

    write_json_atomic(current_path, previous)
    write_launcher(runtime_root, str(previous["executable"]))
    if current:
        write_json_atomic(previous_path, current)
    return {
        "status": "ROLLED_BACK",
        "changes_applied": True,
        "current": previous,
        "previous": current,
        "message": f"runtime pointer를 Python {previous.get('version')}로 복원했습니다.",
    }


def validation_suite(
    python: Path,
    runtime_root: Path,
    requirements: Path,
) -> list[dict[str, Any]]:
    evidence = runtime_root / "evidence"
    evidence.mkdir(parents=True, exist_ok=True)
    checks: list[dict[str, Any]] = []

    if requirements_have_packages(requirements):
        checks.append(
            command_result(
                [str(python), "-m", "pip", "install", "-r", str(requirements)],
                timeout=300,
            )
        )
    else:
        checks.append(
            {
                "command": [str(python), "-m", "pip", "install", "-r", str(requirements)],
                "exit_code": 0,
                "stdout": "requirements.txt에 설치할 외부 패키지가 없어 install을 생략했습니다.",
                "stderr": "",
                "status": "PASS",
                "duration_ms": 0,
            }
        )

    checks.extend(
        [
            command_result([str(python), "-m", "pip", "check"], timeout=60),
            command_result([str(python), "-m", "compileall", "-q", "."], timeout=120),
            command_result(
                [str(python), "-m", "unittest", "discover", "-s", "tests", "-p", "test_*.py", "-v"],
                timeout=180,
            ),
            command_result(
                [
                    str(python),
                    "scenario_runner.py",
                    "scenarios",
                    "--report",
                    str(evidence / "scenario-report.md"),
                    "--json-report",
                    str(evidence / "scenario-report.json"),
                ],
                timeout=120,
            ),
            command_result(
                [
                    str(python),
                    "tools/execute_repo.py",
                    "--target",
                    "all",
                    "--mode",
                    "functional",
                    "--report",
                    str(evidence / "functional-run.md"),
                    "--json-report",
                    str(evidence / "functional-run.json"),
                    "--log-dir",
                    str(evidence / "functional-logs"),
                ],
                timeout=300,
            ),
        ]
    )
    return checks


def apply_runtime(
    result: dict[str, Any],
    runtime_root_value: str,
    requirements_value: str,
) -> dict[str, Any]:
    result["safe_mode"] = False
    result["apply"] = {"requested": True, "started_at": now_utc()}

    if result["blockers"]:
        result["status"] = "BLOCKED"
        return result

    probe = result["target"]["executable"]
    requested = parse_version(str(result["target"]["requested"]))
    if len(requested) != 3:
        result["blockers"].append("실제 적용은 MAJOR.MINOR.PATCH 정확한 버전(예: 3.14.7)이 필요합니다.")
        result["status"] = "BLOCKED"
        return result
    if probe["status"] != "AVAILABLE" or not probe["path"] or not probe["version_tuple"]:
        result["blockers"].append("실제 적용에는 설치된 목표 Python 실행파일이 필요합니다.")
        result["status"] = "BLOCKED"
        return result

    actual = tuple(int(x) for x in probe["version_tuple"])
    if actual != requested:
        result["blockers"].append(
            f"실제 적용 target mismatch: requested={version_text(requested)} actual={version_text(actual)}"
        )
        result["status"] = "BLOCKED"
        return result

    runtime_root = safe_runtime_root(runtime_root_value)
    requirements = Path(requirements_value)
    if not requirements.is_absolute():
        requirements = ROOT / requirements
    requirements = requirements.resolve()

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    release_dir = runtime_root / "releases" / f"python-{version_text(actual)}-{stamp}"
    venv_dir = release_dir / "venv"
    release_dir.mkdir(parents=True, exist_ok=False)

    create = command_result(
        [str(probe["path"]), "-m", "venv", str(venv_dir)],
        timeout=180,
    )
    result["apply"]["venv_create"] = create
    if create["status"] != "PASS":
        result["status"] = "APPLY_FAILED"
        result["blockers"].append("신규 venv 생성에 실패했습니다.")
        return result

    new_python = runtime_python_path(venv_dir)
    validations = validation_suite(new_python, runtime_root, requirements)
    result["apply"]["validations"] = validations
    failed = [item for item in validations if item["status"] != "PASS"]
    if failed:
        result["status"] = "VALIDATION_FAILED"
        result["blockers"].append(
            f"신규 runtime 검증 {len(failed)}건이 실패하여 stable pointer를 전환하지 않았습니다."
        )
        return result

    new_pointer = pointer_payload(
        version_text(actual),
        str(new_python.resolve()),
        managed=True,
        release_dir=str(release_dir),
    )
    previous = switch_pointer(runtime_root, new_pointer)
    result["apply"]["previous_pointer"] = previous
    result["apply"]["current_pointer"] = new_pointer
    result["apply"]["runtime_root"] = str(runtime_root)
    result["apply"]["launcher"] = str(
        runtime_root / ("current-python.cmd" if os.name == "nt" else "current-python")
    )
    result["changes_applied"] = True

    post = command_result([str(new_python), "--version"], timeout=20)
    result["apply"]["postcheck"] = post
    if post["status"] != "PASS":
        rollback = rollback_runtime(runtime_root)
        result["apply"]["automatic_rollback"] = rollback
        result["status"] = "ROLLED_BACK"
        return result

    result["status"] = "APPLIED"
    result["apply"]["completed_at"] = now_utc()
    return result


def render_markdown(result: dict[str, Any]) -> str:
    current = result.get("current", {})
    target = result.get("target", {})
    target_exec = target.get("executable", {}) if isinstance(target, dict) else {}
    prechecks = result.get("prechecks", {})
    source = prechecks.get("source_compile", {})

    lines = [
        "# Python Server Runtime Upgrade",
        "",
        "## 판정",
        "",
        f"- 상태: **{result.get('status', 'UNKNOWN')}**",
        f"- 현재 Python: **{current.get('version', '—')}**",
        f"- 목표 Python: **{target.get('requested', '—') if isinstance(target, dict) else '—'}**",
        f"- 변경 방향: **{result.get('direction', '—')}**",
        f"- 목표 실행파일: **{target_exec.get('status', '—')}**",
        f"- Source compile: **{source.get('status', '—')}** ({source.get('count', 0)} files)",
        f"- 가용 디스크: **{prechecks.get('disk_free_mb', '—')} MB**",
        f"- 실제 managed runtime 변경: **{'예' if result.get('changes_applied') else '아니오'}**",
        "",
        "## Blockers",
        "",
    ]
    lines += [f"- {x}" for x in result.get("blockers", [])] or ["- 없음"]
    lines += ["", "## Warnings", ""]
    lines += [f"- {x}" for x in result.get("warnings", [])] or ["- 없음"]

    apply = result.get("apply")
    if isinstance(apply, dict):
        lines += ["", "## Apply Evidence", ""]
        if apply.get("runtime_root"):
            lines.append(f"- Runtime root: `{apply['runtime_root']}`")
        if apply.get("launcher"):
            lines.append(f"- Stable launcher: `{apply['launcher']}`")
        pointer = apply.get("current_pointer")
        if isinstance(pointer, dict):
            lines.append(
                f"- Current pointer: **Python {pointer.get('version')}** → `{pointer.get('executable')}`"
            )
        validations = apply.get("validations") or []
        if validations:
            passed = sum(item.get("status") == "PASS" for item in validations)
            lines.append(f"- Validation suite: **{passed}/{len(validations)} PASS**")
        if apply.get("automatic_rollback"):
            lines.append(
                f"- Automatic rollback: **{apply['automatic_rollback'].get('status')}**"
            )

    lines += ["", "## Upgrade Plan", ""]
    lines += [f"- {x}" for x in result.get("upgrade_steps", [])]
    lines += ["", "## Rollback Plan", ""]
    lines += [f"- {x}" for x in result.get("rollback_steps", [])]
    lines += [
        "",
        "## 안전 경계",
        "",
        "- OS/system Python(`/usr/bin/python` 또는 Windows 시스템 Python)을 덮어쓰거나 삭제하지 않습니다.",
        "- 목표 Python 인터프리터는 side-by-side로 사전에 설치되어 있어야 합니다.",
        "- 기본 모드는 읽기 전용 precheck입니다.",
        "- `--apply --confirm APPLY`에서만 immutable venv 생성 및 stable runtime pointer를 실제 전환합니다.",
        "- 신규 runtime 검증 실패 시 pointer를 전환하지 않습니다.",
        "- 전환 후 Post Check 실패 시 previous pointer로 자동 rollback합니다.",
        "- systemd/Windows Service 자체 변경·재기동은 이 도구가 자동 수행하지 않습니다.",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    configure_utf8()
    parser = argparse.ArgumentParser(description="Python 서버/애플리케이션 Runtime 업그레이드 관리기")
    parser.add_argument("--target", help="목표 Python 버전/계열 (예: 3.14 또는 3.14.7)")
    parser.add_argument("--target-executable", default=None, help="목표 Python 명령 또는 절대경로")
    parser.add_argument("--service", default=None, help="전환 대상 서비스 이름(계획/증거 표시용)")
    parser.add_argument("--min-free-mb", type=int, default=512)
    parser.add_argument("--strict-target-installed", action="store_true")
    parser.add_argument("--apply", action="store_true", help="managed application runtime 실제 전환")
    parser.add_argument("--rollback", action="store_true", help="previous runtime pointer로 rollback")
    parser.add_argument("--confirm", default="", help="실제 적용 시 APPLY, rollback 시 ROLLBACK")
    parser.add_argument("--runtime-root", default=".runtime")
    parser.add_argument("--requirements", default="requirements.txt")
    parser.add_argument("--report", default="python-upgrade-report.md")
    parser.add_argument("--json-report", default="python-upgrade-report.json")
    args = parser.parse_args()

    if args.apply and args.rollback:
        parser.error("--apply와 --rollback은 동시에 사용할 수 없습니다.")

    if args.rollback:
        if args.confirm != "ROLLBACK":
            parser.error("실제 rollback에는 --confirm ROLLBACK이 필요합니다.")
        try:
            root = safe_runtime_root(args.runtime_root)
        except ValueError as exc:
            parser.error(str(exc))
        result = rollback_runtime(root)
        result.update(
            {
                "safe_mode": False,
                "direction": "ROLLBACK",
                "current": {
                    "version": platform.python_version(),
                    "executable": sys.executable,
                },
                "target": {"requested": "previous-runtime", "executable": {}},
                "prechecks": {
                    "source_compile": {"status": "N/A", "count": 0},
                    "disk_free_mb": disk_free_mb(ROOT),
                },
                "blockers": [] if result["status"] == "ROLLED_BACK" else [result.get("message", "rollback failed")],
                "warnings": [],
                "upgrade_steps": [],
                "rollback_steps": [],
            }
        )
    else:
        if not args.target:
            parser.error("--target이 필요합니다.")
        try:
            target = parse_version(args.target)
        except ValueError as exc:
            parser.error(str(exc))
        target_executable = args.target_executable or f"python{target[0]}.{target[1]}"
        result = evaluate(args.target, target_executable, args.min_free_mb, args.service)
        if args.strict_target_installed and result["target"]["executable"]["status"] != "AVAILABLE":
            result["blockers"].append("strict mode: 목표 Python 실행파일을 찾을 수 없습니다.")
            result["status"] = "BLOCKED"
        if args.apply:
            if args.confirm != "APPLY":
                parser.error("실제 적용에는 --confirm APPLY가 필요합니다.")
            try:
                result = apply_runtime(result, args.runtime_root, args.requirements)
            except ValueError as exc:
                parser.error(str(exc))

    (ROOT / args.report).write_text(render_markdown(result), encoding="utf-8")
    (ROOT / args.json_report).write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        f"Python runtime upgrade: current={result.get('current', {}).get('version')} "
        f"target={result.get('target', {}).get('requested')} "
        f"status={result.get('status')} "
        f"changes_applied={str(bool(result.get('changes_applied'))).lower()}"
    )
    return 0 if result.get("status") in {"READY", "PLAN_READY", "APPLIED", "ROLLED_BACK"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
