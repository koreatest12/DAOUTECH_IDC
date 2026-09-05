# IDC 운영 자동화·시뮬레이션 포트폴리오

데이터센터·금융권 IT 인프라 운영 관점에서 서버 점검, 배치 운영, 장애 대응, 변경관리, 백업, 네트워크·보안, Capacity Planning과 SLA 판단을 **Python 운영 도구 + 단일 HTML 시뮬레이터 + 결정적 CI 검증**으로 구현한 포트폴리오입니다.

실제 운영 경험을 바탕으로 한 영역과 학습·확장 시뮬레이션 영역을 구분하며, 실제 회사·고객의 서버명·IP·로그·업무 데이터는 포함하지 않습니다.

## 핵심 포인트

- **운영 자동화**: Health Check, 로그 분석, 알람 상관분석, 백업 검증, 인증서, Capacity/SLA
- **배치 운영**: 선후행, Critical Path, 재실행, 마감/SLA 영향
- **장애 대응**: 원인 후보 → 영향 범위 → 조치 → 보고서 → 교대 인수인계
- **변경관리**: 사전점검 → 변경 → Post Check → Rollback 판단
- **운영 시나리오 회귀검증**: Root Cause·후행 영향·SLA 위험을 계산해 기대값과 대조
- **교차환경 테스트**: Ubuntu/Windows × Python 3.12/3.13
- **보안검사**: CodeQL Python + JavaScript/TypeScript
- **외부 AI 비의존**: 결과 판정과 요약은 로컬 결정적 Python 검사기로 수행

브라우저에서는 [index.html](index.html)을 열어 전체 HTML 포트폴리오를 탐색할 수 있습니다.

## 아키텍처와 Runbook

- [Architecture](docs/ARCHITECTURE.md) — 운영 기능과 검증 파이프라인 구조
- [Operations Runbook](docs/RUNBOOK.md) — 장애·배치·변경·백업·네트워크 상황별 판단 순서
- [Submission Guide](SUBMISSION.md) — 채용 제출 전 검증 기준

## 전체 제출 검증

```bash
python3 tools/review_repo.py --report review.md --json-report review.json
python3 tools/run_analyze.py --manifest portfolio-manifest.json --report execution-report.md --json-report execution-report.json
python3 tools/execute_repo.py --target all --mode functional --report functional-run.md --json-report functional-run.json --log-dir functional-logs
python3 scenario_runner.py scenarios --report scenario-report.md --json-report scenario-report.json
python3 tools/summarize_reports.py --review-json review.json --execution-json execution-report.json --functional-json functional-run.json --report deterministic-summary.md --json-report deterministic-summary.json
python3 tools/portfolio_report.py --review review.json --execution execution-report.json --functional functional-run.json --summary deterministic-summary.json --scenarios scenario-report.json --output portfolio-report.html
python3 -m unittest discover -s tests -p 'test_*.py' -v
```

정상 제출 기준은 다음과 같습니다.

```text
Repository Review       PASS
Execution Analysis      READY
Functional Execution    PASS
Scenario Regression     PASS
Deterministic Summary   READY
Unit Tests              PASS
CodeQL                  PASS
```

## 운영 시나리오 Runner

`scenario_runner.py`는 단순 JSON 출력기가 아니라 이벤트 의존관계를 재귀적으로 추적합니다.

```text
Root Event
   ↓
Dependent Event
   ↓
Service / Batch / NOC impact
   ↓
Affected Range
   ↓
SLA Risk
   ↓
Expected Result Comparison
```

현재 시나리오:

| 파일 | 시나리오 |
|---|---|
| [SCN-001](scenarios/001-db-disk-capacity.json) | DB 디스크 포화 → DB 지연 → APP/배치/NOC 영향 |
| [SCN-002](scenarios/002-batch-critical-path.json) | 선행 Job 실패 → Critical Path 마감 위험 |
| [SCN-003](scenarios/003-backup-integrity.json) | 백업 SHA-256 불일치 → 복구 신뢰성 저하 |
| [SCN-004](scenarios/004-dns-path-failure.json) | DNS 장애 → APP/배치 연결 장애 |
| [SCN-005](scenarios/005-change-rollback.json) | 변경 후 Post Check 실패 → Rollback 판단 |

시나리오 JSON의 `expected`와 계산 결과가 달라지면 회귀 실패로 처리됩니다.

## 통합 품질 리포트

`tools/portfolio_report.py`는 다음 결과를 하나의 standalone HTML로 통합합니다.

- 저장소 품질검사 파일 수 / ERROR / WARN
- 전체 실행분석 ERROR / SKIP
- Functional 수행 항목 / 오류
- 시나리오 PASS/FAIL
- 시나리오별 Root Cause / Severity / SLA Risk
- 최종 READY/BLOCKED 상태

생성 파일:

```text
portfolio-report.html
```

브라우저만 있으면 별도 서버 없이 열 수 있습니다.

## GitHub Actions

