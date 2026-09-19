# 업그레이드·출시 관리 계획

| 우선순위 | ID | 대상 | 목표 | 완료 기준 |
|---|---|---|---|---|
| P0 | UPG-001 | evidence | 각 핵심 기능의 면접 설명 포인트와 실행 증거를 하나의 자동 리포트로 유지 | interview-readiness.md에서 모든 도메인이 파일과 설명 포인트를 보유 |
| P0 | UPG-002 | release | 면접 직전 검증 결과와 정적 포트폴리오를 릴리스 후보 Artifact로 패키징 | release-readiness workflow가 전체 검증 후 bundle Artifact를 생성 |
| P0 | UPG-007 | python-runtime | Python 3.14 안정 계열 업그레이드를 side-by-side, 신규 venv, strict precheck, Post Check, Rollback 기준으로 관리 | Ubuntu/Windows × Python 3.12/3.13/3.14 교차검증과 Python upgrade strict precheck가 모두 PASS |
| P1 | UPG-003 | scenario | 스토리지·네트워크·배치·변경 외 추가 운영 장애 시나리오 확장 | 새 시나리오는 expected 결과와 단위/회귀 테스트를 동반 |
| P1 | UPG-004 | observability | 운영 자동화 결과를 공통 상태 모델과 증거 포맷으로 정규화 | 핵심 Python 도구가 상태/근거/종료코드 설명을 문서와 테스트로 보유 |
| P1 | UPG-005 | interview | 기능별 예상 기술면접 질문과 답변 근거 파일 연결 | INTERVIEW_GUIDE에서 주요 운영 도메인별 질문·근거·주의사항 확인 가능 |
| P2 | UPG-006 | pages | GitHub Pages 활성화 시 검증된 정적 사이트를 공식 배포 Workflow로 전환 | 저장소 Pages 설정 활성화 후 deploy-pages 성공 |

## 관리 규칙

1. 새 기능은 Manifest와 Feature Catalog 관리 범위에 포함합니다.
2. 기능 변경은 compile/unit/functional/scenario/CodeQL 중 관련 검증을 통과해야 합니다.
3. major 의존성 업데이트는 별도 PR로 검토합니다.
4. 릴리스 후보는 release-readiness Workflow가 생성한 Artifact를 사용합니다.
5. 실제 운영 경험과 시뮬레이션 결과를 면접에서 혼동해 설명하지 않습니다.
