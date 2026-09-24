#!/usr/bin/env python3
"""Safely execute portfolio tools and HTML simulators with deterministic scenarios."""

from __future__ import annotations

import argparse
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
PYTHON_TOOLS = [
    "healthcheck.py", "log_analyzer.py", "disk_forecast.py", "svc_watchdog.py",
    "backup_verify.py", "cert_expiry.py", "incident_report.py",
    "alert_correlator.py", "capacity_planner.py", "sla_calculator.py",
    "python_server_upgrade.py",
]
HTML_FILES = [
    "index.html", "noc-dashboard.html", "linux-security-lab.html",
    "backup-simulator.html", "incident-lab.html", "server-console.html",
    "network-path.html", "batch-operations-lab.html", "change-management-lab.html",
]
PIPELINE_TOOLS = [
    "tools/review_repo.py", "tools/run_analyze.py", "tools/portfolio_manager.py",
    "tools/summarize_reports.py", "tools/portfolio_report.py", "tools/execute_repo.py",
]
GROUP_TARGETS = ["all", "python", "html", "scenarios", "pipeline", "tests", "data"]
TARGETS = [*GROUP_TARGETS, *PYTHON_TOOLS, *HTML_FILES]
TEXT_DATA_EXTS = {".md", ".txt", ".yml", ".yaml"}
TEXT_DATA_NAMES = {"LICENSE", ".gitignore"}


class ScriptParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.scripts: list[str] = []
        self._capture = False
        self._parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() == "script" and not dict(attrs).get("src"):
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


def run(cmd: list[str], cwd: Path = ROOT, timeout: int = 30) -> dict[str, Any]:
    started = time.perf_counter()
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    try:
        p = subprocess.run(cmd, cwd=cwd, text=True, capture_output=True, timeout=timeout, env=env)
        return {"exit_code": p.returncode, "stdout": p.stdout, "stderr": p.stderr,
                "timeout": False, "duration_ms": int((time.perf_counter()-started)*1000)}
    except subprocess.TimeoutExpired as exc:
        return {"exit_code": None, "stdout": exc.stdout if isinstance(exc.stdout, str) else "",
                "stderr": exc.stderr if isinstance(exc.stderr, str) else "", "timeout": True,
                "duration_ms": int((time.perf_counter()-started)*1000)}


def first_line(text: str) -> str:
    return next((x.strip() for x in text.splitlines() if x.strip()), "")[:180]


def save_log(log_dir: Path, name: str, cmd: list[str], result: dict[str, Any]) -> str:
    log_dir.mkdir(parents=True, exist_ok=True)
    path = log_dir / (name.replace("/", "__").replace("#", "__") + ".log")
    path.write_text(
        "$ " + " ".join(cmd) + "\n\nSTDOUT\n======\n" + result.get("stdout", "") +
        "\n\nSTDERR\n======\n" + result.get("stderr", "") +
        f"\n\nexit_code={result.get('exit_code')} timeout={result.get('timeout')} duration_ms={result.get('duration_ms')}\n",
        encoding="utf-8",
    )
    return path.as_posix()


def record(name: str, cmd: list[str], log_dir: Path, expected: set[int] | None = None,
           note: str = "", timeout: int = 30) -> dict[str, Any]:
    result = run(cmd, timeout=timeout)
    expected = expected or {0}
    ok = not result["timeout"] and result["exit_code"] in expected
    return {
        "target": name, "status": "OK" if ok else "ERROR", "command": " ".join(cmd),
        "exit_code": result["exit_code"], "duration_ms": result["duration_ms"],
        "evidence": first_line(result["stdout"] or result["stderr"]), "note": note,
        "log": save_log(log_dir, name, cmd, result),
    }


def fixture_log(sandbox: Path) -> Path:
    p = sandbox / "sample.log"
    rows = [f"2026-09-04T03:{m:02d}:01 ERROR app[{100+m}] timeout from 10.0.0.{m//10+1}" for m in (0,10,20,30)]
    rows += [f"2026-09-04T03:40:{i:02d} ERROR app[{200+i}] timeout from 10.0.1.{i+1}" for i in range(20)]
    p.write_text("\n".join(rows)+"\n", encoding="utf-8")
    return p


def health_config(sandbox: Path) -> Path:
    p = sandbox / "health.json"
    p.write_text(json.dumps({"cpu_warn":100,"mem_warn":100,"disk_warn":100,"disk_crit":100,
                             "services":[],"ping_targets":[],"log_dir":str(sandbox/"health-logs")}), encoding="utf-8")
    return p


