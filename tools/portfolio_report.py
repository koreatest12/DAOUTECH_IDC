#!/usr/bin/env python3
"""검수·실행·시나리오 결과를 standalone HTML 포트폴리오 리포트로 통합합니다."""

from __future__ import annotations

import argparse
import html
import json
from pathlib import Path
from typing import Any


def load(path: str) -> dict[str, Any]:
    p = Path(path)
    if not p.exists():
        return {}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def count_review(review: dict[str, Any]) -> tuple[int, int, int]:
    files = review.get("files", []) if isinstance(review.get("files", []), list) else []
    issues = review.get("issues", []) if isinstance(review.get("issues", []), list) else []
    errors = sum(str(i.get("severity", "")).upper() == "ERROR" for i in issues if isinstance(i, dict))
    warnings = sum(str(i.get("severity", "")).upper() == "WARN" for i in issues if isinstance(i, dict))
    return len(files), errors, warnings


def count_execution(data: dict[str, Any]) -> tuple[int, int, int]:
    records = data.get("files", []) if isinstance(data.get("files", []), list) else []
    checks = data.get("submission_checks", []) if isinstance(data.get("submission_checks", []), list) else []
    errors = sum(str(r.get("status", "")).upper() == "ERROR" for r in records if isinstance(r, dict))
    errors += sum(str(r.get("status", "")).upper() == "ERROR" for r in checks if isinstance(r, dict))
    skipped = sum(str(r.get("status", "")).upper() == "SKIP" for r in records if isinstance(r, dict))
    return len(records), errors, skipped


def count_functional(data: dict[str, Any]) -> tuple[int, int, str]:
    records = data.get("records", []) if isinstance(data.get("records", []), list) else []
    errors = sum(str(r.get("status", "")).upper() == "ERROR" for r in records if isinstance(r, dict))
    return len(records), errors, str(data.get("status", "UNKNOWN"))


def badge(status: str) -> str:
    status = status.upper()
    cls = "ok" if status in {"PASS", "READY", "SUCCESS", "OK"} else "bad" if status in {"FAIL", "BLOCKED", "ERROR"} else "warn"
    return f'<span class="badge {cls}">{html.escape(status)}</span>'


def card(title: str, value: str, sub: str, status: str) -> str:
    return f'''<article class="card"><div class="card-title">{html.escape(title)}</div>
    <div class="card-value">{html.escape(value)}</div><div>{badge(status)}</div>
    <div class="card-sub">{html.escape(sub)}</div></article>'''


