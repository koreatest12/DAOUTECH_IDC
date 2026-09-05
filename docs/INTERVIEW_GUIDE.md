# DAOUTECH_IDC 기술면접 가이드

이 문서는 저장소를 **기술면접에서 설명하기 위한 근거 지도**입니다. 실제 운영 경험과 포트폴리오 시뮬레이션을 구분해 설명하는 것을 최우선 원칙으로 합니다.

## 1. 3분 설명 구조

1. **문제 영역**: 데이터센터·금융권 IT 인프라에서 반복되는 점검, 배치 마감, 장애 대응, 백업, 변경관리, Capacity/SLA 판단을 다룹니다.
2. **구현 방식**: Python CLI, HTML 시뮬레이터, 운영 시나리오 JSON, GitHub Actions 검증으로 분리했습니다.
3. **품질 근거**: 전체 파일 분석, functional 실행, 운영 시나리오 회귀검증, Ubuntu/Windows 교차테스트, CodeQL을 자동화했습니다.
4. **안전 원칙**: CI에서는 실제 서비스 재기동·방화벽 변경·운영 백업 변경을 하지 않습니다.
5. **경험 경계**: 실제 운영 관점에서 익숙한 흐름과 학습·확장 시뮬레이션을 명확히 나눕니다.

## 2. 기능별 설명 포인트

| 영역 | 먼저 보여줄 파일 | 면접에서 설명할 핵심 |
|---|---|---|
| 서버/NOC | `healthcheck.py`, `noc-dashboard.html` | 임계치, 상태코드, 1차 판단, 오탐 방지 |
| 배치 | `batch-operations-lab.html`, `scenarios/002-batch-critical-path.json` | 선후행, Critical Path, 재실행, 마감/SLA |
| 장애 | `incident-lab.html`, `scenario_runner.py` | Root Cause 후보, 영향 범위, 에스컬레이션 |
| 로그/알람 | `log_analyzer.py`, `alert_correlator.py` | 로그 정규화, 급증 탐지, 다중 알람 상관분석 |
| 백업 | `backup_verify.py`, `backup-simulator.html` | SUCCESS와 복구 가능성의 차이, SHA-256 |
| 변경 | `change-management-lab.html`, `scenarios/005-change-rollback.json` | Pre/Post Check, Rollback 조건 |
| 네트워크 | `network-path.html`, `scenarios/004-dns-path-failure.json` | IP/DNS/Port/L4 구간 분리 진단 |
| Capacity/SLA | `capacity_planner.py`, `disk_forecast.py`, `sla_calculator.py` | 추세, 임계 도달, 허용 장애시간 |
| 품질/보안 | `.github/workflows/summary.yml`, `.github/workflows/tests.yml`, `.github/workflows/codeql.yml` | deterministic gate, 교차환경, 정적 보안 분석 |
| 릴리스 | `.github/workflows/release-readiness.yml`, `tools/portfolio_manager.py` | 면접 직전 재검증, Artifact, 변경 이력 |

## 3. 답변할 때 지켜야 할 경계

- 시뮬레이터에서 만든 서버명·장애 수치·로그를 실제 고객 운영 데이터라고 말하지 않습니다.
- 실제 경험이 있는 운영 흐름은 경험 기반이라고 설명하되, 저장소 구현 자체를 실운영 배포 실적이라고 표현하지 않습니다.
- `svc_watchdog.py`의 CI 검증은 `--dry-run`입니다. 실제 서비스 재기동 자동화를 운영에 적용했다고 과장하지 않습니다.
- CodeQL PASS는 모든 보안 취약점이 없다는 의미가 아니라, 현재 코드가 설정된 정적 분석을 통과했다는 의미로 설명합니다.
- GitHub Pages는 저장소 설정이 활성화된 경우에만 실제 공개 배포가 됩니다. 현재 Workflow의 목적은 Pages-ready 패키징과 검증입니다.

## 4. 예상 기술면접 질문과 근거

### Q1. Health Check 임계치는 어떻게 정합니까?

근거: `healthcheck.py`, `check.json`

답변 포인트: 운영 기준값, 평시 baseline, 업무 마감 시간, 지속시간을 함께 봐야 하며 단일 순간값만으로 자동 조치하지 않습니다.

### Q2. 배치 장애에서 실패 Job만 보면 안 되는 이유는 무엇입니까?

근거: `batch-operations-lab.html`, `scenarios/002-batch-critical-path.json`

답변 포인트: 후행 의존성과 Critical Path 때문에 작은 실패도 마감 영향이 커질 수 있어 후행 범위와 SLA 잔여시간을 같이 확인합니다.

### Q3. Root Cause와 증상을 어떻게 구분합니까?

근거: `alert_correlator.py`, `scenario_runner.py`

답변 포인트: 최초 이벤트, 공통 의존성, 시간 순서, 다수 후행 알람을 묶어 원인 후보를 좁힙니다.

### Q4. 서비스 자동 재기동에 상한이 필요한 이유는 무엇입니까?

근거: `svc_watchdog.py`

답변 포인트: 반복 장애에서 무한 재기동은 장애를 가리고 부하를 키울 수 있어 재시도 상한, backoff, 에스컬레이션이 필요합니다.

### Q5. 백업 성공인데도 복구가 안 될 수 있습니까?

근거: `backup_verify.py`, `scenarios/003-backup-integrity.json`

답변 포인트: 파일 존재뿐 아니라 크기, 신선도, 무결성, 복구 체인을 별도로 검증해야 합니다.

### Q6. Windows/Linux를 왜 둘 다 테스트합니까?

근거: `.github/workflows/tests.yml`

답변 포인트: 경로·인코딩·프로세스·명령 차이로 같은 Python 코드도 OS별 문제가 생길 수 있습니다. 실제로 Windows stdout 인코딩 문제를 검증 중 발견해 수정한 경험을 설명할 수 있습니다.

### Q7. Dependabot major 업데이트를 왜 자동 그룹/병합하지 않습니까?

근거: `.github/dependabot.yml`

답변 포인트: major는 호환성 파괴 가능성이 높으므로 minor/patch와 분리해 실제 검증 후 검토합니다.

### Q8. functional test와 CodeQL의 차이는 무엇입니까?

근거: `tools/execute_repo.py`, `.github/workflows/codeql.yml`

답변 포인트: functional은 실제 입력/출력/종료코드 동작을 확인하고, CodeQL은 실행만으로 드러나지 않는 코드 패턴과 보안 문제를 정적으로 분석합니다.

## 5. 면접 직전 체크

```bash
python3 tools/portfolio_manager.py --fail-on-blocked
python3 tools/review_repo.py --report review.md --json-report review.json
python3 tools/run_analyze.py --manifest portfolio-manifest.json --report execution-report.md --json-report execution-report.json
python3 tools/execute_repo.py --target all --mode functional --report functional-run.md --json-report functional-run.json --log-dir functional-logs
python3 scenario_runner.py scenarios --report scenario-report.md --json-report scenario-report.json
python3 -m unittest discover -s tests -p 'test_*.py' -v
```

최종적으로 `interview-readiness.md`가 `READY`, 기존 deterministic summary가 `READY`, 관련 GitHub Actions가 모두 성공인지 확인합니다.
