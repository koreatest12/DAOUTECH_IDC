#!/usr/bin/env python3
"""Deterministic interview/release lifecycle manager for the whole repository."""

from __future__ import annotations

import argparse
import json
import subprocess
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} root must be an object")
    return data


def tracked_files(root: Path) -> set[str]:
    proc = subprocess.run(["git", "ls-files", "-z"], cwd=root, capture_output=True)
    if proc.returncode != 0:
        raise RuntimeError("git ls-files failed")
    return {p.decode("utf-8", errors="strict") for p in proc.stdout.split(b"\0") if p}


def domain_map(catalog: dict[str, Any]) -> dict[str, dict[str, str]]:
    result: dict[str, dict[str, str]] = {}
    for domain in catalog.get("domains", []):
        if not isinstance(domain, dict):
            continue
        for category in domain.get("categories", []):
            result[str(category)] = {
                "id": str(domain.get("id", "unknown")),
                "name": str(domain.get("name", "미분류")),
                "interview_focus": str(domain.get("interview_focus", "")),
            }
    return result


def requirement_score(tracked: set[str], required: list[str], weight: int) -> tuple[int, list[str]]:
    required = [str(x) for x in required]
    missing = [p for p in required if p not in tracked]
    if not required:
        return weight, missing
    present = len(required) - len(missing)
    return round(weight * present / len(required)), missing


def evaluate(manifest: dict[str, Any], catalog: dict[str, Any], tracked: set[str]) -> dict[str, Any]:
    items = [x for x in manifest.get("files", []) if isinstance(x, dict) and x.get("path")]
    manifest_paths = [str(x["path"]) for x in items]
    counts = Counter(manifest_paths)
    duplicates = sorted(p for p, count in counts.items() if count > 1)
    manifest_set = set(manifest_paths)
    unregistered = sorted(tracked - manifest_set)
    missing_tracked = sorted(manifest_set - tracked)

    domains = domain_map(catalog)
    unknown_categories = sorted({str(x.get("category", "")) for x in items if str(x.get("category", "")) not in domains})
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in items:
        category = str(item.get("category", ""))
        domain = domains.get(category, {"id": "unknown", "name": "미분류", "interview_focus": ""})
        grouped[domain["id"]].append({
            "path": str(item["path"]),
            "category": category,
            "purpose": str(item.get("purpose", "")),
            "domain_name": domain["name"],
            "interview_focus": domain["interview_focus"],
        })

    req = catalog.get("readiness_requirements", {})
    documentation_score, doc_missing = requirement_score(tracked, list(req.get("documentation", [])), 20)
    automation_score, automation_missing = requirement_score(tracked, list(req.get("automation", [])), 20)
    release_score, release_missing = requirement_score(tracked, list(req.get("release", [])), 10)

    coverage_issues = len(unregistered) + len(missing_tracked) + len(duplicates) + len(unknown_categories)
    coverage_score = max(0, 35 - coverage_issues * 5)
    expected_domains = [str(x.get("id")) for x in catalog.get("domains", []) if isinstance(x, dict)]
    empty_domains = [d for d in expected_domains if not grouped.get(d)]
    domain_score = round(15 * (len(expected_domains) - len(empty_domains)) / len(expected_domains)) if expected_domains else 15
    score = coverage_score + documentation_score + automation_score + domain_score + release_score

    blockers: list[str] = []
    if unregistered:
        blockers.append(f"manifest 미등록 추적 파일 {len(unregistered)}개")
    if missing_tracked:
        blockers.append(f"manifest 등록 후 누락 파일 {len(missing_tracked)}개")
    if duplicates:
        blockers.append(f"manifest 중복 경로 {len(duplicates)}개")
    if unknown_categories:
        blockers.append(f"feature catalog 미분류 category {len(unknown_categories)}개")
    if doc_missing:
        blockers.append(f"면접 문서 요구사항 누락 {len(doc_missing)}개")
    if automation_missing:
        blockers.append(f"관리 자동화 요구사항 누락 {len(automation_missing)}개")
    if release_missing:
        blockers.append(f"릴리스 관리 요구사항 누락 {len(release_missing)}개")
    if empty_domains:
        blockers.append(f"비어 있는 관리 도메인 {len(empty_domains)}개")

    status = "READY" if score >= 90 and not blockers else "BLOCKED"
    backlog = sorted(
        [x for x in catalog.get("upgrade_backlog", []) if isinstance(x, dict)],
        key=lambda x: ({"P0": 0, "P1": 1, "P2": 2}.get(str(x.get("priority")), 9), str(x.get("id", ""))),
    )
    return {
        "status": status,
        "score": score,
        "tracked_count": len(tracked),
        "registered_count": len(manifest_set),
        "unregistered": unregistered,
        "missing_tracked": missing_tracked,
        "duplicates": duplicates,
        "unknown_categories": unknown_categories,
        "missing_requirements": {
            "documentation": doc_missing,
            "automation": automation_missing,
            "release": release_missing,
        },
        "empty_domains": empty_domains,
        "domains": grouped,
        "backlog": backlog,
        "question_bank": [str(x) for x in catalog.get("interview_question_bank", [])],
        "score_breakdown": {
            "manifest_coverage": coverage_score,
            "documentation": documentation_score,
            "automation": automation_score,
            "domain_coverage": domain_score,
            "release": release_score,
        },
        "blockers": blockers,
    }


