# 작업: job 생성 API

- **입력**: `specs/002-api-job-create/` (plan.md, spec.md, data-model.md, contracts/, research.md)
- **테스트**: 필수

## Phase 1: 기반 (Foundational)
- [x] T001 [P] 형식 타입과 템플릿 모델(`WebTemplate`·`JobTemplate`·`JobSize`·`MAX_JOBS_PER_USER`) 정의 + 모델 검증 테스트 — `src/models/k8s_names.py`, `src/models/user_job_models.py` — 선행: 없음 — #8
- [x] T002 [P] `ErrorEnum` 추가(필드별 9개, `INVALID_PARAMETER` 메시지)와 요청 검증 에러 매핑 + 매핑 테스트 — `src/core/exception/my_exception.py`, `src/core/exception/validation_error.py` — 선행: 없음 — #9
- [x] T003 [P] `web` 템플릿 → Deployment·Service 매니페스트 생성 + 생성 테스트 — `src/services/job_templates.py` — 선행: T001 — #10
- [x] T004 [P] repository 슬롯 저장(`insert_with_slot`, `uniq_owner_slot` 인덱스) + 로컬 MongoDB 확인 — `src/repository/user_job_repository.py` — 선행: T001 — #11

## Phase 2: 유저 스토리 1·3 - 템플릿 등록, 한도와 중복 (P1·P2)
- [x] T005 [US1] [US3] `UserJob`에 `template`·`quota_slot` 추가, `create_job`을 템플릿 입력·개수 한도·`INVALID_USER_ID`·`INVALID_JOB_NAME`으로 변경 + service 테스트(템플릿 입력·한도·형식 규칙) — `src/models/user_job_models.py`, `src/services/user_job_service.py` — 선행: T002, T003, T004 — #12
- [x] T006 [US1] 매니페스트 직접 입력 경로 제거(`_build_resources`·이름 검사 함수·정규식 상수, `ALLOWED_RESOURCE_KINDS`, `INVALID_JOB_RESOURCE`) — `src/services/user_job_service.py`, `src/models/user_job_models.py`, `src/core/exception/my_exception.py` — 선행: T005 — #13

## Phase 3: 유저 스토리 1·2 - API와 요청 검증 (P1)
- [x] T007 [US1] [US2] `POST /jobs` 라우터, 검증 에러 핸들러 등록 + router 테스트(에러 표 행마다) — `src/schemas/job_request.py`, `src/schemas/job_response.py`, `src/schemas/common_request.py`, `src/schemas/error_response.py`, `src/routers/job_router.py`, `src/main.py` — 선행: T006 — #14
- [x] T008 [US2] `/docs`(OpenAPI)에서 실제로 쓰지 않는 422 응답·`HTTPValidationError` 스키마 제거 + 테스트 — `src/main.py`, `tests/test_main.py` — 선행: T007 — #16

## Phase 4: 마무리 (Polish)
- [x] T009 문서 갱신(README API 표, `CLAUDE.md` 고유 구성, `specs/001-domain-user-job/` 문서), `/docs`에서 정상·에러 케이스 직접 호출, 완료 체크리스트 — 선행: T008 — #15

## 실행 흐름 (Dependencies & Execution Order)
1. (병렬) T001, T002
2. (병렬) T003, T004
3. (순차) T005
4. (순차) T006
5. (순차) T007
6. (순차) T008
7. (순차) T009

## 메모
- 커밋마다 `ruff`·`pytest`가 통과해야 하므로, 도메인 동작을 바꾸는 작업(`UserJob` 필수 필드, `create_job` 시그니처)은 T005에 모으고, 매니페스트 직접 입력 경로 제거는 T006으로 나눈다(리뷰 단위를 작게). T001·T002·T004는 기존 코드를 건드리지 않고 추가만 한다.
