# Python Server Upgrade Runbook

이 문서는 [`../python_server_upgrade.py`](../python_server_upgrade.py)를 이용해 서버의 Python 런타임 업그레이드를 **사전점검 → side-by-side 설치 → 신규 venv 검증 → 서비스 전환 → Post Check → Rollback** 순서로 관리하기 위한 포트폴리오 Runbook입니다.

## 1. 안전 원칙

- 기존 Python을 덮어쓰거나 삭제하지 않습니다.
- 신규 Python은 기존 런타임과 **side-by-side**로 설치하는 것을 전제로 합니다.
- CI와 포트폴리오 도구는 실제 설치·삭제·서비스 재기동을 수행하지 않습니다.
- 서비스 전환 전 신규 venv에서 compile, unit test, functional test를 먼저 통과시킵니다.
- Post Check가 실패하면 이전 Python/venv 경로로 즉시 Rollback합니다.
- 실제 운영 적용 시 OS 패키지 저장소, 사내 승인 절차, 서비스 소유자, 점검 시간대를 별도로 확인해야 합니다.

## 2. 현재 권장 검증 계열

저장소는 Python 3.12 이상을 유지하면서 3.12 / 3.13 / 3.14 계열을 교차 검증합니다. Python 3.14는 최신 안정 기능 릴리스 계열을 목표로 하되, 특정 패치 버전에 코드를 고정하지 않습니다.

## 3. 기본 사전점검

저장소 루트에서 다음처럼 실행합니다.

```bash
python python_server_upgrade.py \
  --target 3.14 \
  --report python-upgrade-report.md \
  --json-report python-upgrade-report.json
```

이 단계는 다음을 확인합니다.

- 현재 Python 버전/실행파일/구현체
- OS/아키텍처
- 가상환경 사용 여부
- 최소 가용 디스크
- 현재 Python의 `pip check`
- Git 추적 Python 전체 source compile
- 목표 Python 실행파일 존재 여부
- Upgrade / Patch Upgrade / Downgrade 방향
- Upgrade Plan / Rollback Plan

목표 Python이 아직 설치되지 않은 서버에서는 `PLAN_READY`가 정상입니다. 실제 변경 전에 target runtime을 side-by-side로 설치한 뒤 strict 검증을 다시 수행합니다.

## 4. 목표 런타임 설치 후 Strict Precheck

Linux 예시:

```bash
python python_server_upgrade.py \
  --target 3.14 \
  --target-executable python3.14 \
  --service portfolio-api \
  --strict-target-installed
```

Windows 예시:

```powershell
python python_server_upgrade.py `
  --target 3.14 `
  --target-executable python `
  --service portfolio-api `
  --strict-target-installed
```

`--strict-target-installed` 상태에서 목표 실행파일을 찾지 못하면 `BLOCKED`로 종료합니다.

## 5. 권장 변경 순서

1. 현재 Python 경로, venv, requirements, 서비스 설정을 기록합니다.
2. 목표 Python을 기존 런타임과 side-by-side로 설치합니다.
3. 목표 실행파일의 `--version`을 확인합니다.
4. 신규 Python으로 새 가상환경을 생성합니다.
5. 필요한 의존성을 신규 venv에 설치합니다.
6. `python -m pip check`를 실행합니다.
7. `python -m compileall -q .`을 실행합니다.
8. 전체 unittest와 functional/scenario 검증을 수행합니다.
9. 변경 승인 후 서비스 Python/venv 경로만 전환합니다.
10. Health Check, 로그, 배치, SLA, 오류율을 Post Check합니다.

## 6. Rollback 조건

다음 중 하나라도 발생하면 이전 런타임으로 되돌리는 것을 기본 원칙으로 합니다.

- 신규 venv 의존성 검증 실패
- source compile 또는 unit/functional test 실패
- 서비스 기동 실패
- 오류율/응답시간/배치 마감이 기준을 벗어남
- OS 또는 native extension 호환성 문제
- 변경 후 예상하지 못한 경고·로그 급증

Rollback 시 신규 Python 자체를 즉시 삭제하지 않습니다. 이전 Python/venv 서비스 경로를 복원한 뒤 원인분석이 끝난 다음 정리합니다.

## 7. GitHub Actions에서의 검증

[교차환경 테스트](../.github/workflows/tests.yml)는 Ubuntu/Windows에서 Python 3.12 / 3.13 / 3.14를 각각 준비해 compile, unittest, 운영 시나리오, Python Upgrade strict precheck를 실행합니다.

따라서 목표 Python 계열이 실제 Runner에서 설치된 상태로 코드가 정상 작동하는지를 검증할 수 있습니다.

## 8. 면접 설명 포인트

- 왜 in-place 덮어쓰기보다 side-by-side 설치가 안전한가?
- 왜 신규 Python에서 venv를 새로 만드는가?
- 단순 `python --version` 확인만으로 업그레이드 성공을 판단하면 안 되는 이유는 무엇인가?
- Post Check에서 어떤 지표를 봐야 하는가?
- Python minor 업그레이드에서 deprecated API, native extension, 표준 라이브러리 변경을 어떻게 검증하는가?
- Rollback 시 신규 Python을 바로 삭제하지 않는 이유는 무엇인가?

이 기능은 실제 운영 서버 자동 변경 기능이 아니라 **안전한 변경관리·검증·Rollback 판단을 코드로 표현한 포트폴리오 기능**입니다.
