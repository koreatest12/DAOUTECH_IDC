# 채용 제출 가이드

이 문서는 `DAOUTECH_IDC` 저장소를 채용담당자 또는 기술면접관에게 제출하기 전에 확인할 기준입니다.

## 1. 제출 전 전체 검증

```bash
python3 tools/review_repo.py --report review.md --json-report review.json
python3 tools/run_analyze.py --manifest portfolio-manifest.json --report execution-report.md --json-report execution-report.json
python3 tools/execute_repo.py --target all --mode functional --report functional-run.md --json-report functional-run.json --log-dir functional-logs
python3 scenario_runner.py scenarios --report scenario-report.md --json-report scenario-report.json
python3 tools/summarize_reports.py --review-json review.json --execution-json execution-report.json --functional-json functional-run.json --report deterministic-summary.md --json-report deterministic-summary.json
python3 tools/portfolio_report.py --review review.json --execution execution-report.json --functional functional-run.json --summary deterministic-summary.json --scenarios scenario-report.json --output portfolio-report.html
python3 -m unittest discover -s tests -p 'test_*.py' -v
```

모든 명령이 성공해야 합니다.

## 2. 제출 준비 완료 기준

```text
Repository Review       ERROR 0 / WARN 0
Execution Analysis      READY
Functional Execution    PASS
Scenario Regression     PASS
Deterministic Summary   READY
Unit Tests              PASS
Cross-platform Tests    PASS
CodeQL                  PASS
```

추가 기준:

- `portfolio-manifest.json`의 제출 필수 파일이 모두 Git 추적 상태
- README 로컬 링크 정상
- Python/JSON/HTML JavaScript 문법 정상
- 저장소에 소스와 중복되는 ZIP 없음
- 실제 운영 시스템을 변경하는 테스트 없음

## 3. 채용담당자 권장 확인 순서

1. [README.md](README.md) — 프로젝트 전체 목적과 검증 체계
2. [index.html](index.html) — HTML 포트폴리오 통합 시작 화면
3. [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — 운영 기능/검증 계층 관계
4. [batch-operations-lab.html](batch-operations-lab.html) — 배치 선후행·Critical Path·SLA
5. [incident-lab.html](incident-lab.html) — 장애 대응 판단
6. [change-management-lab.html](change-management-lab.html) — 변경/사후점검/Rollback
7. [scenario_runner.py](scenario_runner.py) + [scenarios/](scenarios/) — Root Cause·영향·SLA 회귀검증
8. [healthcheck.py](healthcheck.py) — 운영 자동화 코드
9. [portfolio-manifest.json](portfolio-manifest.json) — 파일별 역할과 제출 기준

## 4. 운영 시나리오 검증 의미

`scenario_runner.py`는 시나리오 JSON에 기록된 이벤트 의존관계를 재귀적으로 추적합니다.

- Root Cause 후보
- 후행 영향 범위
- 장애 심각도
- SLA 위험도
- 기대 결과와 실제 계산 결과 차이

을 계산합니다. 화면이 정상적으로 보이는지만 검사하는 것이 아니라 **운영 판단 규칙이 변경되지 않았는지** 회귀검증하는 목적입니다.

## 5. 교차환경 검증

`.github/workflows/tests.yml`은 다음 조합을 검증합니다.

- Ubuntu + Python 3.12
- Ubuntu + Python 3.13
- Windows + Python 3.12
- Windows + Python 3.13

각 조합에서 Python 전체 compile, unittest, 시나리오 회귀검증을 수행합니다.

## 6. 보안검사

`.github/workflows/codeql.yml`은 CodeQL로 다음 언어를 검사합니다.

- Python
- JavaScript/TypeScript

보안검사 결과는 GitHub Security/Code Scanning 결과에서 확인합니다.

## 7. Pages/정적 사이트

현재 저장소에는 `index.html`과 `.github/workflows/pages-preview.yml`이 있습니다. Pages 설정이 비활성인 동안에는 정적 사이트를 실제 배포하지 않고 `_site`를 검증해 Actions Artifact로 보관합니다.

Pages publishing source가 GitHub Actions로 활성화되면 배포 Workflow로 전환할 수 있습니다.

## 8. 실행 안전 정책

CI에서 금지하는 동작:

- 운영 서비스 실제 재기동
- 방화벽/네트워크 정책 실제 변경
- 운영 백업 데이터 변경
- 외부 서버 설정 변경

대신:

- 서비스 워치독은 `--dry-run`
- 백업/로그/이력/장애 입력은 임시 샌드박스
- 인증서는 읽기 전용 TLS 확인
- HTML은 문법검사 및 가능한 Runner에서 headless 로딩

으로 검증합니다.

## 9. 외부 AI 비의존

저장소의 품질 판정과 제출 상태는 외부 AI를 사용하지 않습니다.

```text
review.json
execution-report.json
functional-run.json
        ↓
tools/summarize_reports.py
        ↓
deterministic-summary.md/json
```

따라서 외부 모델/API 상태가 제출 CI 결과에 영향을 주지 않습니다.

## 10. 생성물

Git에 커밋하지 않고 Actions Artifact에서 확인하는 생성물:

- `review.md/json`
- `execution-report.md/json`
- `functional-run.md/json`
- `scenario-report.md/json`
- `deterministic-summary.md/json`
- `portfolio-report.html`
- `unit-test-results.txt`
- 실행 로그 디렉터리

ZIP 배포본도 소스 저장소에는 커밋하지 않습니다.