def render(review: dict[str, Any], execution: dict[str, Any], functional: dict[str, Any],
           summary: dict[str, Any], scenarios: dict[str, Any]) -> str:
    rf, re, rw = count_review(review)
    ef, ee, es = count_execution(execution)
    ff, fe, fs = count_functional(functional)
    overall = str(summary.get("status", "READY" if not (re or rw or ee or fe) else "BLOCKED"))
    scenario_results = scenarios.get("results", []) if isinstance(scenarios.get("results", []), list) else []
    scenario_status = str(scenarios.get("status", "N/A"))
    scenario_fail = sum(str(x.get("status", "")).upper() == "FAIL" for x in scenario_results if isinstance(x, dict))

    rows = []
    for item in scenario_results:
        if not isinstance(item, dict):
            continue
        rows.append(
            "<tr>"
            f"<td>{badge(str(item.get('status','UNKNOWN')))}</td>"
            f"<td>{html.escape(str(item.get('scenario_id','')))}</td>"
            f"<td>{html.escape(str(item.get('title','')))}</td>"
            f"<td><code>{html.escape(str(item.get('root_cause','')))}</code></td>"
            f"<td>{html.escape(str(item.get('severity','')))}</td>"
            f"<td>{html.escape(str(item.get('sla_risk','')))}</td>"
            "</tr>"
        )

    return f'''<!doctype html>
<html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>DAOUTECH_IDC Quality Report</title>
<style>
:root{{--bg:#07111f;--panel:#101d2f;--line:#233751;--text:#edf5ff;--muted:#9fb2c8;--ok:#46d39a;--bad:#ff6b7d;--warn:#ffca62}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--text);font:15px/1.55 system-ui,-apple-system,Segoe UI,sans-serif}}
main{{max-width:1180px;margin:auto;padding:42px 22px 70px}}h1{{font-size:34px;margin:0 0 8px}}h2{{margin-top:38px}}p{{color:var(--muted)}}
.hero{{border:1px solid var(--line);background:linear-gradient(135deg,#10243d,#0b1726);padding:28px;border-radius:18px}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:14px;margin-top:20px}}.card{{background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:18px}}
.card-title,.card-sub{{color:var(--muted)}}.card-value{{font-size:30px;font-weight:750;margin:5px 0}}.badge{{display:inline-block;padding:3px 9px;border-radius:999px;font-size:12px;font-weight:750}}
.badge.ok{{background:#123e32;color:var(--ok)}}.badge.bad{{background:#4b1e28;color:var(--bad)}}.badge.warn{{background:#453817;color:var(--warn)}}
table{{width:100%;border-collapse:collapse;background:var(--panel);border:1px solid var(--line);border-radius:12px;overflow:hidden}}th,td{{padding:10px 12px;border-bottom:1px solid var(--line);text-align:left}}th{{color:var(--muted)}}code{{color:#b8d8ff}}
.footer{{margin-top:36px;color:var(--muted);font-size:13px}}@media(max-width:700px){{table{{font-size:12px}}th,td{{padding:7px}}}}
</style></head><body><main>
<section class="hero"><h1>IDC Operations Portfolio · Quality Report</h1>
<p>외부 AI 없이 저장소의 결정적 검사 결과를 통합한 제출용 품질 리포트입니다.</p>
<div>{badge(overall)}</div></section>
<div class="grid">
{card('Repository Quality', f'{rf} files', f'ERROR {re} · WARN {rw}', 'PASS' if not (re or rw) else 'FAIL')}
{card('Execution Analysis', f'{ef} files', f'ERROR {ee} · SKIP {es}', 'PASS' if not ee else 'FAIL')}
{card('Functional Run', f'{ff} checks', f'ERROR {fe}', fs)}
{card('Scenario Validation', f'{len(scenario_results)} scenarios', f'FAIL {scenario_fail}', scenario_status)}
</div>
<h2>운영 시나리오 검증</h2>
<table><thead><tr><th>상태</th><th>ID</th><th>시나리오</th><th>Root Cause</th><th>심각도</th><th>SLA</th></tr></thead><tbody>{''.join(rows) if rows else '<tr><td colspan="6">시나리오 결과 없음</td></tr>'}</tbody></table>
<h2>검증 체계</h2><p>Repository Review → 전체 파일 분석 → Functional Execution → Scenario Validation → Deterministic Summary 순으로 검증합니다. 운영 영향이 있는 서비스 재기동과 실제 백업 변경은 수행하지 않습니다.</p>
<div class="footer">Generated by <code>tools/portfolio_report.py</code> · Standard library only</div>
</main></body></html>'''


def main() -> int:
    ap = argparse.ArgumentParser(description="DAOUTECH_IDC 통합 HTML 품질 리포트")
    ap.add_argument("--review", default="review.json")
    ap.add_argument("--execution", default="execution-report.json")
    ap.add_argument("--functional", default="functional-run.json")
    ap.add_argument("--summary", default="deterministic-summary.json")
    ap.add_argument("--scenarios", default="scenario-report.json")
    ap.add_argument("--output", default="portfolio-report.html")
    args = ap.parse_args()
    content = render(load(args.review), load(args.execution), load(args.functional), load(args.summary), load(args.scenarios))
    Path(args.output).write_text(content, encoding="utf-8")
    print(f"통합 리포트 생성: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