def render_readiness(result: dict[str, Any]) -> str:
    lines = [
        "# 면접 대비 포트폴리오 Lifecycle 리포트",
        "",
        "> 저장소의 사실을 자동 집계한 결정적 관리 리포트입니다. 실제 운영 경험과 시뮬레이션 범위는 README/INTERVIEW_GUIDE의 경계를 따릅니다.",
        "",
        "## 최종 판정",
        "",
        f"- 상태: **{result['status']}**",
        f"- 면접/릴리스 준비 점수: **{result['score']}/100**",
        f"- Git 추적 파일: **{result['tracked_count']}개**",
        f"- Manifest 등록 파일: **{result['registered_count']}개**",
        "",
        "### 점수 구성",
        "",
        "| 항목 | 점수 |",
        "|---|---:|",
    ]
    for key, value in result["score_breakdown"].items():
        lines.append(f"| {key} | {value} |")
    lines += ["", "## 차단 요소", ""]
    lines += [f"- {x}" for x in result["blockers"]] or ["- 없음"]
    lines += ["", "## 도메인별 면접 준비", ""]
    for domain_id, items in result["domains"].items():
        if not items:
            continue
        lines += [f"### {items[0]['domain_name']} (`{domain_id}`)", "", items[0]["interview_focus"], "", f"관리 파일: **{len(items)}개**", ""]
    lines += ["## 다음 업그레이드 우선순위", ""]
    for item in result["backlog"]:
        lines.append(f"- **{item.get('priority')} {item.get('id')}** · {item.get('objective')} — 완료 기준: {item.get('exit_criteria')}")
    lines += ["", "## 예상 기술면접 질문", ""]
    for idx, question in enumerate(result["question_bank"], 1):
        lines.append(f"{idx}. {question}")
    lines.append("")
    return "\n".join(lines)


def render_inventory(result: dict[str, Any]) -> str:
    lines = [
        "# 전체 기능 인벤토리",
        "",
        "| 도메인 | Category | 파일 | 목적 |",
        "|---|---|---|---|",
    ]
    rows: list[dict[str, Any]] = []
    for items in result["domains"].values():
        rows.extend(items)
    for item in sorted(rows, key=lambda x: x["path"]):
        purpose = item["purpose"].replace("|", "\\|")
        lines.append(f"| {item['domain_name']} | `{item['category']}` | `{item['path']}` | {purpose} |")
    lines += ["", "## 등록 이상", "", f"- Manifest 미등록: {', '.join(result['unregistered']) if result['unregistered'] else '없음'}", f"- 추적 누락: {', '.join(result['missing_tracked']) if result['missing_tracked'] else '없음'}", f"- 미분류 Category: {', '.join(result['unknown_categories']) if result['unknown_categories'] else '없음'}", ""]
    return "\n".join(lines)


def render_upgrade_plan(result: dict[str, Any]) -> str:
    lines = ["# 업그레이드·출시 관리 계획", "", "| 우선순위 | ID | 대상 | 목표 | 완료 기준 |", "|---|---|---|---|---|"]
    for item in result["backlog"]:
        lines.append(f"| {item.get('priority')} | {item.get('id')} | {item.get('target')} | {item.get('objective')} | {item.get('exit_criteria')} |")
    lines += ["", "## 관리 규칙", "", "1. 새 기능은 Manifest와 Feature Catalog 관리 범위에 포함합니다.", "2. 기능 변경은 compile/unit/functional/scenario/CodeQL 중 관련 검증을 통과해야 합니다.", "3. major 의존성 업데이트는 별도 PR로 검토합니다.", "4. 릴리스 후보는 release-readiness Workflow가 생성한 Artifact를 사용합니다.", "5. 실제 운영 경험과 시뮬레이션 결과를 면접에서 혼동해 설명하지 않습니다.", ""]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="DAOUTECH_IDC 면접/릴리스 Lifecycle 관리자")
    parser.add_argument("--manifest", default="portfolio-manifest.json")
    parser.add_argument("--catalog", default="feature-catalog.json")
    parser.add_argument("--readiness-report", default="interview-readiness.md")
    parser.add_argument("--json-report", default="interview-readiness.json")
    parser.add_argument("--inventory-report", default="feature-inventory.md")
    parser.add_argument("--upgrade-report", default="upgrade-plan.md")
    parser.add_argument("--fail-on-blocked", action="store_true")
    args = parser.parse_args()

    manifest = load_json(ROOT / args.manifest)
    catalog = load_json(ROOT / args.catalog)
    result = evaluate(manifest, catalog, tracked_files(ROOT))
    (ROOT / args.readiness_report).write_text(render_readiness(result), encoding="utf-8")
    (ROOT / args.inventory_report).write_text(render_inventory(result), encoding="utf-8")
    (ROOT / args.upgrade_report).write_text(render_upgrade_plan(result), encoding="utf-8")
    (ROOT / args.json_report).write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Lifecycle 관리 완료: tracked={result['tracked_count']} registered={result['registered_count']} score={result['score']} status={result['status']}")
    if result["blockers"]:
        for blocker in result["blockers"]:
            print(f"BLOCKER: {blocker}")
    return 1 if args.fail_on_blocked and result["status"] != "READY" else 0


if __name__ == "__main__":
    raise SystemExit(main())
