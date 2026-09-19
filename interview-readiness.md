# 면접 대비 포트폴리오 Lifecycle 리포트

> 저장소의 사실을 자동 집계한 결정적 관리 리포트입니다. 실제 운영 경험과 시뮬레이션 범위는 README/INTERVIEW_GUIDE의 경계를 따릅니다.

## 최종 판정

- 상태: **READY**
- 면접/릴리스 준비 점수: **100/100**
- Git 추적 파일: **60개**
- Manifest 등록 파일: **60개**

### 점수 구성

| 항목 | 점수 |
|---|---:|
| manifest_coverage | 35 |
| documentation | 20 |
| automation | 20 |
| domain_coverage | 15 |
| release | 10 |

## 차단 요소

- 없음

## 도메인별 면접 준비

### 문서·정책·의존성 관리 (`governance`)

저장소 목적, 경험/시뮬레이션 경계, 의존성 및 변경 정책을 설명할 수 있어야 합니다.

관리 파일: **13개**

### 품질·CI·보안·릴리스 (`quality-security`)

코드가 실제로 검증되는 경로, 실패 게이트, 교차환경, CodeQL, 릴리스 증거를 설명할 수 있어야 합니다.

관리 파일: **19개**

### 운영 시나리오·회귀검증 (`scenario-regression`)

Root Cause 후보, 후행 영향, SLA 위험, 기대값 회귀검증의 계산 근거를 설명합니다.

관리 파일: **6개**

### 브라우저 운영 시뮬레이터 (`interactive-simulators`)

NOC·배치·장애·변경·백업·서버·네트워크·보안 시뮬레이터의 목적과 실제 경험 범위를 구분해 설명합니다.

관리 파일: **9개**

### IDC 운영 자동화 (`operations-automation`)

Health Check, 로그/알람, Capacity/SLA, 백업, 인증서, 서비스 감시와 Python 런타임 변경의 입력·판단·종료코드·안전장치를 설명합니다.

관리 파일: **13개**

## 다음 업그레이드 우선순위

- **P0 UPG-001** · 각 핵심 기능의 면접 설명 포인트와 실행 증거를 하나의 자동 리포트로 유지 — 완료 기준: interview-readiness.md에서 모든 도메인이 파일과 설명 포인트를 보유
- **P0 UPG-002** · 면접 직전 검증 결과와 정적 포트폴리오를 릴리스 후보 Artifact로 패키징 — 완료 기준: release-readiness workflow가 전체 검증 후 bundle Artifact를 생성
- **P0 UPG-007** · Python 3.14 안정 계열 업그레이드를 side-by-side, 신규 venv, strict precheck, Post Check, Rollback 기준으로 관리 — 완료 기준: Ubuntu/Windows × Python 3.12/3.13/3.14 교차검증과 Python upgrade strict precheck가 모두 PASS
- **P1 UPG-003** · 스토리지·네트워크·배치·변경 외 추가 운영 장애 시나리오 확장 — 완료 기준: 새 시나리오는 expected 결과와 단위/회귀 테스트를 동반
- **P1 UPG-004** · 운영 자동화 결과를 공통 상태 모델과 증거 포맷으로 정규화 — 완료 기준: 핵심 Python 도구가 상태/근거/종료코드 설명을 문서와 테스트로 보유
- **P1 UPG-005** · 기능별 예상 기술면접 질문과 답변 근거 파일 연결 — 완료 기준: INTERVIEW_GUIDE에서 주요 운영 도메인별 질문·근거·주의사항 확인 가능
- **P2 UPG-006** · GitHub Pages 활성화 시 검증된 정적 사이트를 공식 배포 Workflow로 전환 — 완료 기준: 저장소 Pages 설정 활성화 후 deploy-pages 성공

## 예상 기술면접 질문

1. Health Check에서 WARN과 CRITICAL 임계치를 어떻게 정하고 오탐을 줄였는가?
2. Control-M/배치 운영 경험을 Critical Path와 SLA 관점으로 어떻게 모델링했는가?
3. 장애 발생 시 Root Cause 후보와 영향 범위를 어떤 순서로 좁히는가?
4. 서비스 자동 재기동을 무제한으로 하지 않는 이유와 안전장치는 무엇인가?
5. 백업 SUCCESS와 실제 복구 가능성을 왜 별도로 검증해야 하는가?
6. Capacity Forecast의 추세 계산을 운영 의사결정에 어떻게 연결하는가?
7. 변경 후 Post Check 실패 시 Rollback 기준은 무엇인가?
8. DNS/네트워크 장애를 애플리케이션 장애와 어떻게 분리 진단하는가?
9. Python 서버 업그레이드에서 기존 런타임을 덮어쓰지 않고 side-by-side로 설치하는 이유는 무엇인가?
10. Python minor 업그레이드 전에 신규 venv, pip check, compile, unit/functional 검증을 왜 분리해서 수행하는가?
11. Python 런타임 전환 후 어떤 Post Check 조건에서 Rollback해야 하는가?
12. Windows와 Linux 교차검증이 필요한 이유는 무엇인가?
13. CodeQL과 functional test가 각각 잡는 문제의 차이는 무엇인가?
14. 실제 운영 경험과 포트폴리오 시뮬레이션 범위를 어떻게 구분했는가?
15. Dependabot major 업데이트를 자동 병합하지 않는 이유는 무엇인가?
