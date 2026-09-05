# IDC Operations Runbook

> 이 문서는 포트폴리오 시뮬레이터/도구의 실행 기준입니다. 실제 운영 환경에서는 조직의 승인 절차, 변경 정책, 보안 정책을 우선합니다.

## 1. 장애 최초 인지

1. 장애 시간과 최초 알람을 기록합니다.
2. 단일 알람인지 다중 연쇄 알람인지 구분합니다.
3. 서버 자원 → 서비스 → 네트워크 → 배치/백업 영향 순으로 범위를 좁힙니다.
4. 변경 작업 직후라면 변경 이력을 먼저 확인합니다.

권장 도구:

```bash
python3 healthcheck.py --config check.json
python3 log_analyzer.py <logfile>
python3 alert_correlator.py <alerts.json>
```

## 2. 심각도와 에스컬레이션

| 기준 | 예시 | 권장 판단 |
|---|---|---|
| SEV-1 | 광범위 서비스 중단, 데이터 손상 위험 | 즉시 에스컬레이션, 변경 중단, 복구 우선 |
| SEV-2 | 핵심 서비스/마감 업무 영향 | 원인 범위 확인과 우회/복구 병행 |
| SEV-3 | 일부 기능 저하, 충분한 SLA 여유 | 모니터링 강화 후 계획 조치 |

다음 중 하나면 즉시 상위 담당자/유관 부서 확인 대상으로 봅니다.

- SLA 잔여시간이 20% 이하
- 백업 무결성 실패
- 변경 후 Post Check 실패
- 데이터베이스/스토리지 Critical 알람과 다수 후행 장애가 동시에 발생
- 자동 재기동 상한 도달

## 3. 배치 마감 장애

1. 실패 Job 자체보다 후행 Job과 Critical Path를 먼저 확인합니다.
2. 독립 Job은 불필요하게 중단하지 않습니다.
3. 재실행 전에 입력/선행조건을 검증합니다.
4. 강제 완료는 후행 데이터 정합성 영향을 확인한 뒤 판단합니다.
5. 예상 완료시간이 SLA를 넘으면 즉시 마감 영향으로 에스컬레이션합니다.

실습: `batch-operations-lab.html`, `../scenarios/002-batch-critical-path.json`

## 4. 변경 작업 및 Rollback

변경 전:

- 변경 목적/범위/대상 확인
- 현재 Health 상태 저장
- 백업 또는 복구 지점 확인
- Rollback 명령/절차 준비

변경 후:

- 프로세스/서비스 상태
- 포트/연결
- 핵심 업무 Health Check
- 오류 로그 증가 여부

Rollback 조건 예시:

- 핵심 Health Check 실패
- 오류율이 변경 전 기준보다 지속 증가
- SLA 임계 도달 위험
- 원인 확인 없이 영향 범위 확대

실습: `change-management-lab.html`, `../scenarios/005-change-rollback.json`

## 5. 백업 검증

잡 상태가 `SUCCESS`여도 복구 가능성을 별도로 확인합니다.

```bash
python3 backup_verify.py manifest.json
```

확인 순서:

1. 파일 존재
2. 최소 크기
3. 생성 시각/신선도
4. SHA-256 기준값 일치
5. 복구에 필요한 체인이 모두 존재하는지 확인

해시 불일치는 복구 신뢰성 문제로 취급합니다.

## 6. 네트워크/DNS 장애

1. 로컬 인터페이스/라우팅
2. 대상 IP 도달성
3. DNS 해석
4. TCP 포트
5. L4/LB/방화벽 구간
6. 애플리케이션 응답

DNS 장애에서는 IP 직접 통신 여부와 이름 해석 결과를 분리해 확인합니다.

실습: `network-path.html`, `../scenarios/004-dns-path-failure.json`

## 7. Capacity와 SLA

```bash
python3 disk_forecast.py
python3 capacity_planner.py capacity.json
python3 sla_calculator.py --days 30 --downtime 20 --targets 99.9 99.95 99.99
```

임계치 초과 후 대응보다 추세를 이용해 증설/정리 시점을 사전에 판단합니다. SLA는 장애 종료 후 보고용 숫자가 아니라 장애 중 우선순위를 정하는 기준으로도 사용합니다.

## 8. 장애 종료와 교대 인수인계

장애 종료 후 반드시 남길 항목:

- 발생/인지/복구 시각
- 영향 범위
- Root Cause 또는 현재까지 확인된 원인 후보
- 수행 조치
- 미완료 조치
- 재발 방지 항목
- 다음 확인 시각
- 유관 부서/후속 담당

```bash
python3 incident_report.py incident.json --output incident-report.md
```

## 9. 포트폴리오 회귀 검증

```bash
python3 scenario_runner.py scenarios --report scenario-report.md --json-report scenario-report.json
```

시나리오 계산 결과가 JSON의 `expected`와 다르면 회귀 실패로 판단합니다. 이는 시뮬레이터의 화면이 정상이라는 것과 별개로 **운영 판단 규칙이 변경되어 버리지 않았는지** 확인하기 위한 테스트입니다.
