# TASK: job 목록 조회 API

## 실행 흐름
1. (순차) T1
2. (병렬) T2, T3
3. (순차) T4
4. (순차) T5
5. (순차) T6

## 작업
- [ ] T1 [api-job-list] `models/user_job.py`(`JobPosition`, `JobPage`, limit 상수) + `ErrorEnum` 3개(`INVALID_LIMIT`, `INVALID_JOB_STATUS`, `INVALID_CURSOR`) + `_PRIORITY` 추가, `test_validation_error.py` 우선순위 테스트 — 선행: 없음 — #19
- [ ] T2 [api-job-list] `services/job_cursor.py`(`encode_cursor`, `decode_cursor`) + `tests/test_job_cursor.py` — 선행: T1 — #20
- [ ] T3 [api-job-list] repository `find_active_by_owner` → `find_active_page` + 로컬 MongoDB 임시 DB로 위치 조건·같은 시각 정렬·필터 확인 — 선행: T1 — #21
- [ ] T4 [api-job-list] `UserJobService.list_jobs(owner_id, limit, cursor, status) -> JobPage` + 가짜 repository 교체, service 테스트(spec 정상·에러 케이스) — 선행: T2, T3 — #22
- [ ] T5 [api-job-list] schemas(`JobListQuery`·`job_list_query()`, `JobSummary`·`JobListResponse`·example) + `GET /jobs` 라우터 + router 테스트(요청 검증 에러, `status` 중복, example 검증) — 선행: T4 — #23
- [ ] T6 [api-job-list] README API 표, `docs/domain-user-job/spec.md` 확인, 완료 체크리스트(ruff·pytest·`/docs`·`/redoc` 직접 확인) — 선행: T5 — #24
