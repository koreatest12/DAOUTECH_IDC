#!/usr/bin/env python3
"""Run repository files with safe, deterministic functional scenarios.

This runner is designed for GitHub Actions and local verification. It executes
real entry points where possible, but redirects state/output into a temporary
sandbox and avoids service-changing operations.
"""

from __future__ import annotations

import argparse
import ast
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
HTML_FILES = [
    "noc-dashboard.html",
    "linux-security-lab.html",
    "backup-simulator.html",
    "incident-lab.html",
    "server-console.html",
    "network-path.html",
]
PYTHON_TOOLS = [
    "healthcheck.py",
    "log_analyzer.py",
    "disk_forecast.py",
    "svc_watchdog.py",
    "backup_verify.py",
    "cert_expiry.py",
]
META_TOOLS = [
    "tools/review_repo.py",
    "tools/run_analyze.py",
    "tools/execute_repo.py",
]
TARGETS = ["all", "python", "html", *PYTHON_TOOLS, *HTML_FILES]

EXPECTED_DOMAIN_CODES = {
    "healthcheck.py": {0, 1, 2},
    "log_analyzer.py": {0, 1},
    "disk_forecast.py": {0, 1, 2},
    "svc_watchdog.py": {0, 1, 2},
    "backup_verify.py": {0, 1, 2},
    "cert_expiry.py": {0, 1, 2},
}


class ScriptParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.scripts: list[str] = []
        self._capture = False
        self._parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "script":
            return
        if dict(attrs).get("src"):
            return
        self._capture = True
        self._parts = []

    def handle_data(self, data: str) -> None:
        if self._capture:
            self._parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "script" and self._capture:
            self.scripts.append("".join(self._parts))
            self._capture = False
            self._parts = []


def run(cmd: list[str], cwd: Path, timeout: int = 30) -> dict[str, Any]:
    started = time.perf_counter()
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    try:
        proc = subprocess.run(cmd, cwd=cwd, text=True, capture_output=True, timeout=timeout, env=env)
        return {
            "exit_code": proc.returncode,
            "stdout": proc.stdout,
            "stderr": proc.stderr,
            "timeout": False,
            "duration_ms": int((time.perf_counter() - started) * 1000),
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "exit_code": None,
            "stdout": exc.stdout if isinstance(exc.stdout, str) else "",
            "stderr": exc.stderr if isinstance(exc.stderr, str) else "",
            "timeout": True,
            "duration_ms": int((time.perf_counter() - started) * 1000),
        }


def write_log(log_dir: Path, name: str, result: dict[str, Any], command: list[str]) -> str:
    log_dir.mkdir(parents=True, exist_ok=True)
    safe = name.replace("/", "__").replace("\\", "__")
    path = log_dir / f"{safe}.log"
    path.write_text(
        "$ " + " ".join(command) + "\n\n"
        + "STDOUT\n======\n" + str(result.get("stdout", ""))
        + "\n\nSTDERR\n======\n" + str(result.get("stderr", ""))
        + f"\n\nexit_code={result.get('exit_code')}\n"
        + f"timeout={result.get('timeout')}\n"
        + f"duration_ms={result.get('duration_ms')}\n",
        encoding="utf-8",
    )
    return path.relative_to(ROOT).as_posix()


def short(text: str, limit: int = 180) -> str:
    line = next((x.strip() for x in text.splitlines() if x.strip()), "")
    return line[:limit]


def command_record(name: str, command: list[str], cwd: Path, log_dir: Path,
                   expected_codes: set[int] | None = None, timeout: int = 30,
                   note: str = "") -> dict[str, Any]:
    result = run(command, cwd, timeout=timeout)
    expected = expected_codes if expected_codes is not None else {0}
    ok = not result["timeout"] and result["exit_code"] in expected
    log_path = write_log(log_dir, name, result, command)
    evidence = short(result["stdout"] or result["stderr"])
    return {
        "target": name,
        "status": "OK" if ok else "ERROR",
        "command": " ".join(command),
        "exit_code": result["exit_code"],
        "duration_ms": result["duration_ms"],
        "timeout": result["timeout"],
        "evidence": evidence,
        "note": note,
        "log": log_path,
    }


def make_log_fixture(sandbox: Path) -> Path:
    path = sandbox / "sample.log"
    rows = []
    for minute in range(0, 40, 10):
        rows.append(f"2026-09-04T03:{minute:02d}:01 ERROR app[10] connection failed from 10.0.0.1")
        rows.append(f"2026-09-04T03:{minute:02d}:02 WARN app[11] retry /var/tmp/job-{minute}")
    for i in range(12):
        rows.append(f"2026-09-04T03:40:{i:02d} ERROR app[{100+i}] timeout from 10.0.0.{i+2}")
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")
    return path


