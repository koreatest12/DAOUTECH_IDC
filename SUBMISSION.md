# 채용 제출 가이드

이 문서는 `DAOUTECH_IDC` 저장소를 채용담당자 또는 기술면접관에게 제출하기 전에 확인할 항목과, 처음 저장소를 보는 사람이 빠르게 검토할 순서를 정리합니다.

## 1. 제출 전에 실행할 명령

```bash
python3 tools/review_repo.py --report review.md --json-report review.json
python3 tools/run_analyze.py --manifest portfolio-manifest.json --report execution-report.md --json-report execution-report.json
python3 tools/execute_repo.py --target all --mode functional --report functional-run.md --json-report functional-run.json --log-dir functional-logs
python3 tools/summarize_reports.py --review-json review.json --execution-json execution-report.json --functional-json functional-run.json --report deterministic-summary.md --json-report deterministic-summary.json
python3 -m unittest discover -s tests -p 'test_*.py' -v
```

`review`, `run_analyze`, `execute_repo`, `summarize_reports`, `unittest`가 모두 정상이어야 합니다.

- `review.md`: 구조·문법·링크·호환성의 결정적 검사 결과
- `execution-report.md`: 모든 Git 추적 파일의 안전 실행·분석 결과와 제출 준비 상태
- `functional-run.md`: 실행 가능한 도구와 HTML의 functional 수행 결과
- `deterministic-summary.md`: 위 JSON 결과를 외부 AI 없이 로컬 Python으로 집계한 최종 요약
- JSON 리포트: 자동 처리와 추가 분석을 위한 구조화 결과

생성 리포트는 소스 파일이 아니므로 저장소에 커밋하지 않고 GitHub Actions Artifact로 보관합니다.

## 2. 제출 준비 완료 기준

다음 조건을 모두 만족하면 `READY`로 판단합니다.

- 제출 필수 파일이 모두 Git에 추적되어 있음
- `tools/review_repo.py` 결과 ERROR 0건, WARN 0건
- `tools/run_analyze.py` 결과 실행/분석 오류 0건
- `tools/execute_repo.py` functional 결과 `PASS`
- `tools/summarize_reports.py` 최종 판정 `READY`
- Python `unittest` 성공
- Python CLI 엔트리포인트 로딩 성공
- HTML 인라인 JavaScript의 Node 24 문법 검사 성공
- JSON 파싱 성공
- README 로컬 링크 정상
- 저장소에 중복 배포 ZIP 파일 없음
- GitHub Actions 통합 검수 성공

## 3. 채용담당자가 먼저 보면 좋은 순서

1. [index.html](index.html) — 전체 포트폴리오 통합 시작 화면
2. [README.md](README.md) — 프로젝트 목적과 전체 구성
3. [batch-operations-lab.html](batch-operations-lab.html) — 배치 선후행·장애 전파·SLA 운영 관점
4. [incident-lab.html](incident-lab.html) — 장애 대응 판단 흐름
5. [healthcheck.py](healthcheck.py) — 운영 자동화 코드 구조
6. [change-management-lab.html](change-management-lab.html) — 변경·사후검증·Rollback 판단
7. [portfolio-manifest.json](portfolio-manifest.json) — 전체 파일 역할과 제출 기준

## 4. 실행 안전 정책

CI는 실제 운영 시스템에 영향을 줄 수 있는 동작을 자동으로 수행하지 않습니다.

- `svc_watchdog.py`: functional 검증에서 항상 `--dry-run`
- 백업 검증: 임시 샌드박스 파일만 생성·검증
- 디스크/Capacity 이력: 임시 샌드박스 파일에만 기록
- 장애/알람 보고: 임시 입력과 출력만 사용
- 인증서 검사: 읽기 전용 TLS 연결만 수행
- 실제 방화벽 정책 변경, 운영 서비스 재기동, 운영 백업 데이터 변경: 수행하지 않음

## 5. 외부 AI 비의존 정책

GitHub Models는 2026년 7월 30일 종료되었으므로 제출 CI는 `actions/ai-inference`와 GitHub Models inference API를 사용하지 않습니다.

최종 요약은 `tools/summarize_reports.py`가 다음 파일만 읽어 결정적으로 생성합니다.

- `review.json`
- `execution-report.json`
- `functional-run.json`

따라서 외부 AI 서비스 장애, 모델 retirement, API brownout이 제출 CI의 성공 여부에 영향을 주지 않습니다.

## 6. 제출에 포함되는 핵심 파일

- 안내: `README.md`, `SUBMISSION.md`, `LICENSE`, `index.html`
- 실행 기준: `portfolio-manifest.json`, `requirements.txt`
- 자동 검수: `tools/review_repo.py`, `tools/run_analyze.py`, `tools/execute_repo.py`, `tools/summarize_reports.py`
- 테스트: `tests/test_portfolio.py`
- CI: `.github/workflows/summary.yml`, `.github/workflows/run-files.yml`, `.github/workflows/tests.yml`
- 의존성 관리: `.github/dependabot.yml`
- 운영 Python 도구: `healthcheck.py`, `log_analyzer.py`, `alert_correlator.py`, `disk_forecast.py`, `capacity_planner.py`, `sla_calculator.py`, `svc_watchdog.py`, `backup_verify.py`, `cert_expiry.py`, `incident_report.py`
- 입력/설정: `check.json`, `domains.txt`
- HTML 시뮬레이터: `noc-dashboard.html`, `batch-operations-lab.html`, `incident-lab.html`, `change-management-lab.html`, `linux-security-lab.html`, `backup-simulator.html`, `server-console.html`, `network-path.html`

## 7. 제출하지 않는 생성물

다음 파일은 자동 생성물이며 GitHub Actions Artifact로 확인합니다.

- `review.md`, `review.json`
- `execution-report.md`, `execution-report.json`
- `functional-run.md`, `functional-run.json`
- `deterministic-summary.md`, `deterministic-summary.json`
- 실행 로그 디렉터리

ZIP 배포본도 Git 저장소에는 두지 않습니다. 필요한 경우 GitHub Release 또는 Actions Artifact로 생성해 소스와 배포물을 분리합니다.
