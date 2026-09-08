# Python Server Upgrade Runbook

이 문서는 [`../python_server_upgrade.py`](../python_server_upgrade.py)를 이용해 Python 런타임 변경을 **사전점검 → side-by-side 준비 → 신규 venv 생성 → 전체 검증 → 실제 Runtime Cutover → Post Check → Rollback** 순서로 관리하기 위한 Runbook입니다.

## 1. 적용 범위

이 도구는 두 가지 모드를 제공합니다.

### Precheck

기본 모드입니다. Python 설치, venv 생성, runtime pointer 변경을 수행하지 않고 현재 서버 상태와 목표 버전 호환성을 분석합니다.

### Apply

`--apply --confirm APPLY`를 명시했을 때만 실행됩니다.

- 이미 side-by-side로 설치된 목표 Python을 사용
- immutable release 디렉터리에 신규 venv 실제 생성
- requirements 설치/검증
- pip check
- compileall
- unittest
- Functional 전체 실행
- Scenario Regression
- 검증 성공 후 `current.json`과 stable launcher 실제 전환
- 이전 runtime은 `previous.json`으로 보존
- 전환 후 Post Check 실패 시 previous pointer로 자동 Rollback

## 2. 안전 경계

실제 적용 모드가 추가됐지만 다음 동작은 하지 않습니다.

- `/usr/bin/python` 등 OS/system Python 덮어쓰기
- 기존 Python 삭제
- Windows 시스템 Python 제거
- systemd Unit 자동 수정
- Windows Service 자동 수정
- 운영 서비스 자동 재기동
- 실제 고객 데이터 변경

즉 **시스템 인터프리터 자체를 교체하는 방식이 아니라 애플리케이션이 사용하는 managed Python runtime을 교체**합니다.

운영 서비스는 최초 1회 승인 절차에서 stable launcher를 바라보도록 구성하는 것을 권장합니다.

Linux:

```text
<runtime-root>/current-python
```

Windows:

```text
<runtime-root>\current-python.cmd
```

업그레이드 시 서비스 설정을 매번 변경하지 않고 이 stable launcher의 대상 runtime만 바꿉니다.

## 3. 현재 검증 목표

2026-09 기준 최신 안정 Python 3 기능 릴리스 계열은 3.14이며, 저장소의 실제 Cutover CI 목표는 **Python 3.14.7**입니다.

기존 호환성 Matrix는 다음을 계속 유지합니다.

- Ubuntu + Python 3.12
- Ubuntu + Python 3.13
- Ubuntu + Python 3.14
- Windows + Python 3.12
- Windows + Python 3.13
- Windows + Python 3.14

실제 Runtime Cutover Workflow에서는 Python 3.12.14 환경에서 시작해 Python 3.14.7 managed runtime으로 전환합니다.

## 4. 기본 사전점검

```bash
python python_server_upgrade.py \
  --target 3.14.7 \
  --target-executable python3.14 \
  --strict-target-installed \
  --report python-upgrade-report.md \
  --json-report python-upgrade-report.json
```

사전점검 항목:

- 현재 Python 버전/실행파일
- 목표 Python 실행파일 존재 여부
- 요청 버전과 실제 target interpreter 버전 일치 여부
- OS/아키텍처
- 가용 디스크
- 현재 `pip check`
- Git 추적 Python 전체 source compile
- Upgrade/Patch/Downgrade 방향
- Upgrade/Rollback 절차

## 5. 실제 managed runtime 업그레이드

목표 Python 3.14.7이 side-by-side로 설치되어 있다고 가정합니다.

Linux 예시:

```bash
python3.12 python_server_upgrade.py \
  --target 3.14.7 \
  --target-executable /opt/python/3.14.7/bin/python3.14 \
  --strict-target-installed \
  --apply \
  --confirm APPLY \
  --runtime-root /opt/daoutech-idc/runtime \
  --requirements requirements.txt \
  --report python-upgrade-report.md \
  --json-report python-upgrade-report.json
```