def backup_manifest(sandbox: Path) -> Path:
    base = sandbox / "backup"; base.mkdir(exist_ok=True)
    (base / "sample.bak").write_bytes(b"portfolio-backup-fixture\n" * 32)
    p = sandbox / "backup.json"
    p.write_text(json.dumps({"base_dir":str(base),"max_age_hours":9999,
                             "files":[{"name":"sample.bak","min_mb":0}]}), encoding="utf-8")
    return p


def run_python(name: str, mode: str, sandbox: Path, log_dir: Path) -> list[dict[str, Any]]:
    py = sys.executable
    if mode == "smoke":
        return [record(name, [py, name, "--help"], log_dir, {0}, "CLI entry-point smoke")]
    if name == "healthcheck.py":
        return [record(name, [py,name,"--config",str(health_config(sandbox)),"--quiet"], log_dir,{0,1,2},"Runner local health checks")]
    if name == "log_analyzer.py":
        return [record(name,[py,name,str(fixture_log(sandbox)),"--top","10","--sigma","2.0"],log_dir,{0,1},"Generated local log fixture")]
    if name == "disk_forecast.py":
        return [record(name,[py,name,"/","--history",str(sandbox/"disk.json"),"--threshold","100","--alert-days","1"],log_dir,{0,1,2},"Runner filesystem read; sandbox history")]
    if name == "svc_watchdog.py":
        return [record(name,[py,name,"__portfolio_missing_service__","--dry-run","--state",str(sandbox/"watchdog.json"),"--max-restarts","1"],log_dir,{0,1,2},"Dry-run only; no service restart")]
    if name == "backup_verify.py":
        manifest=backup_manifest(sandbox)
        return [record(name+"#record",[py,name,str(manifest),"--record"],log_dir,{0},"Explicit sandbox SHA-256 baseline approval"),
                record(name+"#verify",[py,name,str(manifest)],log_dir,{0},"Sandbox backup re-verification")]
    if name == "cert_expiry.py":
        return [record(name,[py,name,"example.com","--timeout","3"],log_dir,{0,1,2},"Read-only TLS check; network result is domain verdict",25)]
    if name == "incident_report.py":
        src=sandbox/"incident.json"; out=sandbox/"incident.md"
        a=record(name+"#init",[py,name,str(src),"--init"],log_dir,{0},"Generate incident fixture")
        b=record(name+"#report",[py,name,str(src),"--output",str(out)],log_dir,{0},"Generate incident/handover Markdown")
        return [a,b]
    if name == "alert_correlator.py":
        src=sandbox/"alerts.json"; md=sandbox/"alerts.md"; js=sandbox/"alerts-out.json"
        a=record(name+"#init",[py,name,str(src),"--init"],log_dir,{0},"Generate alert fixture")
        b=record(name+"#correlate",[py,name,str(src),"--output",str(md),"--json-output",str(js)],log_dir,{0},"Correlate alerts into incidents")
        return [a,b]
    if name == "capacity_planner.py":
        src=sandbox/"capacity.json"; out=sandbox/"capacity.md"
        a=record(name+"#init",[py,name,str(src),"--init"],log_dir,{0},"Generate capacity fixture")
        b=record(name+"#forecast",[py,name,str(src),"--output",str(out)],log_dir,{0,1,2},"Forecast capacity thresholds with OK/WARN/CRIT exit codes")
        return [a,b]
    if name == "sla_calculator.py":
        return [record(name,[py,name,"--days","30","--downtime","3","--targets","99.9","99.95","99.99"],log_dir,{0,1},"Calculate allowed downtime and SLA verdict")]
    if name == "python_server_upgrade.py":
        target=f"{sys.version_info.major}.{sys.version_info.minor}"
        report=sandbox/"python-upgrade.md"; js=sandbox/"python-upgrade.json"
        return [record(name,[py,name,"--target",target,"--target-executable",py,"--strict-target-installed",
                            "--report",str(report),"--json-report",str(js)],log_dir,{0},
                       "Strict current-runner precheck; safe_mode=true and no runtime/service changes")]
    return [record(name,[py,name,"--help"],log_dir,{0})]


def chrome() -> str | None:
    for name in ("google-chrome","google-chrome-stable","chromium","chromium-browser"):
        found = shutil.which(name)
        if found:
            return found
    return None


