# 기능 Lifecycle · 업그레이드 · 릴리스 관리

`DAOUTECH_IDC`의 기능은 **등록 → 분석 → 구현 → 검증 → 릴리스 후보 → 면접 근거** 순서로 관리합니다.

## 1. 단일 기준 데이터

- `portfolio-manifest.json`: 저장소 파일별 역할과 제출 필수 파일
- `feature-catalog.json`: 면접 도메인, 준비 요구사항, 업그레이드 백로그, 릴리스 채널
- `tools/portfolio_manager.py`: 위 두 파일과 실제 `git ls-files`를 비교해 전체 상태를 결정적으로 집계

새 파일을 추가하고 Manifest에 등록하지 않으면 Lifecycle 리포트가 `BLOCKED`가 됩니다.

## 2. 기능 변경 절차

1. **등록**: 파일/기능의 목적과 category를 Manifest에 추가합니다.
2. **분류**: category가 Feature Catalog의 면접 도메인에 포함되는지 확인합니다.
3. **구현**: 실제 운영 시스템을 변경하지 않는 안전한 방식으로 코드/시뮬레이터를 구현합니다.
4. **검증**: 관련 compile, unit, functional, scenario, CodeQL 검사를 통과합니다.
5. **증거**: 실행 결과와 설명 포인트가 Actions Artifact/문서에 남는지 확인합니다.
6. **릴리스 후보**: `release-readiness.yml`로 전체 검증과 정적 사이트 패키징을 수행합니다.
7. **면접 준비**: `INTERVIEW_GUIDE.md`와 `interview-readiness.md`로 설명 범위와 근거를 점검합니다.

## 3. 변경 유형별 필수 검증

| 변경 | 최소 검증 |
|---|---|
| Python 운영 도구 | compile + unit + functional |
| 운영 판단 규칙 | unit + scenario regression |
| HTML 시뮬레이터 | JavaScript syntax + headless loading |
| Workflow | repository review + PR Actions |
| 의존성 minor/patch | Dependabot PR + 전체 통합 검수 |
| 의존성 major | 별도 PR + 호환성 검토 + 전체 통합 검수 |
| 문서/면접 근거 | local link + Manifest/Feature Catalog coverage |
| 릴리스 | lifecycle READY + 전체 검수 + 테스트 + CodeQL 상태 확인 |

## 4. 업그레이드 우선순위

- **P0**: 면접 설명/검증/릴리스 증거가 없거나 전체 관리가 깨지는 문제
- **P1**: 운영 판단 품질, 시나리오, 관측성, 설명력을 높이는 기능
- **P2**: 배포 편의, UI 개선, 장기 확장

`feature-catalog.json`의 `upgrade_backlog`가 자동 `upgrade-plan.md`로 변환됩니다.

## 5. 릴리스 채널

### candidate

면접 전 특정 시점의 전체 검증 결과를 Actions Artifact로 보관합니다. 실제 운영 배포물이 아니라 **검증된 포트폴리오 스냅샷**입니다.

### portfolio-site

`index.html`과 HTML 시뮬레이터를 `_site`에 구성합니다. GitHub Pages 설정이 활성화되면 실제 Pages 배포로 확장할 수 있습니다.

### tagged

`v*` 태그가 생성되면 같은 릴리스 검증 Workflow를 수행해 태그 기준 결과를 재현할 수 있게 합니다.

## 6. 릴리스 금지 조건

다음 중 하나라도 발생하면 릴리스 후보를 `BLOCKED`로 봅니다.

- Manifest 미등록 추적 파일
- Manifest에만 있고 실제 Git 추적에서 누락된 파일
- Feature Catalog에 없는 category
- 필수 면접 문서/관리 자동화/릴리스 파일 누락
- Repository Review ERROR/WARN
- Execution Analysis BLOCKED
- Functional FAIL
- Scenario Regression FAIL
- Unit Test FAIL
- CodeQL Workflow 실패

## 7. 운영 경험과 시뮬레이션 경계

릴리스 또는 면접 설명에서 저장소 시뮬레이션 결과를 실제 고객 환경의 운영 실적으로 표현하지 않습니다. 포트폴리오는 실제 운영 관점을 재현하기 위한 안전한 코드/시뮬레이션이며, 실운영 데이터는 포함하지 않습니다.
