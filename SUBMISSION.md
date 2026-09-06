# 채용 제출·면접 준비 가이드

이 문서는 `DAOUTECH_IDC` 저장소를 채용담당자 또는 기술면접관에게 제출하고, 서류 제출 이후 면접까지 기능 상태를 관리하기 위한 기준입니다.

## 1. 제출·면접 전 전체 검증

```bash
python3 tools/review_repo.py --report review.md --json-report review.json
python3 tools/run_analyze.py --manifest portfolio-manifest.json --report execution-report.md --json-report execution-report.json
python3 tools/execute_repo.py --target all --mode functional --report functional-run.md --json-report functional-run.json --log-dir functional-logs
python3 scenario_runner.py scenarios --report scenario-report.md --json-report scenario-report.json
python3 tools/portfolio_manager.py --manifest portfolio-manifest.json --catalog feature-catalog.json --fail-on-blocked
python3 python_server_upgrade.py --target 3.14 --report python-upgrade-report.md --json-report python-upgrade-report.json
python3 tools/summarize_reports.py --review-json review.json --execution-json execution-report.json --functional-json functional-run.json --report deterministic-summary.md --json-report deterministic-summary.json
python3 tools/portfolio_report.py --review review.json --execution execution-report.json --functional functional-run.json --summary deterministic-summary.json --scenarios scenario-report.json --output portfolio-report.html
python3 -m unittest discover -s tests -p 'test_*.py' -v
```

모든 명령이 성공해야 합니다. 로컬 서버에 목표 Python이 아직 설치되지 않은 경우 `python_server_upgrade.py`의 `PLAN_READY`는 정상이며, 실제 변경 직전에는 목표 실행파일을 설치한 뒤 `--strict-target-installed`로 다시 검증합니다.

## 2. 제출·면접 준비 완료 기준

```text
Repository Review       ERROR 0 / WARN 0
Execution Analysis      READY
Functional Execution    PASS
Scenario Regression     PASS
Interview Lifecycle     READY
Python Upgrade Plan     READY / PLAN_READY
Deterministic Summary   READY
Unit Tests              PASS
Cross-platform Tests    PASS (3.12/3.13/3.14)
CodeQL                  PASS
Release Readiness       PASS
```

추가 기준:

- `portfolio-manifest.json`의 제출 필수 파일이 모두 Git 추적 상태
- 모든 Git 추적 파일이 Manifest에 등록되어 Lifecycle 관리 대상
- 모든 Manifest category가 `feature-catalog.json`의 면접 도메인에 분류
- README 로컬 링크 정상
- Python/JSON/HTML JavaScript 문법 정상
- 저장소에 소스와 중복되는 ZIP 없음
- 실제 운영 시스템을 변경하는 테스트 없음
- `interview-readiness.md`의 차단 요소가 없음
- Python 런타임 변경은 in-place 덮어쓰기가 아닌 side-by-side + 신규 venv + Post Check + Rollback 기준을 사용

## 3. 채용담당자·면접관 권장 확인 순서

