#!/usr/bin/env python3
"""DAOUTECH_IDC 저장소의 구조·문법·README 참조를 결정적으로 검수하고 파일별 설명을 생성합니다."""

from __future__ import annotations

import argparse
import ast
import html
import json
import os
import re
import shutil
import subprocess
import tempfile
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlsplit

TEXT_EXTENSIONS = {
    ".md", ".txt", ".py", ".html", ".htm", ".json", ".yml", ".yaml",
    ".toml", ".ini", ".cfg", ".conf", ".csv", ".tsv", ".js", ".mjs", ".cjs",
    ".css", ".sh", ".ps1", ".bat", ".cmd",
}
ARCHIVE_EXTENSIONS = {".zip", ".tar", ".gz", ".tgz", ".7z", ".rar"}
SKIP_NAMES = {".DS_Store"}

PURPOSE_BY_NAME = {
    "README.md": "저장소의 목적, 실행 방법, 도구별 운영 배경을 설명하는 포트폴리오 안내 문서",
    "healthcheck.py": "서버 상태를 수집하고 임계치에 따라 종료 코드로 판정하는 헬스체크 도구",
    "check.json": "서버 헬스체크의 점검 대상과 임계치 설정 파일",
    "log_analyzer.py": "로그를 정규화·집계해 반복 오류와 시간대별 이상 징후를 찾는 분석 도구",
    "disk_forecast.py": "디스크 사용 추세로 임계치 도달 시점을 예측하는 운영 도구",
    "svc_watchdog.py": "서비스 상태 확인과 제한적 재기동을 수행하는 워치독 도구",
    "backup_verify.py": "백업 파일의 존재·크기·신선도·해시 등을 검증하는 도구",
    "cert_expiry.py": "TLS 인증서 만료일까지 남은 기간을 확인하는 도구",
    "domains.txt": "인증서 만료 점검 대상 도메인 목록",
    "noc-dashboard.html": "IDC 장비·랙·포트 상태를 시각화한 단일 파일 관제 시뮬레이터",
    "linux-security-lab.html": "리눅스 권한·로그·방화벽 정책을 실습하는 보안 시뮬레이터",
    "backup-simulator.html": "백업 스케줄·복구 체인·장애 주입을 연습하는 시뮬레이터",
    "incident-lab.html": "IDC 장애 조사·원인 판단·조치 선택을 연습하는 장애 대응 랩",
    "server-console.html": "장애 상황별 서버 명령 결과를 비교하는 운영 콘솔 시뮬레이터",
    "network-path.html": "네트워크 구간별 장애를 진단하는 경로 분석 시뮬레이터",
    "summary.yml": "저장소 검수, 파일별 리포트 생성, AI 요약을 통합 수행하는 GitHub Actions 워크플로",
    ".gitignore": "버전 관리에서 제외할 로컬·생성 파일 패턴 정의",
    "LICENSE": "저장소 소프트웨어 사용 조건을 정의하는 라이선스 문서",
    "review_repo.py": "저장소의 사실 기반 검수와 파일별 설명 리포트를 생성하는 결정적 검사기",
}

class HTMLSummaryParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.title_parts: list[str] = []
        self.headings: list[str] = []
        self.inline_scripts: list[str] = []
        self.external_scripts: list[str] = []
        self._capture_title = False
        self._capture_heading = False
        self._capture_script = False
        self._current_text: list[str] = []
        self._script_text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_dict = dict(attrs)
        lower = tag.lower()
        if lower == "title":
            self._capture_title = True
            self._current_text = []
        elif lower in {"h1", "h2"}:
            self._capture_heading = True
            self._current_text = []
        elif lower == "script":
            src = attrs_dict.get("src")
            if src:
                self.external_scripts.append(src)
            else:
                self._capture_script = True
                self._script_text = []

    def handle_endtag(self, tag: str) -> None:
        lower = tag.lower()
        if lower == "title" and self._capture_title:
            self.title_parts.append(" ".join(self._current_text).strip())
            self._capture_title = False
        elif lower in {"h1", "h2"} and self._capture_heading:
            text = " ".join(self._current_text).strip()
            if text:
                self.headings.append(text)
            self._capture_heading = False
        elif lower == "script" and self._capture_script:
            self.inline_scripts.append("".join(self._script_text))
            self._capture_script = False

    def handle_data(self, data: str) -> None:
        if self._capture_title or self._capture_heading:
            self._current_text.append(data)
        if self._capture_script:
            self._script_text.append(data)


