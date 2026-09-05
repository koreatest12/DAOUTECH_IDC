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
]
HTML_FILES = [
    "index.html", "noc-dashboard.html", "linux-security-lab.html",
    "backup-simulator.html", "incident-lab.html", "server-console.html",
    "network-path.html", "batch-operations-lab.html", "change-management-lab.html",
]
META_TOOLS = ["tools/review_repo.py", "tools/run_analyze.py", "tools/execute_repo.py"]
TARGETS = ["all", "python", "html", *PYTHON_TOOLS, *HTML_FILES]


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
        return [record(name+"#record",[py,name,str(manifest),"--record"],log_dir,{0},"Sandbox SHA-256 baseline"),
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
        b=record(name+"#forecast",[py,name,str(src),"--output",str(out)],log_dir,{0,1},"Forecast capacity thresholds")
        return [a,b]
    if name == "sla_calculator.py":
        return [record(name,[py,name,"--days","30","--downtime","3","--targets","99.9","99.95","99.99"],log_dir,{0,1},"Calculate allowed downtime and SLA verdict")]
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


def selected(target: str) -> list[str]:
    if target == "all": return [*PYTHON_TOOLS,*HTML_FILES]
    if target == "python": return PYTHON_TOOLS[:]
    if target == "html": return HTML_FILES[:]
    return [target]


def render(records: list[dict[str, Any]], target: str, mode: str) -> str:
    errors=sum(r["status"]=="ERROR" for r in records)
    lines=["# 저장소 파일 실행 결과","",f"- 대상: **{target}**",f"- 모드: **{mode}**",f"- 수행 항목: **{len(records)}개**",f"- 오류: **{errors}건**",f"- 최종 상태: **{'PASS' if not errors else 'FAIL'}**","","| 상태 | 대상 | 종료 | 실행/검증 |","|---|---|---:|---|"]
    for r in records:
        detail="; ".join(x for x in (r.get("evidence",""),r.get("note","")) if x).replace("|","\\|")
        lines.append(f"| {r['status']} | `{r['target']}` | {r.get('exit_code')} | {detail} |")
    lines += ["","## 안전 정책","","- 서비스 워치독은 `--dry-run`만 사용합니다.","- 백업/이력/보고서 입력은 임시 샌드박스에 생성합니다.","- 인증서 검사는 읽기 전용 TLS 연결만 수행합니다.","- HTML은 JavaScript 검사 후 격리된 headless 브라우저 profile과 제한된 virtual time으로 실제 로딩합니다.",""]
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
    log_dir=ROOT/args.log_dir; records=[]
    with tempfile.TemporaryDirectory(prefix="daoutech-run-") as td:
        sandbox=Path(td)
        for name in selected(args.target):
            records += run_python(name,args.mode,sandbox,log_dir) if name.endswith(".py") else run_html(name,args.mode,sandbox,log_dir)
        if args.target=="all":
            for meta in META_TOOLS:
                records.append(record(meta,[sys.executable,meta,"--help"],log_dir,{0},"Runner/control smoke"))
    text=render(records,args.target,args.mode)
    (ROOT/args.report).write_text(text,encoding="utf-8")
    errors=sum(r["status"]=="ERROR" for r in records)
    (ROOT/args.json_report).write_text(json.dumps({"target":args.target,"mode":args.mode,"status":"PASS" if not errors else "FAIL","records":records},ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(f"저장소 실행 완료: 수행 {len(records)}개 / 오류 {errors}건")
    print(f"결과: {'PASS' if not errors else 'FAIL'}")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
