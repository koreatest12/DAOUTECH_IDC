# IDC 운영 자동화·시뮬레이션 포트폴리오

데이터센터·금융권 IT 인프라 운영 관점에서 반복 점검, 배치 운영, 장애 대응, 변경관리, 백업, 보안, 네트워크 진단, Capacity Planning과 SLA 판단을 Python 도구와 단일 HTML 시뮬레이터로 구현한 포트폴리오입니다.

이 저장소는 **운영 자동화 도구**, **학습·설명용 시뮬레이터**, **자동 테스트/검수 파이프라인**을 구분해 구성합니다. Python 도구는 표준 라이브러리만 사용하며, HTML 도구는 별도 빌드 없이 브라우저에서 실행할 수 있습니다.

## 한눈에 보기

브라우저에서는 [index.html](index.html)을 열면 전체 포트폴리오를 한 화면에서 탐색할 수 있습니다.

- 서버/NOC: `healthcheck.py`, `noc-dashboard.html`, `server-console.html`
- 배치 운영: `batch-operations-lab.html`
- 장애/교대: `incident-lab.html`, `incident_report.py`
- 변경관리: `change-management-lab.html`
- 로그/알람: `log_analyzer.py`, `alert_correlator.py`
- Capacity/SLA: `disk_forecast.py`, `capacity_planner.py`, `sla_calculator.py`
- 백업/인증서: `backup_verify.py`, `backup-simulator.html`, `cert_expiry.py`
- 네트워크/보안: `network-path.html`, `linux-security-lab.html`
- 품질/실행: `tools/review_repo.py`, `tools/run_analyze.py`, `tools/execute_repo.py`, `tools/summarize_reports.py`, `tests/`

## 제출 상태 확인

채용 제출 전에는 다음 다섯 단계를 실행할 수 있습니다.

```bash
python3 tools/review_repo.py --report review.md --json-report review.json
python3 tools/run_analyze.py --manifest portfolio-manifest.json --report execution-report.md --json-report execution-report.json
python3 tools/execute_repo.py --target all --mode functional --report functional-run.md --json-report functional-run.json --log-dir functional-logs
python3 tools/summarize_reports.py --review-json review.json --execution-json execution-report.json --functional-json functional-run.json --report deterministic-summary.md --json-report deterministic-summary.json
python3 -m unittest discover -s tests -p 'test_*.py' -v
```

- `tools/review_repo.py`: 파일 구조, Python/JavaScript/JSON 문법, README 로컬 경로, GitHub Actions 런타임을 검사합니다.
- `tools/run_analyze.py`: 모든 Git 추적 파일을 유형별로 분석하고 제출 필수 파일 누락 여부를 판정합니다.
- `tools/execute_repo.py`: 실행 가능한 Python/HTML을 샌드박스 기반 functional 시나리오로 실제 수행합니다.
- `tools/summarize_reports.py`: 위 검수 JSON 3종을 외부 AI 없이 로컬 Python으로 집계해 최종 `READY/BLOCKED` 요약을 생성합니다.
- `tests/test_portfolio.py`: 핵심 계산, 정규화, 경계조건, 보고서 생성 로직을 `unittest`로 검증합니다.

결과가 `READY`, functional 결과가 `PASS`, unittest가 성공이면 제출 필수 구성과 자동 검증 기준을 만족한 것입니다.

## GitHub Actions

- [통합 검수 워크플로](.github/workflows/summary.yml): push/PR/정기/수동 실행에서 품질검수 → 전체 파일 분석 → functional 실행 → 로컬 결정적 요약 → Artifact 보관을 수행합니다.
- [저장소 파일 실행](.github/workflows/run-files.yml): Actions 화면에서 개별 Python/HTML 또는 `all`, `python`, `html`을 선택해 `smoke`/`functional` 모드로 실행합니다.
- [단위 테스트](.github/workflows/tests.yml): 모든 Python 파일 compile 검사와 `unittest`를 자동 수행합니다.
- [Dependabot](.github/dependabot.yml): GitHub Actions와 향후 Python 의존성을 주기적으로 확인합니다.

### 외부 AI 서비스에 의존하지 않는 이유

GitHub Models는 2026년 7월 30일 종료되어 기존 inference API가 더 이상 제공되지 않습니다. 따라서 이 저장소의 제출 CI는 `actions/ai-inference`, `provider: github-models`, `models: read` 권한을 사용하지 않습니다.

최종 요약은 다음 구조화 결과만 사용합니다.

```text
review.json
      +
execution-report.json
      +
functional-run.json
      ↓
tools/summarize_reports.py
      ↓
deterministic-summary.md / deterministic-summary.json
```

