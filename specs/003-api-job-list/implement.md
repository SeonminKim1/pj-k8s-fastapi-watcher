# 구현 기록: job 목록 조회 API

## 진행 기록
- ▶ 1단계 (순차) T001 시작 — 다른 작업이 함께 쓰는 모델·limit 상수·에러 종류 정의
- ✔ T001 완료 — `models/user_job_models.py`(`JobPosition`, `JobPage`, `JOB_LIST_DEFAULT_LIMIT`·`JOB_LIST_MAX_LIMIT`), `ErrorEnum` 3개, `_PRIORITY`, `test_validation_error.py`. ruff 통과, pytest 222 passed (#19)
- ■ 1단계 완료 — 다음: 2단계 T002, T003
- ▶ 2단계 (병렬) T002, T003 시작 — cursor 인코딩 모듈, repository 위치 조회
- ✔ T002 완료 — `services/job_cursor.py`, `tests/test_job_cursor.py`(왕복 3, 잘못된 cursor 11). pytest 236 passed. `encode_cursor` 인자를 plan의 `UserJob`에서 `JobPosition`으로 바꿈(아래 메모) (#20)
- ✔ T003 완료 — `find_active_by_owner` → `find_active_page(owner_id, status, after, limit)`. 로컬 MongoDB 9.0.2 임시 DB에서 6개 항목 확인 후 DB 삭제(아래 메모). service는 T004까지 옛 메서드를 부르므로 이 커밋 시점에는 실제 repository로 `list_jobs`가 동작하지 않는다(쓰는 곳 없음) (#21)
- ■ 2단계 완료 — 다음: 3단계 T004
- ▶ 3단계 (순차) T004 시작 — service `list_jobs`와 가짜 repository 교체
- ✔ T004 완료 — `user_job_service.py`(`list_jobs -> JobPage`, `_validate_limit`), `tests/test_user_job_service.py`(가짜 `find_active_page`, list 테스트 16개). pytest 253 passed (#22)
- ■ 3단계 완료 — 다음: 4단계 T005
- ▶ 4단계 (순차) T005 시작 — schemas, `GET /jobs` 라우터, router 테스트
- ✔ T005 완료 — `schemas/job_request.py`(`JobListRequest`, `job_list_request()`), `schemas/job_response.py`(`JobSummary`, `JobListResponse`, example), `routers/job_router.py`(`GET /jobs`), `tests/test_job_router.py`(list 테스트 26개). pytest 279 passed. 헤더를 dependency로 옮김(아래 메모) (#23)
- ■ 4단계 완료 — 다음: 5단계 T006
- ▶ 5단계 (순차) T006 시작 — README, 완료 체크리스트, 실제 앱 확인
- ✔ T006 완료 — README API 표에 `GET /jobs`. 로컬 MongoDB 임시 DB로 앱을 띄워 정상·에러 케이스 직접 호출(아래 메모), `/docs`·`/redoc` 200. ruff 통과, pytest 279 passed (#24)
- ■ 5단계 완료 — 모든 작업 완료

## spec과 달라진 점
- 없음

## 완료 체크리스트
- [x] `uv run ruff check .` / `uv run ruff format .` 통과
- [x] 레이어 규칙 준수 (Router → Service → Repository, 비즈니스 에러는 `MyApiError`)
- [x] spec의 정상 케이스와 에러 케이스를 직접 호출해 확인 (`/docs` 대신 실행 중인 앱에 curl, 아래 메모)
- [x] `/redoc`에서 요청·응답 example이 실제 값으로 보이는지 확인 (OpenAPI JSON의 examples로 확인. 브라우저로는 열어 보지 않음) (`.claude/stacks/fastapi.md`의 "API 문서 (OpenAPI)")
- [x] `uv run pytest` 통과 (279 passed, 비즈니스 규칙마다 service 테스트 존재)
- [x] README 등 관련 문서 갱신
- [x] tasks.md 체크리스트 모두 완료

## 메모
- `encode_cursor(position: JobPosition)`: plan은 `encode_cursor(job: UserJob)`이었지만, `decode_cursor`와 같은 타입을 주고받게 해 왕복 테스트를 단순하게 했다. service가 마지막 항목으로 `JobPosition`을 만들어 넘긴다. 외부 동작은 같다.
- T003 로컬 MongoDB 확인(9.0.2, 임시 DB `tmp_api_job_list_*`, 확인 후 삭제): alice 7개(같은 `created_at` 3개 포함)·삭제 1개·bob 1개로
  1. 전체 조회가 `created_at`·`_id` 내림차순, 삭제된 job·남의 job 제외
  2. `limit=2`로 끝까지 넘겼을 때 같은 시각 그룹이 페이지 경계에 걸려도 빠짐·겹침 없음
  3. `status=running` 필터
  4. `status=pending` + `limit=1` 페이지 넘김
  5. cursor 위치의 job을 삭제한 뒤에도 그 위치 뒤가 이어짐
  6. 다른 유저(bob)의 위치로 조회해도 alice의 job만 나옴
  - 실행 계획: MongoDB는 `owner_created_at`이 아니라 `uniq_owner_name`(`{owner_id, name}`, `is_deleted: false` partial)을 골랐다. 쿼리에 `is_deleted: false`가 있어 삭제된 문서가 빠진 partial 인덱스가 더 좁기 때문이다. 유저당 최대 10개를 메모리 정렬하므로 문제없고, 인덱스를 바꾸지 않는다는 plan 결정과도 맞다.
- T005 dependency 설계(plan의 `JobListQuery`·`job_list_query()` → `JobListRequest`·`job_list_request()`): FastAPI 0.162.0에서 직접 확인한 두 가지 때문에 바꿨다. 외부 동작은 spec 그대로다.
  1. FastAPI는 dependency를 엔드포인트 파라미터보다 먼저 실행한다. 헤더를 엔드포인트에 두면 헤더가 없어도 dependency의 `status` 중복 에러가 먼저 나가 spec 우선순위(헤더 1순위)가 깨진다. 헤더를 dependency 파라미터로 옮기면 헤더·limit·status 형식 에러가 있을 때 dependency 본문이 실행되지 않고, 모인 에러에서 우선순위대로 하나가 골라진다. 그래서 요청 모델에 `user_id`가 들어가 이름을 `JobListRequest`로 했다.
  2. `Query(ge=1, le=100)`에 둔 범위 제약은 `error_code()`의 감싸기 밖에서 적용돼 pydantic 기본 에러(`greater_than_equal`)가 나간다. `Annotated[int, Field(ge, le), error_code(...), Query(...)]`처럼 제약을 `error_code` 앞에 둬야 `invalid_limit`이 된다.
- T006 실제 앱 확인(`MONGO_DB_NAME=tmp_api_job_list_e2e`, kubeconfig `minikube`, 확인 후 DB 삭제): `POST /jobs`로 alice 5개·bob 1개를 만든 뒤
  - 기본 조회: `job4 … job0`, `next_cursor: null`(bob 제외)
  - `limit=2`로 넘기기: `[job4 job3] [job2 job1] [job0]`, 마지막만 `null`
  - `status=running`: `{"items": [], "next_cursor": null}`
  - 400: `limit=0`·`limit=abc` → `invalid_limit`, `status=bad`·`status` 두 번 → `invalid_job_status`, `cursor=bad`·`cursor=` → `invalid_cursor`, 헤더 없음 + `status` 두 번 → `invalid_user_id`
  - OpenAPI: 응답 200·400·500, 파라미터 4개에 examples. `value: None`인 "보내지 않음" example은 `value` 키 없이 나가 Swagger UI에서 빈 칸으로 보인다.

## 변경: 2026-11-03 코드 리뷰 반영
`/code-review` 지적 7건 중 4건을 반영하고 1건은 규칙으로 명시, 2건은 보류했다.
- 반영
  1. **(버그) 범위 밖 시각 cursor가 500**: `0001-01-01T00:00:00+14:00`처럼 UTC로 바꾸면 1년 이전이 되는 시각을 담은 cursor가 디코딩을 통과하고, MongoDB 쿼리 인코딩에서 `OverflowError`가 나서 500(`unknown_error`)이 됐다. 재현을 확인했다. `decode_cursor`가 시각을 UTC로 맞추고 `OverflowError`를 `INVALID_CURSOR`로 바꾼다. 테스트 2개 추가
  2. **`limit`·`cursor` 중복 지정**: `status`만 막고 있어 `?limit=5&limit=100`이 조용히 마지막 값으로 처리됐다. 세 쿼리 모두 중복이면 그 필드의 에러(cursor는 `invalid_cursor`, `_PRIORITY`에 추가). spec 수정, router 테스트 4개 추가
  3. **표준 base64 문자 허용**: `b64decode(altchars=b"-_", validate=True)`가 `+`·`/`도 받아 줬다(`+/+/` 디코딩 확인). 디코딩 전에 base64url 정규식으로 거른다. 테스트 2개 추가
  6. **설명에 박힌 숫자**: `limit` 범위·기본값 설명을 상수로 만든다. `ErrorEnum.INVALID_LIMIT` 메시지는 enum 값이라 그대로 두고 상수 옆에 "상한을 바꾸면 메시지도 고친다" 주석
- 규칙으로 명시
  7. **`schemas/`에 dependency**: 라우터는 "파싱 → service 호출"만 하고 `UserIdHeader`처럼 요청 파싱 타입은 이미 `schemas/`에 있어 위치는 유지했다. `.claude/stacks/fastapi.md` schemas 행에 "모델만으로 검증할 수 없는 요청 파싱은 요청 모듈에 dependency로" 한 줄 추가
- 보류
  4. **목록 인덱스**: 실제 실행 계획은 `uniq_owner_name`(`is_deleted: false` partial)을 써서 삭제된 job은 훑지 않는다(T003 확인). 메모리 정렬 대상은 유저당 최대 10개. 한도를 늘릴 때 partial `{owner_id: 1, created_at: -1, _id: -1}` 인덱스를 추가한다
  5. **service·schema의 `limit` 이중 검사**: `owner_id`·`name`과 같은 "schema를 거치지 않는 호출자 대비" 패턴이고 같은 상수를 쓰므로 어긋나지 않는다
- 확인: ruff 통과, pytest 287 passed

