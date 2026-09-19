# 전체 기능 인벤토리

| 도메인 | Category | 파일 | 목적 |
|---|---|---|---|
| 품질·CI·보안·릴리스 | `lifecycle-management` | `.github/ISSUE_TEMPLATE/feature-upgrade.yml` | 기능 분석·업그레이드·검증·면접 근거·릴리스 변경 요청을 표준 Issue로 관리 |
| 문서·정책·의존성 관리 | `dependency-automation` | `.github/dependabot.yml` | GitHub Actions/Python 의존성 업데이트 감시 |
| 품질·CI·보안·릴리스 | `security-ci` | `.github/workflows/codeql.yml` | Python 및 JavaScript CodeQL 정적 보안 분석 |
| 품질·CI·보안·릴리스 | `deployment-ci` | `.github/workflows/pages-preview.yml` | GitHub Pages 활성화 전 정적 사이트 품질검증과 배포 Artifact 생성 |
| 품질·CI·보안·릴리스 | `lifecycle-management` | `.github/workflows/portfolio-management.yml` | 전체 기능 인벤토리, 면접 준비도, 업그레이드 우선순위를 정기/PR 자동 관리 |
| 품질·CI·보안·릴리스 | `ci-execution` | `.github/workflows/python-upgrade-readiness.yml` | 선택한 OS와 목표 Python 계열에서 서버 업그레이드 strict precheck와 증거 Artifact 생성 |
| 품질·CI·보안·릴리스 | `release-ci` | `.github/workflows/release-readiness.yml` | 전체 검증 후 Git 추적 전체 소스와 면접/품질 증거를 릴리스 후보 Artifact로 패키징 |
| 품질·CI·보안·릴리스 | `ci-execution` | `.github/workflows/run-files.yml` | Actions에서 개별 도구/시뮬레이터 선택 실행 |
| 품질·CI·보안·릴리스 | `ci` | `.github/workflows/summary.yml` | 품질검수, 전체 분석, functional, 시나리오, lifecycle, 결정적 요약, HTML 리포트 생성 |
| 품질·CI·보안·릴리스 | `ci-test` | `.github/workflows/tests.yml` | Ubuntu/Windows 및 Python 3.12/3.13/3.14 교차환경 compile/unittest/시나리오/업그레이드 검증 |
| 문서·정책·의존성 관리 | `runtime` | `.gitignore` | 생성 리포트, 런타임 데이터, 배포 산출물을 소스 추적에서 제외 |
| 문서·정책·의존성 관리 | `legal` | `LICENSE` | 저장소 라이선스 조건 |
| 문서·정책·의존성 관리 | `documentation` | `README.md` | 포트폴리오 목적, 구성, 실행 및 검증 방법 안내 |
| 문서·정책·의존성 관리 | `documentation` | `SUBMISSION.md` | 채용 제출 전 체크와 검토 순서 안내 |
| IDC 운영 자동화 | `python-cli` | `alert_correlator.py` | 다중 알람을 Root Cause 후보 기준 Incident로 상관분석 |
| 브라우저 운영 시뮬레이터 | `simulator` | `backup-simulator.html` | 백업 스케줄·복구 체인·장애 주입 |
| IDC 운영 자동화 | `python-cli` | `backup_verify.py` | 백업 존재·크기·신선도·SHA-256 검증 |
| 브라우저 운영 시뮬레이터 | `simulator` | `batch-operations-lab.html` | 배치 선후행·장애 전파·재실행·SLA·Critical Path 실습 |
| IDC 운영 자동화 | `python-cli` | `capacity_planner.py` | CPU·메모리·디스크 Capacity 임계 도달 예측 |
| IDC 운영 자동화 | `python-cli` | `cert_expiry.py` | TLS 인증서 만료 사전 점검 |
| 브라우저 운영 시뮬레이터 | `simulator` | `change-management-lab.html` | 변경 사전점검·사후검증·Rollback 판단 실습 |
| IDC 운영 자동화 | `config` | `check.json` | 서버 헬스체크 임계치와 대상 설정 |
| IDC 운영 자동화 | `python-cli` | `disk_forecast.py` | 디스크 사용 추세와 임계 도달 시점 예측 |
| 문서·정책·의존성 관리 | `documentation` | `docs/ARCHITECTURE.md` | 운영 자동화·검증 파이프라인 아키텍처와 파일 간 관계 설명 |
| 문서·정책·의존성 관리 | `documentation` | `docs/FEATURE_LIFECYCLE.md` | 기능 등록·분석·검증·업그레이드·릴리스·면접 증거 관리 정책 |
| 문서·정책·의존성 관리 | `documentation` | `docs/INTERVIEW_GUIDE.md` | 기술면접 설명 구조, 기능별 근거, 경험/시뮬레이션 경계와 예상 질문 |
| 문서·정책·의존성 관리 | `documentation` | `docs/PYTHON_SERVER_UPGRADE.md` | Python 서버 런타임 사전점검, side-by-side 전환, Post Check와 Rollback Runbook |
| 문서·정책·의존성 관리 | `documentation` | `docs/RUNBOOK.md` | 장애·배치·변경·백업 상황별 실행 순서와 에스컬레이션 기준 |
| IDC 운영 자동화 | `input` | `domains.txt` | 인증서 만료 점검 대상 목록 |
| 문서·정책·의존성 관리 | `lifecycle-config` | `feature-catalog.json` | 면접 도메인, 준비 요구사항, 업그레이드 백로그와 릴리스 채널 정의 |
| IDC 운영 자동화 | `python-cli` | `healthcheck.py` | 서버 CPU·메모리·디스크·서비스·네트워크 상태 점검 |
| 브라우저 운영 시뮬레이터 | `simulator` | `incident-lab.html` | IDC 장애 조사·원인·조치·보고 흐름 실습 |
| IDC 운영 자동화 | `python-cli` | `incident_report.py` | 장애 보고서·타임라인·교대 인수인계 Markdown 생성 |
| 브라우저 운영 시뮬레이터 | `portal` | `index.html` | 채용담당자용 통합 포트폴리오 시작 화면 |
| 브라우저 운영 시뮬레이터 | `simulator` | `linux-security-lab.html` | Linux 권한·로그·방화벽 정책 검토 실습 |
| IDC 운영 자동화 | `python-cli` | `log_analyzer.py` | 로그 정규화·오류 집계·급증 탐지 |
| 브라우저 운영 시뮬레이터 | `simulator` | `network-path.html` | 네트워크 구간별 장애 원인 진단 |
| 브라우저 운영 시뮬레이터 | `simulator` | `noc-dashboard.html` | IDC 랙·장비·포트·환경 상태 관제 |
| 문서·정책·의존성 관리 | `manifest` | `portfolio-manifest.json` | 파일별 역할과 제출 필수 파일 기준 |
| IDC 운영 자동화 | `python-cli` | `python_server_upgrade.py` | Python 서버 런타임 업그레이드 사전점검, side-by-side 전환 및 rollback 계획 생성 |
| 문서·정책·의존성 관리 | `runtime` | `requirements.txt` | 외부 Python 패키지가 없음을 명시 |
| 운영 시나리오·회귀검증 | `scenario` | `scenario_runner.py` | IDC 장애 시나리오의 Root Cause·영향 범위·SLA 위험을 계산하고 기대값과 회귀 검증 |
| 운영 시나리오·회귀검증 | `scenario-data` | `scenarios/001-db-disk-capacity.json` | DB 디스크 포화의 온라인·배치 연쇄 영향 |
| 운영 시나리오·회귀검증 | `scenario-data` | `scenarios/002-batch-critical-path.json` | 선행 Job 실패와 Critical Path 마감 영향 |
| 운영 시나리오·회귀검증 | `scenario-data` | `scenarios/003-backup-integrity.json` | 백업 해시 불일치와 복구 가능성 저하 |
| 운영 시나리오·회귀검증 | `scenario-data` | `scenarios/004-dns-path-failure.json` | DNS 장애의 애플리케이션·배치 연결 영향 |
| 운영 시나리오·회귀검증 | `scenario-data` | `scenarios/005-change-rollback.json` | 변경 후 서비스 이상과 Rollback 판단 |
| 브라우저 운영 시뮬레이터 | `simulator` | `server-console.html` | 장애 상태와 Linux/Windows 명령 출력 연동 |
| IDC 운영 자동화 | `python-cli` | `sla_calculator.py` | SLA 목표별 허용 장애시간과 실제 가용성 판정 |
| IDC 운영 자동화 | `python-cli` | `svc_watchdog.py` | 서비스 정지 감지와 제한적 재기동 정책 |
| 품질·CI·보안·릴리스 | `test` | `tests/test_portfolio.py` | 운영 도구 핵심 함수와 경계조건 단위 테스트 |
| 품질·CI·보안·릴리스 | `test` | `tests/test_portfolio_manager.py` | Lifecycle READY/BLOCKED, 미등록 파일, 미분류 category, 백로그 정렬 테스트 |
| 품질·CI·보안·릴리스 | `test` | `tests/test_python_server_upgrade.py` | Python 서버 업그레이드 버전 파싱, 방향 판정, target series, upgrade/rollback 계획 테스트 |
| 품질·CI·보안·릴리스 | `test` | `tests/test_scenarios.py` | 시나리오 재귀 영향 분석·SLA 경계·통합 리포트 테스트 |
| 품질·CI·보안·릴리스 | `execution` | `tools/execute_repo.py` | 실행 가능한 파일을 샌드박스 functional 시나리오로 수행 |
| 품질·CI·보안·릴리스 | `lifecycle-management` | `tools/portfolio_manager.py` | Git 추적 전체 파일과 Manifest/Catalog를 비교해 면접·릴리스 준비도와 업그레이드 계획 생성 |
| 품질·CI·보안·릴리스 | `reporting` | `tools/portfolio_report.py` | 검수·실행·시나리오 결과를 standalone HTML 품질 리포트로 통합 |
| 품질·CI·보안·릴리스 | `quality` | `tools/review_repo.py` | 구조·문법·README 경로·Action 런타임 품질 검사 |
| 품질·CI·보안·릴리스 | `quality` | `tools/run_analyze.py` | 모든 Git 추적 파일 분석과 제출 준비도 판정 |
| 품질·CI·보안·릴리스 | `summary` | `tools/summarize_reports.py` | 외부 AI 없이 검수 JSON을 집계해 제출 요약 생성 |

## 등록 이상

- Manifest 미등록: 없음
- 추적 누락: 없음
- 미분류 Category: 없음