이 구조는 모델 retirement, API brownout, 외부 AI 서비스 장애가 저장소의 품질 판정과 제출 상태에 영향을 주지 않도록 합니다.

## 요구 환경

- Python 3.12 이상
- Node.js 24 이상 — HTML 인라인 JavaScript 자동 문법 검사용
- 브라우저 — HTML 시뮬레이터 실행용

외부 Python 패키지는 필요하지 않습니다. [requirements.txt](requirements.txt)는 이 사실을 명시합니다.

## 포트폴리오 파일 구성

| 파일 | 구분 | 무엇을 보여 주는가 | 실행 방법 |
|---|---|---|---|
| [index.html](index.html) | 포털 | 전체 포트폴리오 통합 시작 화면 | 브라우저로 열기 |
| [noc-dashboard.html](noc-dashboard.html) | 시뮬레이터 | IDC 랙·장비·포트·환경 상태 관제 | 브라우저로 열기 |
| [batch-operations-lab.html](batch-operations-lab.html) | 시뮬레이터 | 배치 선후행·장애 전파·재실행·SLA·Critical Path | 브라우저로 열기 |
| [incident-lab.html](incident-lab.html) | 시뮬레이터 | 장애 조사→원인 판단→조치→보고 흐름 | 브라우저로 열기 |
| [change-management-lab.html](change-management-lab.html) | 시뮬레이터 | 사전점검·변경·사후검증·Rollback 판단 | 브라우저로 열기 |
| [server-console.html](server-console.html) | 시뮬레이터 | 장애 상황별 서버 명령 결과 연동 | 브라우저로 열기 |
| [network-path.html](network-path.html) | 시뮬레이터 | DNS·방화벽·L4·라우팅·MTU 장애 진단 | 브라우저로 열기 |
| [linux-security-lab.html](linux-security-lab.html) | 시뮬레이터 | Linux 권한·로그·방화벽 정책 검토 | 브라우저로 열기 |
| [backup-simulator.html](backup-simulator.html) | 시뮬레이터 | 백업 스케줄·복구체인·장애 주입 | 브라우저로 열기 |
| [healthcheck.py](healthcheck.py) | Python | CPU·메모리·디스크·서비스·네트워크 점검 | `python3 healthcheck.py --help` |
| [log_analyzer.py](log_analyzer.py) | Python | 로그 정규화·오류 집계·급증 탐지 | `python3 log_analyzer.py --help` |
| [alert_correlator.py](alert_correlator.py) | Python | 다중 알람을 Incident/Root Cause 후보로 상관분석 | `python3 alert_correlator.py --help` |
| [disk_forecast.py](disk_forecast.py) | Python | 디스크 임계 도달 시점 예측 | `python3 disk_forecast.py --help` |
| [capacity_planner.py](capacity_planner.py) | Python | CPU·메모리·디스크 증설 시점 예측 | `python3 capacity_planner.py --help` |
| [sla_calculator.py](sla_calculator.py) | Python | SLA별 허용 장애시간과 실제 가용성 판정 | `python3 sla_calculator.py --help` |
| [svc_watchdog.py](svc_watchdog.py) | Python | 서비스 정지 감지와 제한적 재기동 정책 | `python3 svc_watchdog.py --help` |
| [backup_verify.py](backup_verify.py) | Python | 백업 존재·크기·신선도·SHA-256 검증 | `python3 backup_verify.py --help` |
| [cert_expiry.py](cert_expiry.py) | Python | TLS 인증서 만료 사전 점검 | `python3 cert_expiry.py --help` |
| [incident_report.py](incident_report.py) | Python | 장애보고서·타임라인·교대 인수인계 생성 | `python3 incident_report.py --help` |
| [tools/summarize_reports.py](tools/summarize_reports.py) | 품질 | 검수 결과의 외부 AI 비의존 최종 요약 | `python3 tools/summarize_reports.py --help` |

지원 파일은 [check.json](check.json), [domains.txt](domains.txt), [portfolio-manifest.json](portfolio-manifest.json)입니다.

## 핵심 설계 의도

### 1. 서버 점검은 사람이 읽기 전에 종료 코드로 판정

`healthcheck.py`는 호스트 정보, 업타임, CPU, 메모리, 파일시스템, 서비스, 네트워크를 확인하고 `0 정상 / 1 주의 / 2 조치 필요`로 결과를 반환합니다. 스케줄러나 상위 자동화가 결과를 기계적으로 판단할 수 있게 하는 것이 핵심입니다.