Windows 예시:

```powershell
py -3.12 python_server_upgrade.py `
  --target 3.14.7 `
  --target-executable "C:\Python314\python.exe" `
  --strict-target-installed `
  --apply `
  --confirm APPLY `
  --runtime-root "C:\DAOUTECH_IDC\runtime" `
  --requirements requirements.txt
```

성공하면 상태는 다음과 같습니다.

```text
APPLIED
changes_applied=true
```

Runtime 디렉터리 구조 예시:

```text
runtime/
├─ current.json
├─ previous.json
├─ current-python        # Linux stable launcher
│  또는 current-python.cmd
├─ releases/
│  └─ python-3.14.7-<UTC timestamp>/
│     └─ venv/
└─ evidence/
   ├─ functional-run.md/json
   ├─ scenario-report.md/json
   └─ functional-logs/
```

## 6. Cutover 전 필수 검증

stable pointer는 다음 검사가 모두 성공해야만 전환됩니다.

1. 목표 Python 정확한 버전 일치
2. 신규 venv 생성
3. requirements 설치 또는 외부 패키지 없음 확인
4. `python -m pip check`
5. `python -m compileall -q .`
6. 전체 unittest
7. Scenario Regression
8. 전체 Functional 실행

한 항목이라도 실패하면 상태는 `VALIDATION_FAILED`가 되고 `current.json`은 변경하지 않습니다.

## 7. Rollback

수동 Rollback:

```bash
python python_server_upgrade.py \
  --rollback \
  --confirm ROLLBACK \
  --runtime-root /opt/daoutech-idc/runtime
```

Rollback은 `previous.json`을 읽어 stable launcher와 `current.json`을 이전 runtime으로 복원합니다.

다음 상황에서는 즉시 Rollback을 권장합니다.

- 서비스 시작 실패
- 오류율 증가
- 응답시간 기준 초과
- 배치 마감 지연
- Health Check 실패
- native extension/OS 호환성 문제
- 예상하지 못한 로그 급증

실패한 신규 runtime은 즉시 삭제하지 않고 원인분석이 끝날 때까지 보존합니다.

## 8. GitHub Actions 실제 Cutover 검증

[`../.github/workflows/python-upgrade-readiness.yml`](../.github/workflows/python-upgrade-readiness.yml)은 두 수준으로 동작합니다.

### workflow_dispatch / precheck

선택한 OS와 Python 정확한 버전으로 strict precheck를 수행합니다.

### main push 또는 apply-ci

GitHub-hosted Runner에서 다음을 실제 수행합니다.

```text
Python 3.12.14 current interpreter
        ↓
Python 3.14.7 target interpreter 설치
        ↓
신규 immutable venv 실제 생성
        ↓
pip / compile / unittest / functional / scenario
        ↓
.runtime-ci/current.json 실제 전환
        ↓
stable launcher에서 Python --version 확인
```

Ubuntu와 Windows 두 환경 모두 실제 managed runtime cutover를 검증합니다.

단, GitHub-hosted Runner는 실행 후 폐기되는 격리 CI 서버입니다. 따라서 이 성공 결과는 **운영 서버 자체가 업그레이드됐다는 의미가 아니라, 실제 업그레이드 절차가 서버 환경에서 재현 가능하게 실행됐다는 증거**입니다.

## 9. 실제 운영 서버 적용 전 확인

운영 서버에 적용하려면 다음이 추가로 필요합니다.

- 대상 서버 접근 권한
- 변경 승인 번호/작업 시간
- target Python side-by-side 설치
- 서비스 계정 권한
- stable launcher를 사용하도록 서비스 실행경로 구성
- 백업/복구 확인
- 서비스 담당자 확인
- 변경 후 Health/Log/Batch/SLA 관찰

이 저장소에 실제 고객 서버 접속정보, 비밀번호, 키, 내부 IP를 저장하지 않습니다.