def browser_command(binary: str, name: str, sandbox: Path) -> list[str]:
    """Use an isolated profile so sequential headless runs cannot lock each other."""
    profile = sandbox / "chrome-profiles" / Path(name).stem
    profile.mkdir(parents=True, exist_ok=True)
    return [
        binary,
        "--headless=new",
        "--disable-gpu",
        "--no-sandbox",
        "--disable-dev-shm-usage",
        "--disable-background-networking",
        "--disable-default-apps",
        "--disable-extensions",
        "--disable-sync",
        "--metrics-recording-only",
        "--no-first-run",
        "--no-default-browser-check",
        "--allow-file-access-from-files",
        "--virtual-time-budget=3000",
        f"--user-data-dir={profile}",
        "--dump-dom",
        (ROOT/name).resolve().as_uri(),
    ]


def run_html(name: str, mode: str, sandbox: Path, log_dir: Path) -> list[dict[str, Any]]:
    text=(ROOT/name).read_text(encoding="utf-8"); parser=ScriptParser(); parser.feed(text)
    node=shutil.which("node"); out=[]
    if not node:
        return [{"target":name,"status":"ERROR","command":"node --check","exit_code":None,"duration_ms":0,"evidence":"Node unavailable","note":"","log":""}]
    for i,script in enumerate(parser.scripts,1):
        if not script.strip(): continue
        js=sandbox/f"{Path(name).stem}-{i}.js"; js.write_text(script,encoding="utf-8")
        out.append(record(f"{name}#js{i}",[node,"--check",str(js)],log_dir,{0},"Inline JavaScript syntax"))
    binary = chrome()
    if mode == "functional" and binary:
        cmd = browser_command(binary, name, sandbox)
        out.append(record(
            f"{name}#browser", cmd, log_dir, {0},
            "Isolated headless browser loads actual HTML with bounded virtual time", 30,
        ))
    if not out:
        out.append({"target":name,"status":"OK","command":"HTML parse","exit_code":0,"duration_ms":0,"evidence":f"inline_scripts={len(parser.scripts)}","note":"HTML parsed","log":""})
    return out


def tracked_files() -> list[str]:
    """Git-tracked files; falls back to a filesystem walk for release bundles without .git."""
    try:
        p = subprocess.run(["git", "ls-files", "-z"], cwd=ROOT, capture_output=True, timeout=15)
        if p.returncode == 0 and p.stdout:
            return sorted(x for x in p.stdout.decode("utf-8").split("\0") if x)
    except (OSError, subprocess.TimeoutExpired):
        pass
    skip = {".git", "__pycache__", ".venv", "venv", "_site", "release-bundle"}
    return sorted(
        f.relative_to(ROOT).as_posix() for f in ROOT.rglob("*")
        if f.is_file() and not skip.intersection(f.relative_to(ROOT).parts)
    )


def inline(name: str, status: str, command: str, evidence: str, note: str) -> dict[str, Any]:
    return {"target": name, "status": status, "command": command, "exit_code": 0 if status == "OK" else 1,
            "duration_ms": 0, "evidence": evidence[:180], "note": note, "log": ""}


def check_yaml_text(text: str) -> str | None:
    """Stdlib-only structural YAML check: YAML forbids tab characters in indentation."""
    for no, line in enumerate(text.splitlines(), 1):
        indent = line[: len(line) - len(line.lstrip())]
        if "\t" in indent:
            return f"line {no}: tab indentation"
    return None


def run_data(files: list[str]) -> list[dict[str, Any]]:
    out = []
    for rel in files:
        path = ROOT / rel
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            out.append(inline(rel, "ERROR", "read utf-8", str(exc), "Data file must be UTF-8 readable"))
            continue
        if not text.strip():
            out.append(inline(rel, "ERROR", "read utf-8", "empty file", "Data file must not be empty"))
            continue
        if rel.endswith(".json"):
            try:
                data = json.loads(text)
            except json.JSONDecodeError as exc:
                out.append(inline(rel, "ERROR", "json.loads", str(exc), "JSON parse"))
                continue
            kind = type(data).__name__
            size = len(data) if isinstance(data, (dict, list)) else 1
            out.append(inline(rel, "OK", "json.loads", f"{kind} entries={size}", "JSON parse"))
        elif rel.endswith((".yml", ".yaml")):
            problem = check_yaml_text(text)
            out.append(inline(rel, "ERROR" if problem else "OK", "yaml structure",
                              problem or f"lines={len(text.splitlines())}", "YAML indentation check"))
        else:
            out.append(inline(rel, "OK", "read utf-8", f"lines={len(text.splitlines())}", "UTF-8 text read"))
    return out


