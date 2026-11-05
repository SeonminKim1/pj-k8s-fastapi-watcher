# TASK: user-job 도메인 모델

## 실행 흐름
1. (병렬) T1, T2
2. (순차) T3
3. (순차) T4
4. (순차) T5
5. (순차) T6

## 작업
- [x] T1 [domain-user-job] `models/user_job.py`(JobStatus, JobResource, UserJob, 허용 리소스·상태 전이) + `ErrorEnum` 4개 추가 — 선행: 없음 — #1
- [x] T2 [domain-user-job] `mongodb.py`를 `AsyncMongoClient(tz_aware=True)`로 전환 + `K8sService(api_client)` 생성자 주입으로 변경 — 선행: 없음 — #2
- [x] T3 [domain-user-job] `UserJobRepository` 구현 + 로컬 MongoDB로 partial 유니크 인덱스·조건부 갱신 직접 확인 — 선행: T1, T2 — #3
- [x] T4 [domain-user-job] `UserJobService` 구현 + 가짜 repository 주입 service 테스트(SPEC 정상·에러 케이스) — 선행: T1, T3 — #4
- [x] T5 [domain-user-job] `core/dependencies.py` + `main.py` lifespan 인덱스 생성 + 의존성 테스트 — 선행: T2, T3, T4 — #5
- [x] T6 [domain-user-job] `CLAUDE.md` 고유 구성 갱신, 완료 체크리스트(ruff·pytest) 수행 — 선행: T5 — #6

## 변경: 2026-10-28 템플릿 입력·개수 한도(api-job-create)
- 이 도메인의 변경 작업은 `docs/api-job-create/task.md`의 T1~T6(#8~#13)으로 진행했다.