1. [README.md](README.md) — 프로젝트 전체 목적과 검증 체계
2. [index.html](index.html) — HTML 포트폴리오 통합 시작 화면
3. [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — 운영 기능/검증 계층 관계
4. [docs/INTERVIEW_GUIDE.md](docs/INTERVIEW_GUIDE.md) — 기능별 설명 근거와 예상 기술면접 질문
5. [docs/PYTHON_SERVER_UPGRADE.md](docs/PYTHON_SERVER_UPGRADE.md) — Python 런타임 업그레이드 사전점검·전환·Rollback 기준
6. [docs/FEATURE_LIFECYCLE.md](docs/FEATURE_LIFECYCLE.md) — 기능 등록·업그레이드·릴리스 정책
7. [batch-operations-lab.html](batch-operations-lab.html) — 배치 선후행·Critical Path·SLA
8. [incident-lab.html](incident-lab.html) — 장애 대응 판단
9. [change-management-lab.html](change-management-lab.html) — 변경/사후점검/Rollback
10. [scenario_runner.py](scenario_runner.py) + [scenarios/](scenarios/) — Root Cause·영향·SLA 회귀검증
11. [healthcheck.py](healthcheck.py) — 운영 자동화 코드
12. [python_server_upgrade.py](python_server_upgrade.py) — Python 런타임 변경관리/사전점검 코드
13. [portfolio-manifest.json](portfolio-manifest.json) + [feature-catalog.json](feature-catalog.json) — 전체 파일 역할과 Lifecycle 관리 기준

## 4. 면접 Lifecycle 관리

`tools/portfolio_manager.py`는 `git ls-files`, `portfolio-manifest.json`, `feature-catalog.json`을 비교합니다.

자동 확인 항목:

- Git 추적 파일 중 Manifest 미등록 파일
- Manifest에는 있지만 Git에서 누락된 파일
- 중복 Manifest 경로
- 면접 도메인에 없는 category
- 필수 면접 문서 누락
- 관리 Workflow/도구 누락
- 릴리스 준비 파일 누락
- 도메인별 관리 파일 수
- P0/P1/P2 업그레이드 우선순위
- 예상 기술면접 질문

생성물:

```text
interview-readiness.md/json
feature-inventory.md
upgrade-plan.md
```

Lifecycle 결과가 `BLOCKED`이면 신규 기능을 면접/릴리스 기준으로 완료된 것으로 보지 않습니다.

## 5. Python 서버 업그레이드 검증

`python_server_upgrade.py`는 실제 설치/삭제/서비스 변경을 하지 않고 다음을 검사합니다.

- 현재 Python/실행파일/가상환경
- OS/아키텍처
- 가용 디스크
- 현재 `pip check`
- Git 추적 Python source compile
- 목표 Python executable 존재 여부
- Upgrade/Patch/Downgrade 방향
- side-by-side 설치 계획
- 신규 venv·테스트·서비스 전환 순서
- Post Check / Rollback 계획

전용 `.github/workflows/python-upgrade-readiness.yml`에서는 Ubuntu 또는 Windows와 Python 3.13/3.14를 선택해 목표 런타임을 실제 GitHub Runner에 설치한 뒤 strict precheck를 수행합니다.

업그레이드 완료 판정은 단순 `python --version`만으로 하지 않습니다. 신규 venv, 의존성, compile, unit/functional, 서비스/로그/배치/SLA Post Check까지 확인한 뒤 전환해야 합니다.

## 6. 운영 시나리오 검증 의미

`scenario_runner.py`는 시나리오 JSON에 기록된 이벤트 의존관계를 재귀적으로 추적합니다.

- Root Cause 후보
- 후행 영향 범위
- 장애 심각도
- SLA 위험도
- 기대 결과와 실제 계산 결과 차이

을 계산합니다. 화면이 정상적으로 보이는지만 검사하는 것이 아니라 **운영 판단 규칙이 변경되지 않았는지** 회귀검증하는 목적입니다.

## 7. 교차환경 검증

`.github/workflows/tests.yml`은 다음 6개 조합을 검증합니다.

- Ubuntu + Python 3.12
- Ubuntu + Python 3.13
- Ubuntu + Python 3.14
- Windows + Python 3.12
- Windows + Python 3.13
- Windows + Python 3.14

각 조합에서 Python 전체 compile, unittest, 시나리오 회귀검증과 Python 서버 업그레이드 strict precheck를 수행합니다.

## 8. 보안검사

`.github/workflows/codeql.yml`은 CodeQL로 다음 언어를 검사합니다.

- Python
- JavaScript/TypeScript

CodeQL PASS는 설정된 정적 분석을 통과했다는 의미이며 모든 종류의 보안 문제 부재를 보장한다는 의미로 과장하지 않습니다.

## 9. Dependabot과 업그레이드 정책

`.github/dependabot.yml`은 GitHub Actions와 Python 의존성을 매주 확인합니다.

- minor/patch: 생태계별 그룹 PR
- major: 별도 PR로 분리
- PR이 생성되면 `summary.yml`의 전체 검수와 Lifecycle 검증 실행
- major는 호환성 파괴 가능성이 있으므로 자동 병합 전 실제 검증 결과 확인

기능 자체의 개선 요청은 `.github/ISSUE_TEMPLATE/feature-upgrade.yml`로 표준화할 수 있습니다.

Python 런타임 자체의 minor upgrade는 패키지 Dependabot과 별개로 `.github/workflows/tests.yml` 및 `.github/workflows/python-upgrade-readiness.yml`에서 실제 목표 런타임을 설치해 검증합니다.

## 10. 릴리스 준비·전체 패키징

`.github/workflows/release-readiness.yml`은 수동 실행 또는 `v*` 태그에서 다음을 수행합니다.

1. Repository Review
2. 전체 파일 실행·분석
3. Functional 실행
4. Scenario Regression
5. Interview Lifecycle
6. Unit Test
7. Deterministic Summary
8. HTML Quality Report
9. Git 추적 전체 소스 + 생성된 증거 리포트 Bundle 생성

릴리스 Bundle은 소스 저장소에 ZIP으로 커밋하지 않고 Actions Artifact로 보관합니다.

릴리스 채널:

- `candidate`: 면접 전 검증 스냅샷
- `portfolio-site`: 정적 사이트 배포 준비
- `tagged`: `v*` 태그 기준 재현 패키지

## 11. Pages/정적 사이트

현재 저장소에는 `index.html`과 `.github/workflows/pages-preview.yml`이 있습니다. Pages 설정이 비활성인 동안에는 정적 사이트를 실제 배포하지 않고 `_site`를 검증해 Actions Artifact로 보관합니다.

Pages publishing source가 GitHub Actions로 활성화되면 배포 Workflow로 전환할 수 있습니다.

## 12. 실행 안전 정책

CI에서 금지하는 동작:

- 운영 서버 Python 실제 설치/삭제/덮어쓰기
- 운영 서비스 실제 재기동
- systemd/Windows Service 실제 경로 변경
- 방화벽/네트워크 정책 실제 변경
- 운영 백업 데이터 변경
- 외부 서버 설정 변경

대신:

- Python 업그레이드는 계획/strict precheck와 GitHub Runner 대상 검증만 수행
- 서비스 워치독은 `--dry-run`
- 백업/로그/이력/장애 입력은 임시 샌드박스
- 인증서는 읽기 전용 TLS 확인
- HTML은 문법검사 및 가능한 Runner에서 독립 profile의 headless 로딩

으로 검증합니다.

## 13. 실제 경험과 시뮬레이션 경계

저장소의 품질 판정은 외부 AI를 사용하지 않습니다. 또한 저장소의 시나리오·샘플 데이터·가상 서버명은 실제 고객 데이터를 의미하지 않습니다.

면접에서는 다음을 구분합니다.

```text
실제 운영 관점/경험
        +
안전하게 재현한 포트폴리오 코드/시뮬레이션
        ≠
실제 고객 시스템에 본 저장소를 운영 배포했다는 주장
```

Python Server Upgrade 기능 역시 변경관리 역량을 안전하게 재현한 포트폴리오 기능이며 실제 운영 서버 자동 업그레이드 실적이라고 표현하지 않습니다.

## 14. 생성물

Git에 커밋하지 않고 Actions Artifact에서 확인하는 생성물:

- `review.md/json`
- `execution-report.md/json`
- `functional-run.md/json`
- `scenario-report.md/json`
- `python-upgrade-report.md/json`
- `python-upgrade-test.md/json/txt`
- `deterministic-summary.md/json`
- `portfolio-report.html`
- `interview-readiness.md/json`
- `feature-inventory.md`
- `upgrade-plan.md`
- `unit-test-results.txt`
- 실행 로그 디렉터리
- `release-bundle/`

ZIP 배포본도 소스 저장소에는 커밋하지 않습니다.