def run_scenarios(mode: str, sandbox: Path, log_dir: Path) -> list[dict[str, Any]]:
    py = sys.executable
    if mode == "smoke":
        return [record("scenario_runner.py", [py, "scenario_runner.py", "--help"], log_dir, {0}, "CLI entry-point smoke")]
    return [record("scenario_runner.py", [py, "scenario_runner.py", "scenarios",
                                          "--report", str(sandbox / "scenario-report.md"),
                                          "--json-report", str(sandbox / "scenario-report.json")],
                   log_dir, {0}, "Deterministic scenario regression against expected verdicts", 60)]


def run_tests(mode: str, log_dir: Path) -> list[dict[str, Any]]:
    if mode == "smoke":
        code = "import ast,pathlib;fs=sorted(pathlib.Path('tests').glob('test_*.py'));" \
               "[ast.parse(f.read_text(encoding='utf-8'),str(f)) for f in fs];print(f'parsed={len(fs)}')"
        return [record("tests#syntax", [sys.executable, "-c", code], log_dir, {0}, "Unit test syntax smoke")]
    return [record("tests#unittest", [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", "test_*.py"],
                   log_dir, {0}, "Full unit test suite", 180)]


def write_interim(records: list[dict[str, Any]], path: Path) -> None:
    errors = sum(r["status"] == "ERROR" for r in records)
    path.write_text(json.dumps({"target": "all", "mode": "functional", "status": "PASS" if not errors else "FAIL",
                                "records": records}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def run_pipeline(mode: str, sandbox: Path, log_dir: Path, prior: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Chain the control/report tools so each consumes the previous tool's real output."""
    py = sys.executable
    if mode == "smoke":
        return [record(t, [py, t, "--help"], log_dir, {0}, "Runner/control smoke") for t in PIPELINE_TOOLS]
    sb = sandbox / "pipeline"; sb.mkdir(exist_ok=True)
    functional = sb / "functional-run.json"
    write_interim(prior, functional)
    out = [
        record("tools/review_repo.py", [py, "tools/review_repo.py", "--report", str(sb/"review.md"),
                                        "--json-report", str(sb/"review.json")], log_dir, {0},
               "Repository review into sandbox", 60),
        record("tools/run_analyze.py", [py, "tools/run_analyze.py", "--manifest", "portfolio-manifest.json",
                                        "--report", str(sb/"execution-report.md"),
                                        "--json-report", str(sb/"execution-report.json")], log_dir, {0},
               "Execution analysis of every tracked file", 180),
        record("tools/portfolio_manager.py", [py, "tools/portfolio_manager.py", "--fail-on-blocked",
                                              "--readiness-report", str(sb/"interview-readiness.md"),
                                              "--json-report", str(sb/"interview-readiness.json"),
                                              "--inventory-report", str(sb/"feature-inventory.md"),
                                              "--upgrade-report", str(sb/"upgrade-plan.md")], log_dir, {0},
               "Lifecycle readiness gate", 60),
        record("tools/summarize_reports.py", [py, "tools/summarize_reports.py",
                                              "--review-json", str(sb/"review.json"),
                                              "--execution-json", str(sb/"execution-report.json"),
                                              "--functional-json", str(functional),
                                              "--report", str(sb/"summary.md"),
                                              "--json-report", str(sb/"summary.json")], log_dir, {0},
               "Deterministic summary of chained reports"),
    ]
    scenario_json = sandbox / "scenario-report.json"
    report_cmd = [py, "tools/portfolio_report.py", "--review", str(sb/"review.json"),
                  "--execution", str(sb/"execution-report.json"), "--functional", str(functional),
                  "--summary", str(sb/"summary.json"), "--output", str(sb/"portfolio-report.html")]
    if scenario_json.exists():
        report_cmd[-2:-2] = ["--scenarios", str(scenario_json)]
    out.append(record("tools/portfolio_report.py", report_cmd, log_dir, {0}, "Integrated HTML quality report"))
    out.append(record("tools/execute_repo.py", [py, "tools/execute_repo.py", "--list"], log_dir, {0},
                      "Self target listing (no recursive run)"))
    return out


def base_name(target: str) -> str:
    return target.split("#", 1)[0]


def coverage_gate(records: list[dict[str, Any]], tracked: list[str]) -> dict[str, Any]:
    """Every tracked executable/data file must have been exercised by at least one record."""
    covered = {base_name(r["target"]) for r in records}
    if any(r["target"] in {"tests#unittest", "tests#syntax"} and r["status"] == "OK" for r in records):
        covered.update(f for f in tracked if f.startswith("tests/") and f.endswith(".py"))
    required = [f for f in tracked if is_runnable(f) or is_data(f)]
    missing = [f for f in required if f not in covered]
    status = "OK" if not missing else "ERROR"
    evidence = f"covered={len(required)-len(missing)}/{len(required)}"
    if missing:
        evidence += " missing=" + ",".join(missing[:8])
    return inline("coverage#gate", status, "git ls-files coverage", evidence,
                  "Every tracked .py/.html/data file must be executed or validated")


def is_runnable(rel: str) -> bool:
    return rel.endswith((".py", ".html"))


def is_data(rel: str) -> bool:
    return Path(rel).suffix in {".json", *TEXT_DATA_EXTS} or Path(rel).name in TEXT_DATA_NAMES


def selected(target: str) -> list[str]:
    if target == "all": return [*PYTHON_TOOLS,*HTML_FILES]
    if target == "python": return PYTHON_TOOLS[:]
    if target == "html": return HTML_FILES[:]
    if target in {"scenarios", "pipeline", "tests", "data"}: return []
    return [target]


def execute(target: str, mode: str, log_dir: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    tracked = tracked_files()
    with tempfile.TemporaryDirectory(prefix="daoutech-run-") as td:
        sandbox = Path(td)
        for name in selected(target):
            records += run_python(name, mode, sandbox, log_dir) if name.endswith(".py") else run_html(name, mode, sandbox, log_dir)
        if target in {"all", "scenarios"}:
            records += run_scenarios(mode, sandbox, log_dir)
        if target in {"all", "tests"}:
            records += run_tests(mode, log_dir)
        if target in {"all", "data"}:
            records += run_data([f for f in tracked if is_data(f)])
        if target in {"all", "pipeline"}:
            records += run_pipeline(mode, sandbox, log_dir, records)
        if target == "all":
            records.append(coverage_gate(records, tracked))
    return records


def render(records: list[dict[str, Any]], target: str, mode: str) -> str:
    errors=sum(r["status"]=="ERROR" for r in records)
    lines=["# 저장소 파일 실행 결과","",f"- 대상: **{target}**",f"- 모드: **{mode}**",f"- 수행 항목: **{len(records)}개**",f"- 오류: **{errors}건**",f"- 최종 상태: **{'PASS' if not errors else 'FAIL'}**","","| 상태 | 대상 | 종료 | 실행/검증 |","|---|---|---:|---|"]
    for r in records:
        detail="; ".join(x for x in (r.get("evidence",""),r.get("note","")) if x).replace("|","\\|")
        lines.append(f"| {r['status']} | `{r['target']}` | {r.get('exit_code')} | {detail} |")
    lines += ["","## 안전 정책","","- 서비스 워치독은 `--dry-run`만 사용합니다.","- 백업/이력/보고서 입력은 임시 샌드박스에 생성합니다.","- 인증서 검사는 읽기 전용 TLS 연결만 수행합니다.","- Python 런타임 업그레이드는 strict precheck만 수행하며 설치·삭제·서비스 변경을 하지 않습니다.","- HTML은 JavaScript 검사 후 격리된 headless 브라우저 profile과 제한된 virtual time으로 실제 로딩합니다.","- 제어/리포트 도구 체인(review → analyze → lifecycle → summary → HTML report)은 샌드박스 경로에만 출력합니다.","- `all` 대상은 `git ls-files` 기준 모든 .py/.html/데이터 파일이 실행·검증되었는지 coverage gate로 확인합니다.",""]
    return "\n".join(lines)


def main() -> int:
    ap=argparse.ArgumentParser(description="DAOUTECH_IDC 저장소 실행기")
    ap.add_argument("--target",default="all",choices=TARGETS)
    ap.add_argument("--mode",default="functional",choices=["functional","smoke"])
    ap.add_argument("--report",default="run-results.md")
    ap.add_argument("--json-report",default="run-results.json")
    ap.add_argument("--log-dir",default="execution-logs")
    ap.add_argument("--list",action="store_true")
    args=ap.parse_args()
    if args.list:
        print("\n".join(TARGETS)); return 0
    log_dir=ROOT/args.log_dir
    records=execute(args.target,args.mode,log_dir)
    text=render(records,args.target,args.mode)
    (ROOT/args.report).write_text(text,encoding="utf-8")
    errors=sum(r["status"]=="ERROR" for r in records)
    (ROOT/args.json_report).write_text(json.dumps({"target":args.target,"mode":args.mode,"status":"PASS" if not errors else "FAIL","records":records},ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(f"저장소 실행 완료: 수행 {len(records)}개 / 오류 {errors}건")
    print(f"결과: {'PASS' if not errors else 'FAIL'}")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
