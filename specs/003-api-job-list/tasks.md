# 작업: job 목록 조회 API

- **입력**: `specs/003-api-job-list/` (plan.md, spec.md, data-model.md, contracts/, research.md)
- **테스트**: 필수
- **이관 메모**: `docs/api-job-list/task.md`의 `T1`~`T6`을 `T001`~`T006`으로 옮겼다. 커밋·이슈의 `T1`은 `T001`과 같다. 작업 이름의 파일명은 당시 이름(`models/user_job.py`, `JobListQuery`)이다.

## Phase 1: 기반 (Foundational)
- [x] T001 모델(`JobPosition`, `JobPage`, limit 상수) + `ErrorEnum` 3개(`INVALID_LIMIT`, `INVALID_JOB_STATUS`, `INVALID_CURSOR`) + `_PRIORITY` 추가, 우선순위 테스트 — `src/models/user_job.py`, `src/core/exception/`, `tests/test_validation_error.py` — 선행: 없음 — #19
- [x] T002 [P] cursor 인코딩(`encode_cursor`, `decode_cursor`) + 테스트 — `src/services/job_cursor.py`, `tests/test_job_cursor.py` — 선행: T001 — #20
- [x] T003 [P] repository `find_active_by_owner` → `find_active_page` + 로컬 MongoDB 임시 DB로 위치 조건·같은 시각 정렬·필터 확인 — `src/repository/user_job_repository.py` — 선행: T001 — #21

## Phase 2: 유저 스토리 1~3 - 목록, 나눠 받기, 상태 필터 (P1~P3)
- [x] T004 [US1] [US2] [US3] `UserJobService.list_jobs(owner_id, limit, cursor, status) -> JobPage` + 가짜 repository 교체, service 테스트(정상·에러 케이스) — `src/services/user_job_service.py`, `tests/test_user_job_service.py` — 선행: T002, T003 — #22
- [x] T005 [US1] [US2] [US3] schemas(요청 dependency, `JobSummary`·`JobListResponse`·example) + `GET /jobs` 라우터 + router 테스트(요청 검증 에러, `status` 중복, example 검증) — `src/schemas/job_request.py`, `src/schemas/job_response.py`, `src/routers/job_router.py` — 선행: T004 — #23

## Phase 3: 마무리 (Polish)
- [x] T006 README API 표, `domain-user-job` spec 확인, 완료 체크리스트(ruff·pytest·`/docs`·`/redoc` 직접 확인) — 선행: T005 — #24

## 실행 흐름 (Dependencies & Execution Order)
1. (순차) T001
2. (병렬) T002, T003
3. (순차) T004
4. (순차) T005
5. (순차) T006
