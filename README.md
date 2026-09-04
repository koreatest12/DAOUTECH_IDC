# IDC 운영 자동화·시뮬레이션 포트폴리오

데이터센터·금융권 IT 인프라 운영 경험을 바탕으로, 반복 점검·장애 대응·백업·보안·네트워크 진단에서 중요하다고 판단한 항목을 Python 도구와 단일 HTML 시뮬레이터로 구현한 포트폴리오입니다.

이 저장소는 **실제 운영 자동화 코드**와 **학습·설명용 시뮬레이터**를 구분하고, 제출 전에 모든 Git 추적 파일을 자동 검수하도록 구성했습니다. Python 도구는 표준 라이브러리만 사용하며, HTML 도구는 별도 빌드 없이 브라우저에서 실행할 수 있습니다.

## 제출 상태 확인

채용 제출 전에는 다음 두 검사를 실행합니다.

```bash
python3 tools/review_repo.py --report review.md --json-report review.json
python3 tools/run_analyze.py --manifest portfolio-manifest.json --report execution-report.md --json-report execution-report.json
```

- `tools/review_repo.py`: 파일 구조, Python/JavaScript/JSON 문법, README 로컬 링크, GitHub Actions Node 버전을 결정적으로 검사합니다.
- `tools/run_analyze.py`: Git이 추적하는 모든 파일을 유형별로 안전하게 실행·분석하고 제출 필수 파일 누락 여부를 판정합니다.
- `portfolio-manifest.json`: 파일별 역할과 제출 필수 파일 목록의 기준입니다.
- [SUBMISSION.md](SUBMISSION.md): 채용담당자 관점의 실행 순서와 제출 전 체크 항목입니다.

GitHub Actions의 [통합 검수 워크플로](.github/workflows/summary.yml)는 위 두 검사를 자동 실행하고 `review.md`, `review.json`, `execution-report.md`, `execution-report.json`, `prompt.txt`를 Artifact로 보관합니다.

## 빠른 실행

### 요구 환경

- Python 3.12 이상
- Node.js 24 이상 — HTML 인라인 JavaScript 자동 문법 검사용
- 브라우저 — HTML 시뮬레이터 실행용

Python 외부 패키지는 필요하지 않습니다. [requirements.txt](requirements.txt)는 이 사실을 명시하기 위한 제출용 파일입니다.

### 전체 포트폴리오 상태 점검

```bash
python3 tools/run_analyze.py --manifest portfolio-manifest.json
```

결과가 `READY`이면 제출 필수 파일이 모두 존재하고 안전 실행·분석에서 오류가 없다는 뜻입니다.

## 포트폴리오 파일 구성

| 파일 | 구분 | 무엇을 보여 주는가 | 실행 방법 |
|---|---|---|---|
| [noc-dashboard.html](noc-dashboard.html) | 시뮬레이터 | IDC 랙·장비·포트·환경 상태 관제 | 브라우저로 열기 |
| [healthcheck.py](healthcheck.py) | Python 운영 도구 | CPU·메모리·디스크·서비스·네트워크 점검과 종료 코드 판정 | `python3 healthcheck.py --help` |
| [log_analyzer.py](log_analyzer.py) | Python 운영 도구 | 로그 정규화, 오류 집계, 급증 구간 탐지 | `python3 log_analyzer.py --help` |
| [disk_forecast.py](disk_forecast.py) | Python 운영 도구 | 디스크 사용 추세와 임계 도달 시점 예측 | `python3 disk_forecast.py --help` |
| [svc_watchdog.py](svc_watchdog.py) | Python 운영 도구 | 서비스 정지 감지와 제한적 재기동 정책 | `python3 svc_watchdog.py --help` |
| [backup_verify.py](backup_verify.py) | Python 운영 도구 | 백업 존재·크기·신선도·SHA-256 검증 | `python3 backup_verify.py --help` |
| [cert_expiry.py](cert_expiry.py) | Python 운영 도구 | 인증서 만료 사전 점검 | `python3 cert_expiry.py --help` |
| [linux-security-lab.html](linux-security-lab.html) | 시뮬레이터 | 권한·로그·방화벽 정책 검토 실습 | 브라우저로 열기 |
| [backup-simulator.html](backup-simulator.html) | 시뮬레이터 | 백업 스케줄·복구 체인·장애 주입 | 브라우저로 열기 |
| [incident-lab.html](incident-lab.html) | 시뮬레이터 | 장애 조사→원인 판단→조치→보고서 흐름 | 브라우저로 열기 |
| [server-console.html](server-console.html) | 시뮬레이터 | 장애 상황별 서버 명령 결과의 연동 | 브라우저로 열기 |
| [network-path.html](network-path.html) | 시뮬레이터 | 네트워크 구간별 장애 원인 좁히기 | 브라우저로 열기 |