| Workflow | 목적 |
|---|---|
| [통합 제출 검수](.github/workflows/summary.yml) | Review → Analyze → Functional → Scenario → Summary → HTML Report |
| [교차환경 테스트](.github/workflows/tests.yml) | Ubuntu/Windows × Python 3.12/3.13 compile/unittest/scenario |
| [CodeQL](.github/workflows/codeql.yml) | Python / JavaScript 정적 보안 분석 |
| [Pages 준비](.github/workflows/pages-preview.yml) | 정적 사이트 검증 후 배포 가능한 `_site` Artifact 생성 |
| [개별 파일 실행](.github/workflows/run-files.yml) | Python/HTML 개별 smoke/functional 실행 |
| [Dependabot](.github/dependabot.yml) | GitHub Actions/Python 의존성 변경 감시 |

### GitHub Pages 상태

저장소에는 `index.html`과 정적 사이트 검증 Workflow가 준비되어 있습니다. 현재 GitHub Pages 저장소 설정이 비활성 상태이므로 CI가 실패하지 않도록 자동 배포 대신 **Pages-ready Artifact**를 생성합니다. Pages publishing source를 GitHub Actions로 활성화하면 공식 Pages Actions(`configure-pages`, `upload-pages-artifact`, `deploy-pages`) 구조로 바로 전환할 수 있습니다.

## 포트폴리오 구성

### HTML 시뮬레이터

- [NOC Dashboard](noc-dashboard.html)
- [Batch Operations Lab](batch-operations-lab.html)
- [Incident Lab](incident-lab.html)
- [Change Management Lab](change-management-lab.html)
- [Server Console](server-console.html)
- [Network Path Lab](network-path.html)
- [Linux Security Lab](linux-security-lab.html)
- [Backup Simulator](backup-simulator.html)

### Python 운영 도구

| 파일 | 핵심 기능 |
|---|---|
| `healthcheck.py` | CPU·메모리·디스크·서비스·네트워크 Health Check |
| `log_analyzer.py` | 로그 정규화·오류 유형 집계·급증 탐지 |
| `alert_correlator.py` | 다중 알람을 Incident/Root Cause 후보로 상관분석 |
| `disk_forecast.py` | 디스크 임계 도달 시점 예측 |
| `capacity_planner.py` | CPU·메모리·디스크 Capacity 예측 |
| `sla_calculator.py` | SLA별 허용 장애시간·실제 가용성 판정 |
| `svc_watchdog.py` | 서비스 정지 감지·재기동 상한/백오프 정책 |
| `backup_verify.py` | 존재·크기·신선도·SHA-256 백업 검증 |
| `cert_expiry.py` | TLS 인증서 만료 사전 확인 |
| `incident_report.py` | 장애보고서·타임라인·교대 인수인계 생성 |
| `scenario_runner.py` | 운영 시나리오 Root Cause·영향·SLA 회귀 검증 |

## 자동 검증 원칙

1. 모든 Python을 AST/compile 방식으로 확인합니다.
2. argparse CLI는 `--help`로 실제 엔트리포인트를 로딩합니다.
3. HTML 인라인 JavaScript는 Node 24 `node --check`로 검사합니다.
4. Functional 검증은 임시 fixture와 sandbox를 이용해 실제 로직을 수행합니다.
5. 가능한 GitHub Runner에서는 HTML을 headless 브라우저로 실제 로딩합니다.
6. 모든 JSON을 실제 파싱합니다.
7. README 로컬 링크와 제출 필수 경로를 확인합니다.
8. 운영 시나리오는 Root Cause/영향/SLA 예상값과 실제 결과를 대조합니다.
9. Ubuntu/Windows에서 Python 핵심 로직을 교차 검증합니다.
10. CodeQL로 Python/JavaScript 정적 보안 분석을 수행합니다.
11. 외부 AI 서비스 상태는 품질 판정에 영향을 주지 않습니다.

## 안전 실행 정책

CI는 실제 운영 시스템을 변경하지 않습니다.

- 서비스 워치독은 Functional 검증에서 `--dry-run`만 사용합니다.
- 백업·이력·장애·알람 입력은 임시 샌드박스에 생성합니다.
- 인증서 검사는 읽기 전용 TLS 연결만 수행합니다.
- 실제 서버 설정 변경, 방화벽 정책 적용, 운영 서비스 재기동, 실제 백업 변경은 CI에서 실행하지 않습니다.

## 경험과 학습 범위

**운영 경험을 바탕으로 구현한 영역**은 서버·네트워크 모니터링, 장애 1차 대응/에스컬레이션 판단, 배치 선후행·마감 관리, 백업 결과 확인, Linux/Windows 상태 조회, 변경 전후 확인, 교대 인수인계 관점입니다.

**학습·확장 시뮬레이션 영역**에는 실제 담당 범위를 넘어서는 방화벽 정책 설계, DNS 세부 장애, 인증서 발급/갱신, 환경 설비 시나리오 등이 포함될 수 있으며 실무 경험으로 과장하지 않습니다.

## 요구 환경

- Python 3.12 이상
- Node.js 24 이상
- HTML 실행용 브라우저
- Python 외부 패키지 없음

## 라이선스

[Apache License 2.0](LICENSE)
