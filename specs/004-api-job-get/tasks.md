# 작업: job 단건 조회 API

- **입력**: `specs/004-api-job-get/` (plan.md, spec.md, data-model.md, contracts/, research.md, quickstart.md)
- **테스트**: 필수 (service `get_job`의 소유권·없음·삭제됨·잘못된 ID·유저 ID 테스트는 `tests/test_user_job_service.py`에 있음)
- **이슈 트래커**: 이 기능은 이슈를 만들지 않는다(사용자 결정)

## Phase 1: 유저 스토리 1·2 - 내 job 상세, 내 것이 아니면 없음 (P1) 🎯 MVP
- **목표**: `GET /jobs/{job_id}`가 자기 job은 생성 응답과 같은 상세로, 남의 job·없음·삭제됨·잘못된 ID는 같은 404 `job_not_found`로 응답
- **독립 테스트**: router 테스트(가짜 service)와 quickstart 시나리오 1~3
- [x] T001 [US1] [US2] 404 응답 문서와 `GET /jobs/{job_id}` 라우터 + router 테스트 — `src/schemas/error_response.py`, `src/routers/job_router.py`, `tests/test_job_router.py` — 선행: 없음
  - `error_response.py`: `NOT_FOUND_RESPONSES`(404: `ErrorResponse` + `job_not_found` example), `COMMON_ERROR_RESPONSES` 주석의 code 목록 기준을 "각 기능의 contracts 에러 표"로
  - 라우터: `response_model=JobResponse`, `description`에 `specs/004-api-job-get/contracts/get-job.md` 경로, `responses`에 200 example `JOB_RESPONSE_EXAMPLE`·`NOT_FOUND_RESPONSES`
  - 테스트: 200 본문·`get_job(owner_id, job_id)` 전달, `running` 상태 job의 상태·`updated_at`이 그대로 나옴(US1/AC2), `JOB_NOT_FOUND` 404 본문, 헤더 없음·형식 오류 400 `invalid_user_id`(service 미호출), OpenAPI 200·400·404·500, 404 example, `POST /jobs`·`GET /jobs`에 404 없음, 200 example이 `JobResponse`로 검증

## Phase 2: 유저 스토리 1 - 생성 응답과 같은 시각 (P1)
- **목표**: 생성 응답과 조회 응답의 시각이 같다(US1/AC1). quickstart 시나리오 1에서 생성 응답(마이크로초)과 조회 응답(MongoDB 밀리초)이 달랐다
- [x] T003 [US1] 서버 시각 `_now()`(UTC, 밀리초로 자름)를 생성·상태 갱신·삭제에 적용 + service 테스트(세 시각이 밀리초 단위) — `src/services/user_job_service.py`, `tests/test_user_job_service.py` — 선행: T001

## Phase 3: 마무리 (Polish)
- [x] T002 README API 표에 `GET /jobs/{job_id}`·에러 상세 링크, quickstart 시나리오 1~4 직접 확인, 완료 체크리스트 — `README.md` — 선행: T003

## Phase 4: 수렴 (Convergence)
- [x] T004 `/docs`에 보이는 400 설명 문구 "(목록은 엔드포인트 설명의 spec 참고)"를 contracts 기준으로 고친다 — `src/schemas/error_response.py` — 출처: plan: `COMMON_ERROR_RESPONSES` code 목록 기준 (partial)
- [x] T005 `CLAUDE.md` 고유 모듈의 `error_response.py` 설명에 404 문서(`NOT_FOUND_RESPONSES`)를 더한다 — `CLAUDE.md` — 출처: Constitution I (partial)
- **실행 순서**: 1. (순차) T004 2. (순차) T005

## 실행 흐름 (Dependencies & Execution Order)
1. (순차) T001
2. (순차) T003
3. (순차) T002

## 구현 전략
- **MVP**: Phase 1(US1·US2)이 끝나면 독립 확인 가능. US1과 US2는 같은 엔드포인트의 정상·에러 응답이라 한 작업으로 묶었다
