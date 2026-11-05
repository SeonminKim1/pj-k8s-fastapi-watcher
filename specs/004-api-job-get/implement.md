# 구현 기록: job 단건 조회 API

## 진행 기록
- ▶ 1단계 (순차) T001 시작 — 404 응답 문서와 `GET /jobs/{job_id}` 라우터, router 테스트. 기존 service·schema를 엔드포인트로 연결
- ✔ T001 완료 — `src/schemas/error_response.py`(`NOT_FOUND_RESPONSES`), `src/routers/job_router.py`(`GET /jobs/{job_id}`), `tests/test_job_router.py`(8개). ruff 통과, pytest 295 passed
- ■ 1단계 완료 — 다음: 2단계 T002 (README, quickstart 직접 확인, 완료 체크리스트)
- ▶ 2단계 (순차) T002 시작 — README API 표, quickstart 직접 확인
- ⏸ T002 중단 — spec에 없는 상황: quickstart 1에서 생성 응답 시각(마이크로초)과 조회 응답 시각(MongoDB 밀리초)이 다름. 사용자 결정: 서버 시각을 밀리초로 자른다 → 001 data-model·research, 004 plan·tasks(T003 추가)를 먼저 고침
- ▶ 3단계 (순차) T003 시작 — 서버 시각을 밀리초로(생성·상태 갱신·삭제)
- ✔ T003 완료 — `src/services/user_job_service.py`(`_now()`), `tests/test_user_job_service.py`(`test_times_are_milliseconds`). pytest 296 passed. 실제 앱에서 생성 응답 = 조회 응답 확인
- ■ 3단계 완료 — 다음: T002 재개
- ▶ T002 재개 — README, quickstart 시나리오 1~4 직접 확인
- ✔ T002 완료 — `README.md` API 표·에러 상세 링크. 실제 앱(임시 DB `tmp_api_job_get_e2e`, kubeconfig `minikube`, 확인 후 DB 삭제)으로 시나리오 1~4 통과(아래 메모). ruff 통과, pytest 296 passed
- ■ 모든 작업 완료 — 다음: `/sdd-speckit-converge`
- converge: 남은 일 2건(LOW partial) → 수렴 phase T004·T005 추가
- ▶ 수렴 phase (순차) T004 시작 — `/docs` 400 설명 문구를 contracts 기준으로
- ✔ T004 완료 — `src/schemas/error_response.py`. OpenAPI 세 엔드포인트의 400 설명 확인, pytest 296 passed
- ▶ 수렴 phase (순차) T005 시작 — `CLAUDE.md` 고유 모듈에 404 문서
- ✔ T005 완료 — `CLAUDE.md`. pytest 296 passed
- ■ 수렴 phase 완료 — 다음: `/sdd-speckit-converge`
- converge: ✅ 수렴 — 다음: `/code-review`
- `/code-review`: 버그 0건, 지적 5건 → 리뷰 반영 phase T006~T009 추가
- ▶ 리뷰 반영 phase (순차) T006 시작 — `job_id` path 파라미터 설명·example
- ✔ T006 완료 — `src/schemas/job_request.py`(`JobIdPath`, `JOB_ID_EXAMPLES`), `src/routers/job_router.py`, `tests/test_job_router.py`. pytest 297 passed
- ▶ 리뷰 반영 phase (순차) T007 시작 — 404 문서 이름을 job 전용으로
- ✔ T007 완료 — `JOB_NOT_FOUND_RESPONSES`(`src/schemas/error_response.py`, `src/routers/job_router.py`, `CLAUDE.md`). 동작 변화 없음, pytest 297 passed

## spec과 달라진 점
- 없음

## 완료 체크리스트
- [x] `uv run ruff check .` / `uv run ruff format .` 통과
- [x] 레이어 규칙·에러 표현 준수 (Router → Service → Repository, 비즈니스 에러는 `MyApiError`)
- [x] quickstart 시나리오(정상·에러)를 직접 실행해 확인 (`/docs`와 같은 요청을 실제 앱에 curl)
- [x] `/redoc`에서 요청·응답 example이 실제 값으로 보이는지 확인 (OpenAPI JSON의 200·404 example로 확인, `/redoc` 200. 브라우저로는 열어 보지 않음)
- [x] `uv run pytest` 통과 (296 passed. 없음 4경우는 service 테스트, 404·400·문서는 router 테스트)
- [x] README 등 관련 문서 갱신
- [x] tasks.md 모두 완료, converge `✅ 수렴` (두 번째 converge, 남은 일 0건)

## 메모
- 이슈 트래커: 이 기능은 이슈를 만들지 않는다(tasks.md).
- 리뷰 보류(삭제 API에서): `get_job`은 `_id`로 읽은 뒤 Python에서 소유자를 확인하고, `soft_delete`는 쿼리 조건에 `owner_id`를 넣는다. 같은 규칙을 두 방식으로 지킨다. 삭제 API를 만들 때 `find_active_by_owner_and_id`처럼 쿼리 한 곳으로 맞춘다.
- converge 뒤 `/code-review`: 버그 0건, 지적 5건 → 4건은 Phase 5(T006~T009), 1건은 위 보류.
- quickstart 확인(T002): 1) 200, 생성 응답과 본문이 같음 2) 남의 job·형식은 맞지만 없는 ID·`abc` 모두 404 `job_not_found`, 같은 본문 3) 헤더 없음 400 `invalid_user_id` 4) `/jobs/{job_id}`만 404 문서, 200·404 example. 삭제된 job은 삭제 API가 없어 직접 호출하지 않고 service 테스트(`test_get_job_not_found[deleted]`)로 확인한다.
- 첫 확인에서 생성 응답 시각(마이크로초)과 조회 응답 시각(MongoDB 밀리초)이 달라 T003을 추가했다. 가짜 repository를 쓰는 단위 테스트로는 드러나지 않는 차이였다.