지원 파일은 [check.json](check.json), [domains.txt](domains.txt), [portfolio-manifest.json](portfolio-manifest.json)입니다.

## 주요 설계 의도

### 서버 헬스체크

`healthcheck.py`는 호스트 정보, 업타임, CPU 부하, 메모리, 파일시스템 사용률, 지정 서비스 상태, 네트워크 도달성 등을 확인하고 종료 코드를 `0 정상 / 1 주의 / 2 조치 필요`로 나눕니다. 사람이 매번 로그를 읽지 않아도 스케줄러가 상태를 판정할 수 있도록 한 것이 핵심입니다.

### 운영 스크립트

- `log_analyzer.py`: 타임스탬프·PID·IP·경로·숫자 차이를 정규화해 같은 원인의 로그를 묶고 시간대별 급증을 찾습니다.
- `disk_forecast.py`: 사용률 이력을 쌓아 임계치 도달 예상 시점을 계산합니다.
- `svc_watchdog.py`: 무조건 재기동하지 않고 재시도 간격과 상한을 둡니다.
- `backup_verify.py`: 잡 성공 여부와 복구 가능한 파일 존재 여부를 분리해 검증합니다.
- `cert_expiry.py`: 만료 임박 인증서를 사전에 확인하도록 구성했습니다.

### 장애·백업·보안·네트워크 시뮬레이터

HTML 파일은 화면만 보여 주는 데모가 아니라, 상태를 바꾸면 관련 출력과 판정이 함께 바뀌도록 구성했습니다. 예를 들어 서버 서비스 정지 시 프로세스·포트·서비스 상태가 같이 변하고, 네트워크 장애도 장애 지점에 따라 ping·DNS·포트·경로 결과가 다르게 나오도록 설계했습니다.

## 검증 방식

제출 CI에서는 부작용 없는 검사만 자동 실행합니다.

1. 모든 Python 파일을 AST로 파싱합니다.
2. argparse 기반 Python CLI는 실제로 `--help`를 실행해 엔트리포인트 로딩을 확인합니다.
3. 모든 HTML 인라인 JavaScript를 Node 24의 `node --check`로 검사합니다.
4. JSON 파일을 실제 파싱합니다.
5. Markdown 로컬 링크와 문서에 적힌 실제 저장소 경로를 확인합니다.
6. 제출 필수 파일이 Git에 추적되고 있는지 확인합니다.
7. 소스와 중복되는 ZIP 파일은 저장소에 커밋하지 않고 Actions Artifact 또는 Release로 분리합니다.

서비스 재기동, 외부 시스템 변경, 실제 백업 데이터 변경처럼 운영 영향이 가능한 동작은 CI에서 자동 실행하지 않습니다. 대신 해당 CLI의 로딩·문법·인자 구성을 안전하게 실행 검증합니다.

## 경험과 학습 범위 구분

**운영 경험을 바탕으로 구현한 영역**은 서버·네트워크 모니터링, 장애 1차 대응과 에스컬레이션 판단, 배치 마감 관리, 백업 결과 확인, Linux/Windows 서버 상태 조회 등입니다.

**학습·확장 목적으로 구현한 영역**에는 방화벽 정책 검토, DNS 장애 시나리오, 인증서 만료 관리, 항온항습 관련 시나리오 등이 포함됩니다. 해당 영역은 포트폴리오에서 실무 경험으로 과장하지 않고 학습 범위로 구분합니다.

## AI 활용 원칙

코드 작성과 정리 과정에서 생성형 AI를 보조 도구로 활용할 수 있지만, 저장소의 사실 판정은 AI가 아니라 `tools/review_repo.py`와 `tools/run_analyze.py`가 수행합니다. AI 요약은 이미 확정된 검사 결과를 읽기 쉽게 정리하는 역할만 담당합니다.

## 라이선스

라이선스 조건은 [LICENSE](LICENSE)를 확인해 주세요.