def run(cmd: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=cwd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def repo_root() -> Path:
    proc = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
    )
    if proc.returncode == 0 and proc.stdout.strip():
        return Path(proc.stdout.strip()).resolve()
    return Path.cwd().resolve()


def tracked_files(root: Path) -> list[Path]:
    proc = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=root,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.decode("utf-8", errors="replace"))
    items = [p for p in proc.stdout.decode("utf-8", errors="surrogateescape").split("\0") if p]
    return [root / item for item in items if Path(item).name not in SKIP_NAMES]


def human_size(size: int) -> str:
    value = float(size)
    for unit in ("B", "KB", "MB", "GB"):
        if value < 1024 or unit == "GB":
            return f"{value:.0f} {unit}" if unit == "B" else f"{value:.1f} {unit}"
        value /= 1024
    return f"{size} B"


def first_nonempty(text: str, limit: int = 140) -> str:
    for line in text.splitlines():
        cleaned = re.sub(r"\s+", " ", line.strip().lstrip("#").strip())
        if cleaned:
            return cleaned[:limit]
    return ""


def safe_read_text(path: Path) -> tuple[str | None, str | None]:
    try:
        return path.read_text(encoding="utf-8"), None
    except UnicodeDecodeError:
        try:
            return path.read_text(encoding="utf-8-sig"), None
        except Exception as exc:
            return None, f"UTF-8 텍스트로 읽을 수 없음: {exc}"
    except Exception as exc:
        return None, f"파일 읽기 실패: {exc}"


def infer_purpose(path: Path, text: str | None = None) -> str:
    if path.name in PURPOSE_BY_NAME:
        return PURPOSE_BY_NAME[path.name]
    ext = path.suffix.lower()
    if ext in ARCHIVE_EXTENSIONS:
        return "배포·백업용 압축 아카이브"
    if ext == ".py":
        return "Python 운영/자동화 도구"
    if ext in {".html", ".htm"}:
        return "브라우저에서 실행하는 단일 파일 HTML 도구 또는 시뮬레이터"
    if ext in {".yml", ".yaml"}:
        return "YAML 설정 또는 CI/CD 워크플로"
    if ext == ".json":
        return "구조화된 JSON 설정/데이터 파일"
    if ext == ".md":
        return "Markdown 문서"
    if ext in {".txt", ".csv", ".tsv"}:
        return "운영 입력/참조용 텍스트 데이터"
    if text:
        line = first_nonempty(text)
        if line:
            return line
    return "저장소 구성 파일"


def status_rank(status: str) -> int:
    return {"OK": 0, "WARN": 1, "ERROR": 2}.get(status, 0)


def add_issue(issues: list[dict[str, str]], file_info: dict[str, Any], severity: str, message: str, action: str) -> None:
    issues.append({"severity": severity, "path": file_info["path"], "message": message, "action": action})
    if status_rank(severity) > status_rank(file_info["status"]):
        file_info["status"] = severity
    file_info["checks"].append(f"{severity}: {message}")