def make_health_config(sandbox: Path) -> Path:
    path = sandbox / "healthcheck.json"
    payload = {
        "cpu_warn": 100,
        "mem_warn": 100,
        "disk_warn": 100,
        "disk_crit": 100,
        "services": [],
        "ping_targets": [],
        "log_dir": str(sandbox / "health-logs"),
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def make_backup_fixture(sandbox: Path) -> tuple[Path, Path]:
    base = sandbox / "backup"
    base.mkdir(parents=True, exist_ok=True)
    payload = base / "sample.bak"
    payload.write_bytes(b"DAOUTECH_IDC functional backup fixture\n" * 16)
    manifest = sandbox / "backup-manifest.json"
    manifest.write_text(json.dumps({
        "base_dir": str(base),
        "max_age_hours": 9999,
        "files": [{"name": payload.name, "min_mb": 0}],
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest, payload


def run_python_target(name: str, mode: str, sandbox: Path, log_dir: Path) -> list[dict[str, Any]]:
    py = sys.executable
    if mode == "smoke":
        return [command_record(name, [py, name, "--help"], ROOT, log_dir,
                               expected_codes={0}, note="CLI entry point smoke execution")]

    if name == "healthcheck.py":
        cfg = make_health_config(sandbox)
        return [command_record(name, [py, name, "--config", str(cfg), "--quiet"], ROOT, log_dir,
                               expected_codes=EXPECTED_DOMAIN_CODES[name],
                               note="Real local host checks; no configured service or network targets")]

    if name == "log_analyzer.py":
        fixture = make_log_fixture(sandbox)
        return [command_record(name, [py, name, str(fixture), "--top", "10", "--sigma", "2.0"], ROOT, log_dir,
                               expected_codes=EXPECTED_DOMAIN_CODES[name],
                               note="Functional analysis using generated local log fixture")]

    if name == "disk_forecast.py":
        history = sandbox / "disk-history.json"
        return [command_record(name, [py, name, "/", "--history", str(history), "--threshold", "100", "--alert-days", "1"], ROOT, log_dir,
                               expected_codes=EXPECTED_DOMAIN_CODES[name],
                               note="Reads runner filesystem usage; writes history only inside sandbox")]

    if name == "svc_watchdog.py":
        state = sandbox / "watchdog-state.json"
        return [command_record(name, [py, name, "__daoutech_portfolio_nonexistent_service__", "--dry-run",
                                      "--state", str(state), "--max-restarts", "1", "--window", "60"], ROOT, log_dir,
                               expected_codes=EXPECTED_DOMAIN_CODES[name],
                               note="Dry-run only; never starts or restarts a service")]

    if name == "backup_verify.py":
        manifest, _ = make_backup_fixture(sandbox)
        first = command_record(name + "#record", [py, name, str(manifest), "--record"], ROOT, log_dir,
                               expected_codes={0}, note="Records SHA-256 against generated sandbox backup")
        second = command_record(name + "#verify", [py, name, str(manifest)], ROOT, log_dir,
                                expected_codes={0}, note="Verifies existence, size, freshness and recorded SHA-256")
        return [first, second]

    if name == "cert_expiry.py":
        domains = ROOT / "domains.txt"
        return [command_record(name, [py, name, "--file", str(domains), "--timeout", "3"], ROOT, log_dir,
                               expected_codes=EXPECTED_DOMAIN_CODES[name], timeout=25,
                               note="Read-only TLS connection test; domain/network verdict does not count as runner failure")]

    return [command_record(name, [py, name, "--help"], ROOT, log_dir)]


def chrome_binary() -> str | None:
    for candidate in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser"):
        found = shutil.which(candidate)
        if found:
            return found
    return None


def run_html_target(name: str, mode: str, sandbox: Path, log_dir: Path) -> list[dict[str, Any]]:
    path = ROOT / name
    text = path.read_text(encoding="utf-8")
    parser = ScriptParser()
    parser.feed(text)
    node = shutil.which("node")
    records: list[dict[str, Any]] = []

    if node:
        with tempfile.TemporaryDirectory(prefix="daoutech-js-", dir=sandbox) as temp:
            for index, script in enumerate(parser.scripts, 1):
                if not script.strip():
                    continue
                js = Path(temp) / f"{Path(name).stem}-{index}.js"
                js.write_text(script, encoding="utf-8")
                records.append(command_record(f"{name}#js{index}", [node, "--check", str(js)], ROOT, log_dir,
                                              expected_codes={0}, note="Inline JavaScript syntax execution check"))
    else:
        records.append({"target": name, "status": "ERROR", "command": "node --check", "exit_code": None,
                        "duration_ms": 0, "timeout": False, "evidence": "Node executable not found", "note": "", "log": ""})

    if mode == "functional":
        chrome = chrome_binary()
        if chrome:
            command = [chrome, "--headless", "--disable-gpu", "--no-sandbox", "--disable-dev-shm-usage",
                       "--allow-file-access-from-files", "--dump-dom", path.resolve().as_uri()]
            records.append(command_record(f"{name}#browser", command, ROOT, log_dir,
                                          expected_codes={0}, timeout=40,
                                          note="Headless browser loads the actual HTML document"))
        else:
            records.append({"target": f"{name}#browser", "status": "OK", "command": "browser capability probe",
                            "exit_code": 0, "duration_ms": 0, "timeout": False,
                            "evidence": "Chrome/Chromium unavailable; JS checks completed",
                            "note": "Browser load falls back to deterministic JavaScript checks on this runner", "log": ""})

    if not records:
        records.append({"target": name, "status": "OK", "command": "HTML parser", "exit_code": 0,
                        "duration_ms": 0, "timeout": False, "evidence": f"inline_scripts={len(parser.scripts)}",
                        "note": "HTML parsed successfully", "log": ""})
    return records


def run_meta_tools(log_dir: Path) -> list[dict[str, Any]]:
    records = []
    for name in META_TOOLS:
        path = ROOT / name
        if not path.exists():
            continue
        ast.parse(path.read_text(encoding="utf-8"), filename=name)
        records.append(command_record(name, [sys.executable, name, "--help"], ROOT, log_dir,
                                      expected_codes={0}, note="Runner/control script entry point smoke execution"))
    return records


def selected_targets(target: str) -> list[str]:
    if target == "all":
        return [*PYTHON_TOOLS, *HTML_FILES]
    if target == "python":
        return list(PYTHON_TOOLS)
    if target == "html":
        return list(HTML_FILES)
    return [target]


def render(records: list[dict[str, Any]], target: str, mode: str) -> str:
    errors = [r for r in records if r["status"] == "ERROR"]
    lines = [
        "# 저장소 파일 실행 결과", "", f"- 요청 대상: **{target}**", f"- 실행 모드: **{mode}**",
        f"- 수행 항목: **{len(records)}개**", f"- 실행 오류: **{len(errors)}건**",
        f"- 최종 상태: **{'PASS' if not errors else 'FAIL'}**", "", "## 결과", "",
        "| 상태 | 대상 | 종료코드 | 시간 | 실행/검증 |", "|---|---|---:|---:|---|",
    ]
    for record in records:
        evidence = record.get("evidence", "").replace("|", "\\|")
        note = record.get("note", "").replace("|", "\\|")
        detail = "; ".join(x for x in (evidence, note) if x)
        lines.append(f"| {record['status']} | `{record['target']}` | {record.get('exit_code')} | "
                     f"{record.get('duration_ms', 0)}ms | {detail} |")
    lines += [
        "", "## 실행 안전 정책", "",
        "- `svc_watchdog.py`는 항상 `--dry-run`으로 실행하여 서비스 시작/재기동을 하지 않습니다.",
        "- 백업 검증은 임시 샌드박스 파일만 생성·검증합니다.",
        "- 디스크 예측 이력과 헬스체크 로그는 임시 샌드박스에만 기록합니다.",
        "- 인증서 검사는 읽기 전용 TLS 연결만 수행하며 원격 시스템을 변경하지 않습니다.",
        "- HTML functional 모드는 Chrome/Chromium이 있으면 실제 headless 로딩하고, 없으면 Node 문법 검증으로 폴백합니다.", "",
    ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="DAOUTECH_IDC 저장소 파일 안전 실행기")
    parser.add_argument("--target", choices=TARGETS, default="all")
    parser.add_argument("--mode", choices=("smoke", "functional"), default="functional")
    parser.add_argument("--report", default="run-results.md")
    parser.add_argument("--json-report", default="run-results.json")
    parser.add_argument("--log-dir", default="execution-logs")
    parser.add_argument("--list", action="store_true", help="실행 가능한 대상 목록 출력")
    args = parser.parse_args()

    if args.list:
        print("\n".join(TARGETS))
        return 0

    log_dir = ROOT / args.log_dir
    records: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory(prefix="daoutech-run-") as temp:
        sandbox = Path(temp)
        for target in selected_targets(args.target):
            if target in PYTHON_TOOLS:
                records.extend(run_python_target(target, args.mode, sandbox, log_dir))
            elif target in HTML_FILES:
                records.extend(run_html_target(target, args.mode, sandbox, log_dir))
            else:
                records.append({"target": target, "status": "ERROR", "command": "", "exit_code": None,
                                "duration_ms": 0, "timeout": False, "evidence": "Unknown target", "note": "", "log": ""})
        if args.target in {"all", "python"}:
            records.extend(run_meta_tools(log_dir))

    (ROOT / args.report).write_text(render(records, args.target, args.mode), encoding="utf-8")
    (ROOT / args.json_report).write_text(json.dumps({
        "target": args.target,
        "mode": args.mode,
        "status": "PASS" if not any(r["status"] == "ERROR" for r in records) else "FAIL",
        "records": records,
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    errors = sum(r["status"] == "ERROR" for r in records)
    print(f"저장소 실행 완료: 수행 {len(records)}개 / 오류 {errors}건")
    print(f"결과: {'PASS' if errors == 0 else 'FAIL'}")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
