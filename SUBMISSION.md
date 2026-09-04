# 채용 제출 가이드

이 문서는 `DAOUTECH_IDC` 저장소를 채용담당자 또는 기술면접관에게 제출하기 전에 확인할 항목과, 처음 저장소를 보는 사람이 빠르게 검토할 순서를 정리합니다.

## 1. 제출 전에 실행할 명령

```bash
python3 tools/review_repo.py --report review.md --json-report review.json
python3 tools/run_analyze.py --manifest portfolio-manifest.json --report execution-report.md --json-report execution-report.json
```

두 명령 모두 종료 코드가 0이어야 합니다.

- `review.md`: 구조·문법·링크·호환성의 결정적 검사 결과
- `execution-report.md`: 모든 Git 추적 파일의 안전 실행·분석 결과와 제출 준비 상태
- JSON 리포트: 자동 처리 또는 추가 분석을 위한 구조화 결과

생성 리포트는 소스 파일이 아니므로 저장소에 커밋하지 않고 GitHub Actions Artifact로 보관합니다.

## 2. 제출 준비 완료 기준

다음 조건을 모두 만족하면 `READY`로 판단합니다.

- 제출 필수 파일이 모두 Git에 추적되어 있음
- `tools/review_repo.py` 결과 ERROR 0건, WARN 0건
- `tools/run_analyze.py` 결과 실행/분석 오류 0건
- Python CLI의 `--help` 실행 성공
- HTML 인라인 JavaScript의 Node 24 문법 검사 성공
- JSON 파싱 성공
- README 로컬 링크 정상
- 저장소에 중복 배포 ZIP 파일 없음
- GitHub Actions 통합 검수 성공

## 3. 채용담당자가 먼저 보면 좋은 순서

1. [README.md](README.md) — 프로젝트 목적과 전체 구성
2. [incident-lab.html](incident-lab.html) — 장애 대응 판단 흐름
3. [healthcheck.py](healthcheck.py) — 운영 자동화 코드 구조
4. [server-console.html](server-console.html) — 상태 변화와 명령 결과 연동
5. [backup-simulator.html](backup-simulator.html) — 백업 정책·복구 체인·장애 주입
6. [portfolio-manifest.json](portfolio-manifest.json) — 전체 파일 역할과 제출 기준

## 4. 실행 안전 정책

CI는 실제 운영 시스템에 영향을 줄 수 있는 동작을 자동으로 실행하지 않습니다.

- 서비스 재기동: 자동 실행하지 않음
- 실제 인증서 원격 조회: 자동 실행하지 않음
- 실제 백업 데이터 기록/변경: 자동 실행하지 않음
- 실제 네트워크 정책 변경: 자동 실행하지 않음

대신 Python CLI는 `--help`를 실제 실행하고, Python AST·HTML JavaScript·JSON을 결정적으로 검사합니다. 이 방식으로 **코드가 로드되고 기본 엔트리포인트가 정상인지 확인하면서도 외부 시스템에 부작용을 만들지 않습니다.**

## 5. 제출에 포함되는 핵심 파일

- 안내: `README.md`, `SUBMISSION.md`, `LICENSE`
- 실행 기준: `portfolio-manifest.json`, `requirements.txt`
- 자동 검수: `tools/review_repo.py`, `tools/run_analyze.py`
- CI: `.github/workflows/summary.yml`
- 운영 Python 도구: `healthcheck.py`, `log_analyzer.py`, `disk_forecast.py`, `svc_watchdog.py`, `backup_verify.py`, `cert_expiry.py`
- 입력/설정: `check.json`, `domains.txt`
- HTML 시뮬레이터: `noc-dashboard.html`, `linux-security-lab.html`, `backup-simulator.html`, `incident-lab.html`, `server-console.html`, `network-path.html`

## 6. 제출하지 않는 생성물

다음 파일은 자동 생성물이며 GitHub Actions Artifact로 확인합니다.

- `review.md`
- `review.json`
- `execution-report.md`
- `execution-report.json`
- `prompt.txt`

ZIP 배포본도 Git 저장소에는 두지 않습니다. 필요한 경우 GitHub Release 또는 Actions Artifact로 생성해 소스와 배포물을 분리합니다.
