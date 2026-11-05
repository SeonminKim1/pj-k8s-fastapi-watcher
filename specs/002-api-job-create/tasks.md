# 작업: job 생성 API

- **입력**: `specs/002-api-job-create/` (plan.md, spec.md, data-model.md, contracts/, research.md)
- **테스트**: 필수
- **이관 메모**: `docs/api-job-create/task.md`의 `T1`~`T9`을 `T001`~`T009`로 옮겼다. 커밋·이슈의 `T1`은 `T001`과 같다. 작업 이름의 파일명은 당시 이름(`models/user_job.py`, `schemas/job.py`)이다.

## Phase 1: 기반 (Foundational)
- [x] T001 [P] 형식 타입과 템플릿 모델(`WebTemplate`·`JobTemplate`·`JobSize`·`MAX_JOBS_PER_USER`) 정의 + 모델 검증 테스트 — `src/models/k8s_names.py`, `src/models/user_job.py` — 선행: 없음 — #8
- [x] T002 [P] `ErrorEnum` 추가(필드별 9개, `INVALID_PARAMETER` 메시지)와 요청 검증 에러 매핑 + 매핑 테스트 — `src/core/exception/my_exception.py`, `src/core/exception/validation_error.py` — 선행: 없음 — #9
- [x] T003 [P] `web` 템플릿 → Deployment·Service 매니페스트 생성 + 생성 테스트 — `src/services/job_templates.py` — 선행: T001 — #10
- [x] T004 [P] repository 슬롯 저장(`insert_with_slot`, `uniq_owner_slot` 인덱스) + 로컬 MongoDB 확인 — `src/repository/user_job_repository.py` — 선행: T001 — #11

## Phase 2: 유저 스토리 1·3 - 템플릿 등록, 한도와 중복 (P1·P2)
- [x] T005 [US1] [US3] `UserJob`에 `template`·`quota_slot` 추가, `create_job`을 템플릿 입력·개수 한도·`INVALID_USER_ID`·`INVALID_JOB_NAME`으로 변경 + service 테스트 갱신(옛 매니페스트 검증 테스트 제거) — `src/models/user_job.py`, `src/services/user_job_service.py` — 선행: T002, T003, T004 — #12
- [x] T006 [US1] 쓰지 않게 된 옛 코드 제거(`_build_resources`·이름 검사 함수·정규식 상수, repository `insert`, `ALLOWED_RESOURCE_KINDS`, `INVALID_JOB_RESOURCE`) — `src/services/user_job_service.py` 외 — 선행: T005 — #13

## Phase 3: 유저 스토리 1·2 - API와 요청 검증 (P1)
- [x] T007 [US1] [US2] `POST /jobs` 라우터, 검증 에러 핸들러 등록 + router 테스트(에러 표 행마다) — `src/schemas/job.py`, `src/routers/job_router.py`, `src/main.py` — 선행: T006 — #14
- [x] T008 [US2] `/docs`(OpenAPI)에서 실제로 쓰지 않는 422 응답·`HTTPValidationError` 스키마 제거 + 테스트 — `src/main.py`, `tests/test_main.py` — 선행: T007 — #16

## Phase 4: 마무리 (Polish)
- [x] T009 문서 갱신(README API 표, `CLAUDE.md` 고유 구성, `domain-user-job` 변경 섹션), `/docs`에서 정상·에러 케이스 직접 호출, 완료 체크리스트 — 선행: T008 — #15

## Phase 5: 변경 2026-10-28 /docs 422 제거 작업 추가
- T007 작업 확인 중 발견: 검증 에러를 400으로 바꿔 응답하는데 FastAPI가 OpenAPI에 422를 자동으로 넣어 `/docs`가 실제 응답과 다르다. 사용자 요청으로 별도 작업·커밋으로 분리했다.
- 새 T008(#16)을 추가하고, 기존 T008(문서 갱신·완료 체크리스트, #15)은 T009로 번호를 옮겼다(이슈 제목도 변경). 이관 전 문서라 번호를 옮겼고, 지금 규칙은 기존 작업 번호를 바꾸지 않는다.

## 실행 흐름 (Dependencies & Execution Order)
1. (병렬) T001, T002
2. (병렬) T003, T004
3. (순차) T005
4. (순차) T006
5. (순차) T007
6. (순차) T008
7. (순차) T009

## 메모
- 커밋마다 `ruff`·`pytest`가 통과해야 하므로, 기존 동작을 바꾸는 변경(`UserJob` 필수 필드 추가, `create_job` 시그니처)은 T005에 모으고, 그 결과 쓰지 않게 된 코드 제거는 T006으로 분리했다(사용자 요청: 리뷰 단위를 작게). T001·T002·T004는 기존 코드를 건드리지 않고 추가만 한다.