### 2. 배치는 Job 하나가 아니라 선후행과 마감 영향으로 판단

`batch-operations-lab.html`은 독립 Job은 계속 진행하고 실패 Job의 후행만 차단합니다. 재실행 후 후행을 다시 계산하고, Critical Path와 SLA 여유시간이 어떻게 달라지는지 보여 줍니다.

### 3. 알람 수보다 Root Cause 후보를 먼저 찾기

`alert_correlator.py`는 여러 Host에서 연쇄적으로 발생한 알람을 시간 창과 상위 의존성 기준으로 묶어 Incident 수를 줄입니다. DB 디스크 문제로 APP 지연과 배치 지연이 함께 발생한 경우 각각의 알람이 아니라 하나의 원인 후보로 보는 흐름입니다.

### 4. 변경은 작업보다 사전점검과 Rollback 기준이 중요

`change-management-lab.html`은 변경 요청, 영향도 분석, 백업, 사전 Health Check, 적용, 사후 검증, 실패 시 Rollback을 하나의 절차로 다룹니다.

### 5. 장애 대응 결과는 인수인계 가능한 기록으로 남기기

`incident_report.py`는 장애 발생/종료 시각, 영향, 원인, 타임라인, 조치, 재발 방지, 다음 확인 시각을 Markdown 보고서로 만듭니다.

### 6. 임계 초과 후 대응보다 Capacity/SLA를 미리 계산

`capacity_planner.py`는 일별 CPU·메모리·디스크 이력의 기울기로 임계 도달 예상 시점을 계산합니다. `sla_calculator.py`는 99.9/99.95/99.99% 같은 목표별 허용 장애시간과 실제 가용성을 계산합니다.

## 자동 검증 방식

1. 모든 Python 파일을 AST로 파싱합니다.
2. argparse 기반 CLI는 `--help`로 엔트리포인트 로딩을 확인합니다.
3. 모든 HTML 인라인 JavaScript를 Node 24 `node --check`로 검사합니다.
4. functional 실행에서는 안전한 임시 입력을 만들어 실제 CLI 로직을 수행합니다.
5. HTML은 가능한 Runner에서 headless 브라우저로 실제 문서를 로딩합니다.
6. JSON 파일을 실제 파싱합니다.
7. Markdown 로컬 링크와 저장소 경로를 확인합니다.
8. `portfolio-manifest.json`의 제출 필수 파일이 Git에 추적되는지 확인합니다.
9. `unittest`에서 기존/신규 도구의 핵심 함수와 경계조건을 검증합니다.
10. 검수 JSON 3종을 `tools/summarize_reports.py`가 로컬에서 집계합니다.
11. 소스와 중복되는 ZIP은 저장소에 커밋하지 않고 Actions Artifact/Release로 분리합니다.

## 안전 실행 정책

CI는 실제 운영 시스템을 변경하지 않습니다.

- `svc_watchdog.py`는 functional 검증에서 항상 `--dry-run`을 사용합니다.
- 백업 파일, 디스크 이력, 장애 입력, 알람 입력은 임시 샌드박스에 생성합니다.
- 인증서 검사는 읽기 전용 TLS 연결만 수행합니다.
- 외부 서버 설정, 방화벽, 실제 백업 데이터, 운영 서비스 재기동은 자동 실행하지 않습니다.

## 경험과 학습 범위 구분

**운영 경험을 바탕으로 구현한 영역**은 서버·네트워크 모니터링, 장애 1차 대응과 에스컬레이션 판단, 배치 선후행/마감 관리, 백업 결과 확인, Linux/Windows 서버 상태 조회, 변경 작업 전후 확인과 교대 인수인계 관점입니다.

**학습·확장 목적으로 구현한 영역**에는 방화벽 정책 설계, DNS 장애 시나리오, 인증서 발급·갱신, 항온항습 계통 등 실제 담당 범위를 넘어서는 주제가 포함됩니다. 해당 영역은 실무 경험으로 과장하지 않고 학습/시뮬레이션 범위로 구분합니다.

## 생성형 AI 활용 원칙

코드 작성과 정리 과정에서 생성형 AI를 보조 도구로 활용할 수 있지만, 저장소의 사실 판정과 CI 성공 여부에는 외부 AI 서비스를 사용하지 않습니다. 품질 판정은 `review_repo.py`, `run_analyze.py`, `execute_repo.py`, `summarize_reports.py`, `unittest`의 결정적 결과만 사용합니다.

## 라이선스

라이선스 조건은 [LICENSE](LICENSE)를 확인해 주세요.
