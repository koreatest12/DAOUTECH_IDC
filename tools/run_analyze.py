#!/usr/bin/env python3
"""Safely execute and analyze every tracked portfolio file for submission readiness."""

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

ARCHIVES = {".zip", ".tar", ".gz", ".tgz", ".7z", ".rar"}
TEXT_EXTS = {".md", ".txt", ".json", ".yml", ".yaml", ".toml", ".ini", ".cfg", ".conf", ".csv", ".tsv", ".js", ".mjs", ".cjs", ".css", ".sh", ".ps1", ".bat", ".cmd"}


class InlineScriptParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.scripts: list[str] = []
        self._capture = False
        self._parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "script":
            return
        attr_map = dict(attrs)
        if attr_map.get("src"):
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


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def run(cmd: list[str], cwd: Path, timeout: int = 20) -> dict[str, Any]:
    started = time.perf_counter()
    env = os.environ.copy()
    env.setdefault("PYTHONDONTWRITEBYTECODE", "1")
    try:
        proc = subprocess.run(cmd, cwd=cwd, text=True, capture_output=True, timeout=timeout, env=env)
        elapsed = int((time.perf_counter() - started) * 1000)
        return {
            "exit_code": proc.returncode,
            "duration_ms": elapsed,
            "stdout": proc.stdout.strip(),
            "stderr": proc.stderr.strip(),
            "timeout": False,
        }
    except subprocess.TimeoutExpired as exc:
        elapsed = int((time.perf_counter() - started) * 1000)
        return {
            "exit_code": None,
            "duration_ms": elapsed,
            "stdout": (exc.stdout or "") if isinstance(exc.stdout, str) else "",
            "stderr": (exc.stderr or "") if isinstance(exc.stderr, str) else "",
            "timeout": True,
        }


def tracked_files(root: Path) -> list[Path]:
    proc = subprocess.run(["git", "ls-files", "-z"], cwd=root, capture_output=True)
    if proc.returncode == 0:
        return [root / p.decode("utf-8", errors="surrogateescape") for p in proc.stdout.split(b"\0") if p]
    return sorted(p for p in root.rglob("*") if p.is_file() and ".git" not in p.parts)