def check_python(root: Path, path: Path, text: str, info: dict[str, Any], issues: list[dict[str, str]]) -> None:
    try:
        tree = ast.parse(text, filename=str(path))
    except SyntaxError as exc:
        add_issue(issues, info, "ERROR", f"Python 문법 오류: {exc.msg} (line {exc.lineno})", "해당 줄의 Python 문법을 수정한 뒤 다시 실행")
        return
    doc = ast.get_docstring(tree)
    functions = [n.name for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
    classes = [n.name for n in tree.body if isinstance(n, ast.ClassDef)]
    imports: list[str] = []
    for node in tree.body:
        if isinstance(node, ast.Import):
            imports.extend(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.append(node.module.split(".")[0])
    if doc:
        info["summary"] = re.sub(r"\s+", " ", doc.strip().splitlines()[0])[:180]
    detail_parts = []
    if functions:
        detail_parts.append("함수 " + ", ".join(functions[:8]) + (" 외" if len(functions) > 8 else ""))
    if classes:
        detail_parts.append("클래스 " + ", ".join(classes[:5]) + (" 외" if len(classes) > 5 else ""))
    if imports:
        detail_parts.append("주요 import " + ", ".join(sorted(set(imports))[:10]))
    info["analysis"] = "; ".join(detail_parts) or "AST 문법 검사 통과"
    info["checks"].append("OK: Python AST 문법 검사 통과")


def check_inline_js(root: Path, path: Path, scripts: list[str], info: dict[str, Any], issues: list[dict[str, str]]) -> None:
    node = shutil.which("node")
    if not scripts:
        info["checks"].append("OK: 인라인 JavaScript 없음")
        return
    if not node:
        add_issue(issues, info, "WARN", "Node 실행 파일이 없어 인라인 JavaScript 문법 검사를 건너뜀", "GitHub Actions에서 Node 24를 준비한 뒤 다시 실행")
        return
    with tempfile.TemporaryDirectory(prefix="repo-review-js-") as temp_dir:
        for idx, script in enumerate(scripts, 1):
            if not script.strip():
                continue
            temp_path = Path(temp_dir) / f"script-{idx}.js"
            temp_path.write_text(script, encoding="utf-8")
            proc = run([node, "--check", str(temp_path)], root)
            if proc.returncode != 0:
                message = (proc.stderr or proc.stdout).strip().splitlines()
                excerpt = message[-1] if message else "알 수 없는 문법 오류"
                add_issue(issues, info, "ERROR", f"인라인 JavaScript #{idx} 문법 오류: {excerpt[:180]}", f"{path.name}의 {idx}번째 인라인 script 문법 수정")
                return
    info["checks"].append(f"OK: 인라인 JavaScript {len(scripts)}개 node --check 통과")


def check_html(root: Path, path: Path, text: str, info: dict[str, Any], issues: list[dict[str, str]]) -> None:
    parser = HTMLSummaryParser()
    try:
        parser.feed(text)
    except Exception as exc:
        add_issue(issues, info, "WARN", f"HTML 파서 경고: {exc}", "HTML 태그 구조 확인")
        return
    title = next((t for t in parser.title_parts if t), "")
    heading_text = ", ".join(parser.headings[:5])
    if title:
        info["summary"] = html.unescape(title)[:180]
    elif parser.headings:
        info["summary"] = html.unescape(parser.headings[0])[:180]
    parts = []
    if title:
        parts.append(f"title: {title}")
    if heading_text:
        parts.append(f"주요 제목: {heading_text}")
    parts.append(f"인라인 script {len(parser.inline_scripts)}개")
    if parser.external_scripts:
        parts.append(f"외부 script {len(parser.external_scripts)}개")
    info["analysis"] = "; ".join(parts)
    check_inline_js(root, path, parser.inline_scripts, info, issues)


def normalize_local_target(raw: str) -> str | None:
    raw = html.unescape(raw.strip())
    if not raw or raw.startswith(("#", "mailto:", "tel:", "javascript:", "data:")):
        return None
    split = urlsplit(raw)
    if split.scheme or split.netloc:
        return None
    target = unquote(split.path).strip()
    if not target or target in {".", "./"}:
        return None
    return target


def check_markdown(root: Path, path: Path, text: str, info: dict[str, Any], issues: list[dict[str, str]]) -> None:
    headings = re.findall(r"(?m)^\s{0,3}#{1,6}\s+(.+?)\s*$", text)
    links = re.findall(r"(?<!!)\[[^\]]*\]\(([^)]+)\)", text)
    local_targets = []
    for raw in links:
        target = normalize_local_target(raw.split()[0].strip("<>"))
        if target:
            local_targets.append(target)
    broken_links = []
    for target in local_targets:
        candidate = (path.parent / target).resolve()
        try:
            candidate.relative_to(root)
        except ValueError:
            continue
        if not candidate.exists():
            broken_links.append(target)
    for target in sorted(set(broken_links)):
        add_issue(issues, info, "ERROR", f"Markdown 로컬 링크 대상 없음: {target}", "README/문서의 링크를 실제 저장소 경로로 수정하거나 파일을 추가")
    code_spans = re.findall(r"`([^`\n]+)`", text)
    referenced_missing = []
    for span in code_spans:
        value = span.strip().rstrip(".,;:")
        if " " in value or value.startswith(("-", "$", "http://", "https://")):
            continue
        looks_like_repo_path = bool(re.match(r"^\d{2}-[A-Za-z0-9._-]+(?:/.*)?$", value) or re.search(r"/.+\.(?:py|html?|json|txt|md|ya?ml)$", value, re.I))
        if not looks_like_repo_path:
            continue
        candidate = (path.parent / value).resolve()
        try:
            candidate.relative_to(root)
        except ValueError:
            continue
        if not candidate.exists():
            referenced_missing.append(value)
    for target in sorted(set(referenced_missing)):
        add_issue(issues, info, "WARN", f"문서가 존재하지 않는 저장소 경로를 코드 표기로 언급: {target}", "문서 경로를 실제 파일 위치와 맞추거나 해당 디렉터리/파일을 구성")
    if headings:
        info["summary"] = re.sub(r"[*_`]", "", headings[0])[:180]
    info["analysis"] = f"제목 {len(headings)}개; Markdown 링크 {len(links)}개; 로컬 링크 {len(local_targets)}개"
    if not broken_links:
        info["checks"].append("OK: Markdown 로컬 링크 검사 통과")


def check_json(text: str, info: dict[str, Any], issues: list[dict[str, str]]) -> None:
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        add_issue(issues, info, "ERROR", f"JSON 문법 오류: {exc.msg} (line {exc.lineno})", "JSON 문법을 수정한 뒤 다시 실행")
        return
    if isinstance(data, dict):
        keys = list(data)[:12]
        info["analysis"] = f"JSON object; 최상위 키: {', '.join(map(str, keys)) or '(없음)'}"
    elif isinstance(data, list):
        info["analysis"] = f"JSON array; 항목 {len(data)}개"
    else:
        info["analysis"] = f"JSON {type(data).__name__}"
    info["checks"].append("OK: JSON 파싱 통과")


def check_yaml_workflow(path: Path, text: str, info: dict[str, Any], issues: list[dict[str, str]]) -> None:
    name_match = re.search(r"(?m)^name:\s*(.+?)\s*$", text)
    jobs = re.findall(r"(?m)^\s{2}([A-Za-z0-9_-]+):\s*$", text)
    uses = re.findall(r"(?m)^\s*uses:\s*([^\s#]+)", text)
    if name_match:
        info["summary"] = f"GitHub Actions: {name_match.group(1).strip().strip(chr(34)).strip(chr(39))}"
    info["analysis"] = f"job 후보 {len(jobs)}개; 외부 action {len(uses)}개"
    deprecated_patterns = {
        "actions/checkout@v4": "actions/checkout@v5 이상(Node 24 런타임)으로 업그레이드",
        "actions/setup-python@v5": "actions/setup-python@v6 이상(Node 24 런타임)으로 업그레이드",
        "actions/setup-node@v4": "actions/setup-node@v5 이상(Node 24 런타임)으로 업그레이드",
        "actions/ai-inference@v1": "GitHub Models를 유지하려면 actions/ai-inference@v2.1.1 등 Node 24 버전으로 업그레이드",
    }
    for action, remediation in deprecated_patterns.items():
        if action in uses:
            add_issue(issues, info, "WARN", f"Node 20 기반 구버전 action 사용 가능성: {action}", remediation)
    node20 = re.search(r"(?m)^\s*node-version:\s*['\"]?20(?:\.\d+)*['\"]?\s*$", text)
    if node20:
        add_issue(issues, info, "WARN", "워크플로 실행 Node가 20으로 고정됨", "node-version을 24로 변경")
    if info["status"] == "OK":
        info["checks"].append("OK: 알려진 Node 20 고정 패턴 없음")


def analyze_file(root: Path, path: Path, issues: list[dict[str, str]]) -> dict[str, Any]:
    rel = path.relative_to(root).as_posix()
    size = path.stat().st_size if path.exists() else 0
    ext = path.suffix.lower()
    info: dict[str, Any] = {
        "path": rel, "size_bytes": size, "size": human_size(size),
        "type": ext.lstrip(".").upper() if ext else "FILE", "status": "OK",
        "purpose": infer_purpose(path), "summary": "", "analysis": "", "checks": [],
    }
    if not path.exists():
        add_issue(issues, info, "ERROR", "Git이 추적하지만 작업트리에 파일이 없음", "체크아웃 상태 확인")
        return info
    if size == 0:
        add_issue(issues, info, "WARN", "빈 파일", "의도된 빈 파일인지 확인")
    if ext in ARCHIVE_EXTENSIONS:
        add_issue(issues, info, "WARN", "압축 아카이브가 저장소에 직접 포함됨", "소스와 중복되는 배포본이라면 Releases/Artifacts로 이동하고 저장소에서는 제거 검토")
        info["summary"] = "압축된 배포/백업 파일"
        info["analysis"] = "아카이브 내부는 결정적 검사에서 직접 실행하지 않음"
        return info
    text: str | None = None
    if ext in TEXT_EXTENSIONS or path.name in {".gitignore", "LICENSE"}:
        text, read_error = safe_read_text(path)
        if read_error:
            add_issue(issues, info, "WARN", read_error, "파일 인코딩/권한 확인")
            return info
    if text is None:
        info["summary"] = infer_purpose(path)
        info["analysis"] = "바이너리/비텍스트 파일: 크기와 경로만 확인"
        return info
    info["summary"] = first_nonempty(text) or info["purpose"]
    if ext == ".py":
        check_python(root, path, text, info, issues)
    elif ext in {".html", ".htm"}:
        check_html(root, path, text, info, issues)
    elif ext == ".md":
        check_markdown(root, path, text, info, issues)
    elif ext == ".json":
        check_json(text, info, issues)
    elif ext in {".yml", ".yaml"} and ".github/workflows/" in f"/{rel}":
        check_yaml_workflow(path, text, info, issues)
    else:
        lines = text.count("\n") + (1 if text else 0)
        info["analysis"] = f"UTF-8 텍스트 {lines}줄"
        info["checks"].append("OK: 텍스트 읽기 통과")
    return info


def escape_cell(value: Any) -> str:
    text = str(value).replace("\n", " ").replace("|", "\\|")
    return re.sub(r"\s+", " ", text).strip()


def render_markdown(root: Path, files: list[dict[str, Any]], issues: list[dict[str, str]]) -> str:
    errors = sum(1 for issue in issues if issue["severity"] == "ERROR")
    warnings = sum(1 for issue in issues if issue["severity"] == "WARN")
    ok_files = sum(1 for item in files if item["status"] == "OK")
    total_size = sum(item["size_bytes"] for item in files)
    lines = [
        "# 저장소 자동 검수 리포트", "",
        "> 이 문서는 `tools/review_repo.py`가 Git 추적 파일을 기준으로 결정적으로 생성합니다.",
        "> AI는 아래 사실을 바꾸지 않고 우선순위와 설명만 정리하도록 설계합니다.", "",
        "## 전체 요약", "", f"- 추적 파일: **{len(files)}개**", f"- 총 크기: **{human_size(total_size)}**",
        f"- 정상 파일: **{ok_files}개**", f"- 오류: **{errors}건**", f"- 경고: **{warnings}건**", "",
    ]
    if issues:
        lines.extend(["## 조치가 필요한 항목", "", "| 등급 | 파일 | 확인 내용 | 권장 조치 |", "|---|---|---|---|"])
        for issue in sorted(issues, key=lambda x: (-status_rank(x["severity"]), x["path"], x["message"])):
            lines.append(f"| {issue['severity']} | `{escape_cell(issue['path'])}` | {escape_cell(issue['message'])} | {escape_cell(issue['action'])} |")
        lines.append("")
    else:
        lines.extend(["## 조치가 필요한 항목", "", "오류와 경고가 없습니다.", ""])
    lines.extend(["## 전체 파일 목록", "", "| 상태 | 파일 | 형식 | 크기 | 역할 요약 |", "|---|---|---:|---:|---|"])
    for item in files:
        lines.append(f"| {item['status']} | `{escape_cell(item['path'])}` | {escape_cell(item['type'])} | {escape_cell(item['size'])} | {escape_cell(item['purpose'])} |")
    lines.extend(["", "## 파일별 요약·분석·설명", ""])
    for item in files:
        lines.extend([
            f"### `{item['path']}`", "", f"- **상태:** {item['status']}", f"- **역할:** {escape_cell(item['purpose'])}",
            f"- **내용 요약:** {escape_cell(item['summary'] or item['purpose'])}", f"- **구조/분석:** {escape_cell(item['analysis'] or '기본 구조 확인')}",
            f"- **검사:** {escape_cell('; '.join(item['checks']) or '추가 검사 없음')}", "",
        ])
    lines.extend([
        "## 판정 기준", "",
        "- **ERROR**: 문법 오류, 깨진 Markdown 로컬 링크처럼 재현 가능한 실패. CI 실패 대상입니다.",
        "- **WARN**: 저장소 공개 품질 또는 향후 호환성에 영향을 줄 수 있으나 즉시 실행 실패는 아닌 항목입니다.",
        "- **OK**: 해당 파일에 적용 가능한 결정적 검사를 통과했습니다.", "",
    ])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="저장소 결정적 검수 및 파일별 설명 리포트 생성")
    parser.add_argument("--report", default="review.md", help="Markdown 리포트 경로")
    parser.add_argument("--json-report", default="", help="선택적 JSON 리포트 경로")
    args = parser.parse_args()
    root = repo_root()
    try:
        paths = tracked_files(root)
    except Exception as exc:
        print(f"ERROR: git 추적 파일 목록을 읽지 못했습니다: {exc}")
        return 2
    issues: list[dict[str, str]] = []
    files = [analyze_file(root, path, issues) for path in paths]
    files.sort(key=lambda item: item["path"].lower())
    report_text = render_markdown(root, files, issues)
    report_path = (root / args.report).resolve()
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(report_text, encoding="utf-8")
    if args.json_report:
        json_path = (root / args.json_report).resolve()
        json_path.parent.mkdir(parents=True, exist_ok=True)
        json_path.write_text(json.dumps({"files": files, "issues": issues}, ensure_ascii=False, indent=2), encoding="utf-8")
    errors = sum(1 for issue in issues if issue["severity"] == "ERROR")
    warnings = sum(1 for issue in issues if issue["severity"] == "WARN")
    print(f"검수 완료: 파일 {len(files)}개 / 오류 {errors}건 / 경고 {warnings}건")
    print(f"Markdown 리포트: {report_path}")
    if args.json_report:
        print(f"JSON 리포트: {(root / args.json_report).resolve()}")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
