# 기능 Lifecycle · 업그레이드 · 릴리스 관리

`DAOUTECH_IDC`의 기능은 **등록 → 분석 → 구현 → 검증 → 릴리스 후보 → 면접 근거** 순서로 관리합니다.

## 1. 단일 기준 데이터

- `portfolio-manifest.json`: 저장소 파일별 역할과 제출 필수 파일
- `feature-catalog.json`: 면접 도메인, 준비 요구사항, 업그레이드 백로그, 릴리스 채널
- `../tools/portfolio_manager.py`: 위 두 파일과 실제 `git ls-files`를 비교해 전체 상태를 결정적으로 집계

새 파일을 추가하고 Manifest에 등록하지 않으면 Lifecycle 리포트가 `BLOCKED`가 됩니다.

## 2. 기능 변경 절차

1. **등록**: 파일/기능의 목적과 category를 Manifest에 추가합니다.
2. **분류**: category가 Feature Catalog의 면접 도메인에 포함되는지 확인합니다.
3. **구현**: 실제 고객 데이터와 운영 자격증명을 저장소에 포함하지 않고 안전한 변경 경계를 정의합니다.
4. **검증**: 관련 compile, unit, functional, scenario, CodeQL 검사를 통과합니다.
5. **증거**: 실행 결과와 설명 포인트가 Actions Artifact/문서에 남는지 확인합니다.
6. **릴리스 후보**: `release-readiness.yml`로 전체 검증과 정적 사이트 패키징을 수행합니다.
7. **면접 준비**: `INTERVIEW_GUIDE.md`와 `interview-readiness.md`로 설명 범위와 근거를 점검합니다.

## 3. 변경 유형별 필수 검증

| 변경 | 최소 검증 |
|---|---|
| Python 운영 도구 | compile + unit + functional |
| Python Runtime 실제 Cutover | exact target + 신규 venv + pip check + compile + unit + functional + scenario + pointer Post Check |
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

`main`이 변경될 때 전체 검증 결과를 Actions Artifact로 자동 보관합니다. 실제 운영 배포물이 아니라 **검증된 포트폴리오 스냅샷**입니다.

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

## 7. Repository Governance

Lifecycle Workflow는 GitHub API로 다음 관리자 설정을 읽어 별도 `repository-governance.md/json` 증거를 생성합니다.

### 목표 Repository Description

```text
IDC 시스템 엔지니어 포트폴리오 | Python 운영 자동화·배치·장애·백업·변경관리·Windows/Linux 교차검증·CI/릴리스
```

### 목표 main Branch Protection

- `main` 변경은 Pull Request를 통해 수행
- 개인 포트폴리오이므로 필수 승인 수는 0으로 두어 본인 PR 병합 가능
- 필수 상태검사:
  - `전체 파일 검수·실행 분석·제출 판정`
  - `CodeQL · python`
  - `CodeQL · javascript-typescript`
- merge 전에 최신 `main` 반영 요구
- Conversation resolution 요구
- Force push 차단
- Branch deletion 차단

현재 연결된 GitHub App은 Administration 쓰기 권한을 제공하지 않으므로 이 두 설정을 Workflow가 임의로 변경하지 않습니다. 대신 설정이 기준과 다르면 `ACTION_REQUIRED`와 GitHub Actions warning으로 명확하게 노출합니다.

## 8. Python Runtime 변경 경계

`../python_server_upgrade.py`의 기본 모드는 precheck입니다. 실제 Runtime 변경은 `--apply --confirm APPLY`에서만 수행합니다.

실제 Apply에서도 OS/system Python 자체는 교체하지 않습니다. 이미 side-by-side로 설치된 목표 Python을 이용해 immutable venv release를 만들고, 모든 검증 성공 후 애플리케이션용 stable runtime pointer만 전환합니다.

이 경계는 다음 위험을 줄입니다.

- 시스템 도구가 의존하는 Python 파손
- 기존 runtime 즉시 삭제로 인한 Rollback 불가
- 검증되지 않은 venv로 서비스 전환
- 변경 실패 후 원인분석 증거 소실

## 9. 운영 경험과 시뮬레이션 경계

릴리스 또는 면접 설명에서 저장소 시뮬레이션 결과를 실제 고객 환경의 운영 실적으로 표현하지 않습니다. 포트폴리오는 실제 운영 관점을 재현하기 위한 안전한 코드/시뮬레이션이며, 실운영 데이터는 포함하지 않습니다.

GitHub-hosted Runner에서 수행하는 실제 managed Runtime Cutover도 운영 고객 서버를 변경한 실적이 아니라 **실제 전환 절차가 격리 서버에서 실행·검증됐다는 재현 증거**로 설명합니다.