def read_manifest(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError("manifest root must be a JSON object")
    return data


def purpose_map(manifest: dict[str, Any]) -> dict[str, str]:
    result: dict[str, str] = {}
    for item in manifest.get("files", []):
        if isinstance(item, dict) and isinstance(item.get("path"), str):
            result[item["path"]] = str(item.get("purpose", ""))
    return result


def short_output(result: dict[str, Any]) -> str:
    text = result.get("stdout") or result.get("stderr") or ""
    line = next((ln.strip() for ln in str(text).splitlines() if ln.strip()), "")
    return line[:180]


def analyze_python(root: Path, path: Path, rel: str) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    tree = ast.parse(text, filename=rel)
    functions = [n.name for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
    classes = [n.name for n in tree.body if isinstance(n, ast.ClassDef)]
    has_cli = "argparse" in text or "ArgumentParser" in text
    record: dict[str, Any] = {
        "status": "OK",
        "check": "Python AST parse",
        "details": f"functions={len(functions)}, classes={len(classes)}",
        "command": None,
        "exit_code": None,
        "duration_ms": 0,
    }
    if has_cli:
        cmd = [sys.executable, rel, "--help"]
        result = run(cmd, root)
        record.update({
            "check": "Python AST + safe CLI execution (--help)",
            "command": " ".join(cmd),
            "exit_code": result["exit_code"],
            "duration_ms": result["duration_ms"],
            "evidence": short_output(result),
        })
        if result["timeout"] or result["exit_code"] != 0:
            record["status"] = "ERROR"
            record["details"] = "safe CLI execution failed or timed out"
    return record


def analyze_html(root: Path, path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    parser = InlineScriptParser()
    parser.feed(text)
    node = shutil.which("node")
    if not node:
        return {
            "status": "SKIP",
            "check": "HTML parse; Node unavailable",
            "details": f"inline_scripts={len(parser.scripts)}",
            "command": None,
            "exit_code": None,
            "duration_ms": 0,
        }
    total_ms = 0
    with tempfile.TemporaryDirectory(prefix="portfolio-js-") as temp_dir:
        for index, script in enumerate(parser.scripts, 1):
            if not script.strip():
                continue
            js = Path(temp_dir) / f"script-{index}.js"
            js.write_text(script, encoding="utf-8")
            result = run([node, "--check", str(js)], root)
            total_ms += result["duration_ms"]
            if result["timeout"] or result["exit_code"] != 0:
                return {
                    "status": "ERROR",
                    "check": "HTML parse + inline JavaScript node --check",
                    "details": short_output(result) or f"inline script {index} failed",
                    "command": "node --check <inline-script>",
                    "exit_code": result["exit_code"],
                    "duration_ms": total_ms,
                }
    return {
        "status": "OK",
        "check": "HTML parse + inline JavaScript node --check",
        "details": f"inline_scripts={len(parser.scripts)}",
        "command": "node --check <inline-script>",
        "exit_code": 0,
        "duration_ms": total_ms,
    }


def analyze_regular(path: Path) -> dict[str, Any]:
    ext = path.suffix.lower()
    if ext == ".json":
        data = json.loads(path.read_text(encoding="utf-8"))
        return {"status": "OK", "check": "JSON parse", "details": f"root_type={type(data).__name__}", "command": None, "exit_code": 0, "duration_ms": 0}
    if ext in ARCHIVES:
        return {"status": "ERROR", "check": "submission archive policy", "details": "tracked archive is not allowed; use Actions artifact or Release", "command": None, "exit_code": None, "duration_ms": 0}
    if ext in TEXT_EXTS or path.name in {".gitignore", "LICENSE", "requirements.txt"}:
        text = path.read_text(encoding="utf-8")
        return {"status": "OK", "check": "UTF-8 readability", "details": f"lines={len(text.splitlines())}", "command": None, "exit_code": 0, "duration_ms": 0}
    return {"status": "SKIP", "check": "metadata only", "details": "no safe deterministic execution rule", "command": None, "exit_code": None, "duration_ms": 0}


def analyze_file(root: Path, path: Path, purposes: dict[str, str]) -> dict[str, Any]:
    rel = path.relative_to(root).as_posix()
    base = {
        "path": rel,
        "purpose": purposes.get(rel, ""),
        "size_bytes": path.stat().st_size,
        "type": path.suffix.lower().lstrip(".") or "file",
    }
    try:
        if path.suffix.lower() == ".py":
            check = analyze_python(root, path, rel)
        elif path.suffix.lower() in {".html", ".htm"}:
            check = analyze_html(root, path)
        else:
            check = analyze_regular(path)
    except (SyntaxError, UnicodeDecodeError, json.JSONDecodeError, OSError, ValueError) as exc:
        check = {"status": "ERROR", "check": "analysis", "details": str(exc), "command": None, "exit_code": None, "duration_ms": 0}
    base.update(check)
    return base


def submission_checks(root: Path, manifest: dict[str, Any], tracked: set[str]) -> list[dict[str, str]]:
    checks: list[dict[str, str]] = []
    for rel in manifest.get("submission_required", []):
        rel = str(rel)
        exists = (root / rel).is_file() and rel in tracked
        checks.append({
            "status": "OK" if exists else "ERROR",
            "item": rel,
            "message": "tracked and present" if exists else "required submission file missing or untracked",
        })
    archives = sorted(p for p in tracked if Path(p).suffix.lower() in ARCHIVES)
    checks.append({
        "status": "OK" if not archives else "ERROR",
        "item": "tracked archives",
        "message": "none" if not archives else ", ".join(archives),
    })
    return checks


def render_markdown(records: list[dict[str, Any]], submission: list[dict[str, str]]) -> str:
    errors = sum(r["status"] == "ERROR" for r in records) + sum(c["status"] == "ERROR" for c in submission)
    skipped = sum(r["status"] == "SKIP" for r in records)
    lines = [
        "# 제출 실행·분석 리포트",
        "",
        "> 안전한 제출 검증만 수행합니다. 서비스 재기동, 외부 시스템 변경, 실제 백업 변경 같은 부작용 동작은 실행하지 않습니다.",
        "",
        "## 판정",
        "",
        f"- 추적 파일: **{len(records)}개**",
        f"- 실행/분석 오류: **{errors}건**",
        f"- 안전 규칙상 실행 생략: **{skipped}건**",
        f"- 제출 준비 상태: **{'READY' if errors == 0 else 'BLOCKED'}**",
        "",
        "## 제출 필수 파일 검사",
        "",
        "| 상태 | 항목 | 결과 |",
        "|---|---|---|",
    ]
    for item in submission:
        lines.append(f"| {item['status']} | `{item['item']}` | {item['message']} |")
    lines.extend([
        "",
        "## 전체 파일 실행·분석",
        "",
        "| 상태 | 파일 | 검사/실행 방식 | 결과 |",
        "|---|---|---|---|",
    ])
    for rec in records:
        result = rec.get("details", "")
        if rec.get("command"):
            result += f"; exit={rec.get('exit_code')}; {rec.get('duration_ms', 0)}ms"
        lines.append(f"| {rec['status']} | `{rec['path']}` | {rec['check']} | {result} |")
    lines.extend([
        "",
        "## 안전 실행 정책",
        "",
        "- Python CLI는 `--help`로 실제 엔트리포인트 로딩과 argparse 구성을 실행 검증합니다.",
        "- HTML은 파싱 후 모든 인라인 JavaScript를 Node 24의 `node --check`로 검증합니다.",
        "- JSON은 실제 파싱하고, Markdown/YAML/TXT/라이선스/설정 파일은 UTF-8 가독성을 확인합니다.",
        "- 운영 영향 가능성이 있는 서비스 재기동, 외부 인증서 조회, 실제 백업/파일 변경은 CI에서 자동 실행하지 않습니다.",
        "- 새 파일이 Git에 추가되면 별도 YAML 수정 없이 다음 실행부터 자동 분석 대상이 됩니다.",
        "",
    ])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="DAOUTECH_IDC 제출용 전체 파일 안전 실행·분석")
    parser.add_argument("--manifest", default="portfolio-manifest.json")
    parser.add_argument("--report", default="execution-report.md")
    parser.add_argument("--json-report", default="execution-report.json")
    args = parser.parse_args()

    root = repo_root()
    manifest = read_manifest(root / args.manifest)
    purposes = purpose_map(manifest)
    paths = tracked_files(root)
    records = [analyze_file(root, path, purposes) for path in paths]
    tracked = {path.relative_to(root).as_posix() for path in paths}
    submission = submission_checks(root, manifest, tracked)

    (root / args.report).write_text(render_markdown(records, submission), encoding="utf-8")
    payload = {"files": records, "submission_checks": submission}
    (root / args.json_report).write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    errors = sum(r["status"] == "ERROR" for r in records) + sum(c["status"] == "ERROR" for c in submission)
    skipped = sum(r["status"] == "SKIP" for r in records)
    print(f"실행·분석 완료: 파일 {len(records)}개 / 오류 {errors}건 / 생략 {skipped}건")
    print(f"제출 준비 상태: {'READY' if errors == 0 else 'BLOCKED'}")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
