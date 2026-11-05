# 작업: user-job 도메인 모델

- **입력**: `specs/001-domain-user-job/` (plan.md, spec.md, data-model.md, research.md)
- **테스트**: 필수

## Phase 1: 기반 (Foundational)
- [x] T001 [P] 모델(`JobStatus`, `JobResource`, `UserJob`, 상태 전이) + `ErrorEnum` 추가 — `src/models/enums.py`, `src/models/user_job_models.py`, `src/core/exception/my_exception.py` — 선행: 없음 — #1
- [x] T002 [P] `AsyncMongoClient(tz_aware=True)` 전환 + `K8sService(api_client)` 생성자 주입 — `src/core/db/mongodb.py`, `src/services/k8s_service.py` — 선행: 없음 — #2
- [x] T003 `UserJobRepository` 구현 + 로컬 MongoDB로 partial 유니크 인덱스·조건부 갱신 직접 확인 — `src/repository/user_job_repository.py` — 선행: T001, T002 — #3

## Phase 2: 유저 스토리 1~3 - 저장·조회, 상태 갱신, 삭제 (P1~P3)
- [x] T004 [US1] [US2] [US3] `UserJobService` 구현 + 가짜 repository 주입 service 테스트(정상·에러 케이스) — `src/services/user_job_service.py`, `tests/test_user_job_service.py` — 선행: T001, T003 — #4
- [x] T005 [US1] `dependencies.py` + `main.py` lifespan 인덱스 생성 + 의존성 테스트 — `src/core/dependencies.py`, `src/main.py`, `tests/test_dependencies.py` — 선행: T002, T003, T004 — #5

## Phase 3: 마무리 (Polish)
- [x] T006 `CLAUDE.md` 고유 구성 갱신, 완료 체크리스트(ruff·pytest) — `CLAUDE.md` — 선행: T005 — #6

## 실행 흐름 (Dependencies & Execution Order)
1. (병렬) T001, T002
2. (순차) T003
3. (순차) T004
4. (순차) T005
5. (순차) T006
