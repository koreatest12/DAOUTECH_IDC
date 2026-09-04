#!/usr/bin/env python3
"""Create a deterministic repository summary without external AI services."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"{path} root must be a JSON object")
    return data


def review_stats(data: dict[str, Any]) -> dict[str, Any]:
    issues = [x for x in data.get("issues", []) if isinstance(x, dict)]
    errors = [x for x in issues if str(x.get("severity", "")).upper() == "ERROR"]
    warnings = [x for x in issues if str(x.get("severity", "")).upper() == "WARN"]
    files = data.get("files", []) if isinstance(data.get("files", []), list) else []
    return {"files": len(files), "errors": len(errors), "warnings": len(warnings), "issues": issues}


def execution_stats(data: dict[str, Any]) -> dict[str, Any]:
    files = [x for x in data.get("files", []) if isinstance(x, dict)]
    checks = [x for x in data.get("submission_checks", []) if isinstance(x, dict)]
    file_errors = [x for x in files if str(x.get("status", "")).upper() == "ERROR"]
    check_errors = [x for x in checks if str(x.get("status", "")).upper() == "ERROR"]
    skipped = [x for x in files if str(x.get("status", "")).upper() == "SKIP"]
    return {
        "files": len(files),
        "errors": len(file_errors) + len(check_errors),
        "skipped": len(skipped),
        "file_errors": file_errors,
        "check_errors": check_errors,
    }


def functional_stats(data: dict[str, Any]) -> dict[str, Any]:
    records = [x for x in data.get("records", []) if isinstance(x, dict)]
    errors = [x for x in records if str(x.get("status", "")).upper() == "ERROR"]
    status = str(data.get("status", "FAIL")).upper()
    return {"records": len(records), "errors": len(errors), "status": status, "error_records": errors}


def issue_lines(review: dict[str, Any], execution: dict[str, Any], functional: dict[str, Any]) -> list[str]:
    lines: list[str] = []
    for item in review["issues"]:
        severity = str(item.get("severity", "INFO")).upper()
        if severity not in {"ERROR", "WARN"}:
            continue
        path = str(item.get("path", "repository"))
        message = str(item.get("message", "issue detected"))
        lines.append(f"- **{severity}** `{path}` — {message}")
    for item in execution["file_errors"]:
        lines.append(f"- **ERROR** `{item.get('path', 'file')}` — {item.get('details', 'execution analysis failed')}")
    for item in execution["check_errors"]:
        lines.append(f"- **ERROR** `{item.get('item', 'submission')}` — {item.get('message', 'submission check failed')}")
    for item in functional["error_records"]:
        lines.append(f"- **ERROR** `{item.get('target', 'functional')}` — {item.get('evidence') or item.get('note') or 'functional execution failed'}")
    return lines[:10]


def render(review: dict[str, Any], execution: dict[str, Any], functional: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    ready = (
        review["errors"] == 0
        and review["warnings"] == 0
        and execution["errors"] == 0
        and functional["errors"] == 0
        and functional["status"] == "PASS"
    )
    findings = issue_lines(review, execution, functional)
    payload = {
        "status": "READY" if ready else "BLOCKED",
        "quality": {"files": review["files"], "errors": review["errors"], "warnings": review["warnings"]},
        "execution": {"files": execution["files"], "errors": execution["errors"], "skipped": execution["skipped"]},
        "functional": {"records": functional["records"], "errors": functional["errors"], "status": functional["status"]},
        "findings": findings,
        "summary_engine": "local-deterministic-python",
        "external_ai_required": False,
    }

    lines = [
        "# DAOUTECH_IDC 결정적 검수 요약",
        "",
        "> 외부 AI/API를 호출하지 않고 저장소가 생성한 JSON 검수 결과만 집계합니다.",
        "",
        "## 최종 판정",
        "",
        f"- 상태: **{payload['status']}**",
        f"- 품질 검수: 파일 **{review['files']}개** / ERROR **{review['errors']}건** / WARN **{review['warnings']}건**",
        f"- 전체 실행·분석: 파일 **{execution['files']}개** / 오류 **{execution['errors']}건** / 생략 **{execution['skipped']}건**",
        f"- Functional 수행: 항목 **{functional['records']}개** / 오류 **{functional['errors']}건** / 결과 **{functional['status']}**",
        "",
        "## 조치 필요 항목",
        "",
    ]
    if findings:
        lines.extend(findings)
    else:
        lines.append("- 없음 — 결정적 검수 기준에서 제출을 막는 오류나 경고가 없습니다.")
    lines += [
        "",
        "## 요약 원칙",
        "",
        "- 사실 판정은 `review.json`, `execution-report.json`, `functional-run.json`만 사용합니다.",
        "- 외부 모델, 네트워크 AI inference, 생성형 요약 서비스에 의존하지 않습니다.",
        "- 동일한 입력 리포트에는 동일한 판정 로직을 적용합니다.",
        "",
    ]
    return "\n".join(lines), payload


def main() -> int:
    parser = argparse.ArgumentParser(description="검수 JSON 3종을 로컬에서 결정적으로 요약")
    parser.add_argument("--review-json", default="review.json")
    parser.add_argument("--execution-json", default="execution-report.json")
    parser.add_argument("--functional-json", default="functional-run.json")
    parser.add_argument("--report", default="deterministic-summary.md")
    parser.add_argument("--json-report", default="deterministic-summary.json")
    args = parser.parse_args()

    try:
        review = review_stats(load_json(ROOT / args.review_json))
        execution = execution_stats(load_json(ROOT / args.execution_json))
        functional = functional_stats(load_json(ROOT / args.functional_json))
        text, payload = render(review, execution, functional)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"요약 생성 실패: {exc}")
        return 2

    (ROOT / args.report).write_text(text, encoding="utf-8")
    (ROOT / args.json_report).write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"결정적 요약 생성: {payload['status']}")
    return 0 if payload["status"] == "READY" else 1


if __name__ == "__main__":
    raise SystemExit(main())
