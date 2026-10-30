# IMPLEMENT: job 생성 API

## 진행 기록
- ▶ 1단계 (병렬) T1, T2 시작 — 형식 타입·템플릿 모델, ErrorEnum·검증 에러 매핑(이후 작업의 기반)
- ✔ T1 완료 — `src/models/k8s_names.py` 추가, `src/models/user_job.py`에 `JobSize`·`WebTemplate`·`JobTemplate`·`MAX_JOBS_PER_USER` 추가, `tests/test_user_job_model.py`. pytest 146 passed (#8)
- ✔ T2 완료 — `ErrorEnum` 9개 추가·`INVALID_PARAMETER` 메시지 변경, `src/core/exception/validation_error.py`(`to_error_enum`), `tests/test_validation_error.py`. pytest 174 passed (#9)
- ■ 1단계 완료 — 다음: 2단계 T3, T4
- ▶ 2단계 (병렬) T3, T4 시작 — web 템플릿 매니페스트 생성, repository 슬롯 저장
- ✔ T3 완료 — `src/services/job_templates.py`(`build_resources`, `SIZE_PRESETS`, `KINDS_BY_TYPE`), `tests/test_job_templates.py`. pytest 185 passed (#10)
- ✔ T4 완료 — `src/repository/user_job_repository.py`에 `insert_with_slot`·`JobQuotaExceededError`·`uniq_owner_slot` 인덱스 추가. 로컬 MongoDB 9.0.2 임시 DB에서 9개 항목 확인 후 DB 삭제(아래 메모). pytest 185 passed (#11)
- ■ 2단계 완료 — 다음: 3단계 T5
- ▶ 3단계 (순차) T5 시작 — UserJob·create_job을 템플릿 입력·개수 한도로 변경
- ✔ T5 완료 — `src/models/user_job.py`(`template`·`quota_slot`), `src/services/user_job_service.py`(`create_job(owner_id, name, template)`, `INVALID_USER_ID`·`INVALID_JOB_NAME`·`JOB_QUOTA_EXCEEDED`), `tests/test_user_job_service.py`(가짜 repository 슬롯 규칙, 매니페스트 검증 테스트 제거, 한도 테스트 추가). pytest 175 passed (#12)
- ■ 3단계 완료 — 다음: 4단계 T6
- ▶ 4단계 (순차) T6 시작 — 쓰지 않게 된 옛 매니페스트 검증 코드 제거
- ✔ T6 완료 — service 정규식·이름 검사 함수·`_build_resources`, repository `insert`, `ALLOWED_RESOURCE_KINDS`, `INVALID_JOB_RESOURCE` 제거(116줄 삭제). 동작 변화 없음, pytest 175 passed (#13)
- ■ 4단계 완료 — 다음: 5단계 T7
- ▶ 5단계 (순차) T7 시작 — schema·`POST /jobs` router·검증 에러 핸들러 연결
- ✔ T7 완료 — `src/schemas/job.py`, `src/schemas/error.py`, `src/routers/job_router.py`, `src/main.py`(라우터 등록, `RequestValidationError` → 400 핸들러), `tests/test_job_router.py`. pytest 205 passed (#14)
- ■ 5단계 완료 — 다음: 6단계 T8(작업 확인 중 추가)
- ▶ 6단계 (순차) T8 시작 — `/docs`에서 실제로 쓰지 않는 422 제거(task·plan·spec에 변경 반영)
- ✔ T8 완료 — `src/main.py`(`_openapi_without_422`), `tests/test_main.py`(`test_openapi_has_no_422`). pytest 206 passed (#16)
- ■ 6단계 완료 — 다음: 7단계 T9
- ▶ 7단계 (순차) T9 시작 — 문서 갱신, 실제 앱 직접 호출, 완료 체크리스트
- ✔ T9 완료 — README API 표, `CLAUDE.md` 고유 구성, `domain-user-job` plan·task·implement 변경 섹션. 실제 앱(임시 DB)으로 정상·에러 케이스 확인(아래 메모). pytest 206 passed (#15)
- T9 완료 체크리스트(레이어 규칙)에서 발견: 라우터가 `models/k8s_names.UserId`를 직접 import → `X-User-Id` 헤더 타입을 `src/schemas/common.py`(`UserIdHeader`)로 옮김. 동작 변화 없음, pytest 206 passed
- ■ 7단계 완료 — 모든 작업 완료

## spec과 달라진 점
- T7 작업 확인 중 `/docs`에 실제로 쓰지 않는 422가 표시되는 것을 발견해, spec에 "OpenAPI에는 201·400·500만 문서화"를 추가하고 T8로 구현했다. task·plan에 변경 섹션 추가, 기존 T8은 T9로 옮김.

## 완료 체크리스트
- [x] `uv run ruff check .` / `uv run ruff format .` 통과
- [x] 레이어 규칙 준수 (Router → Service → Repository, 비즈니스 에러는 `MyApiError`. 라우터는 schema만 반환, 매니페스트 생성은 service, 슬롯 처리는 repository)
- [x] spec의 정상 케이스와 에러 케이스를 직접 호출해 확인 — `/docs`와 같은 요청을 실제 앱에 curl로 보냄(아래 메모)
- [x] `uv run pytest` 통과 (206 passed. service 테스트에 한도·중복·형식 규칙, router 테스트에 spec 에러 표의 모든 행)
- [x] README 등 관련 문서 갱신 (README API 표, `CLAUDE.md` 고유 구성·요구사항, `domain-user-job` 문서)
- [x] task.md 체크리스트 모두 완료

## 메모
- `gh issue close`가 `Could not close the issue`를 내면서도 실제로는 닫혔다(#13). 지난 기능과 같은 현상이라 `gh issue view`로 상태만 확인했다.
- **T4 로컬 MongoDB 확인**(9.0.2 standalone, 임시 DB `k8s_client_t4_check`, 확인 후 삭제): 인덱스 3개 생성(`uniq_owner_slot` partial `{is_deleted: false, quota_slot: {$exists: true}}` — 리뷰 4에서 `$exists` 제거), 10개 저장 시 슬롯 0~9, 11번째 한도 초과, 한도가 찬 상태의 중복 이름은 한도 초과가 먼저, soft delete 후 비운 슬롯(3) 재사용, 빈 슬롯이 있을 때 중복 이름은 이름 중복, **동시 15개 → 정확히 10개 성공·나머지 한도 초과**, 같은 이름 동시 5개 → 1개 성공, `quota_slot` 없는 옛 문서 여러 개 저장 가능(리뷰 4에서 이 방어를 없앰. 아래 참고). 확인 스크립트는 저장소에 두지 않고 확인 후 scratchpad에서도 지웠다. repository를 고치면 같은 항목을 다시 확인한다.

- **T9 실제 앱 확인**(uvicorn + 로컬 MongoDB 9.0.2 임시 DB `k8s_client_t9_check` + kubeconfig, 확인 후 DB 삭제·서버 종료): `/docs` 200, 정상 생성 201(응답 필드·기본값·리소스 요약), 이름 중복 `job_name_duplicated`, 헤더 없음 `invalid_user_id`, JSON 아님·정의 안 된 필드(`hostNetwork`) `invalid_parameter`, `invalid_job_name`·`invalid_job_type`·`invalid_image`(latest)·`invalid_port`·`invalid_replicas`·`invalid_env`·`invalid_size`, 10개 후 11번째 `job_quota_exceeded`, **새 유저 동시 요청 15개 → 201 10개·400 5개**. 저장 문서에 `template`(JSON)·`quota_slot`·Deployment·Service 리소스, 인덱스 4개 확인.
- 다음 기능: `api-job-list`(cursor 페이지네이션 — `limit` 기본값·상한, cursor 인코딩, 인덱스 조정), `api-job-get`·`api-job-delete`, `component-job-operator`(네임스페이스 생성, 이름 재사용 시 `user-job-id` 라벨로 apply 미루기, probe 기반 running 판단).

## 변경: 2026-10-29 코드 리뷰 반영
`/code-review` 지적 8건 중 5건 반영, 1건 규칙 보완, 2건 보류.
- 리뷰 1: body JSON 파싱이 실패하면 FastAPI가 헤더 검증을 건너뛰어, `X-User-Id`가 없어도 `invalid_parameter`가 나갔다(재현됨). 검증 에러 핸들러가 `json_invalid`일 때 `X-User-Id`를 직접 확인해 `invalid_user_id`를 먼저 응답. router 테스트 2개 추가.
- 리뷰 2: 동시 요청으로 슬롯·이름 인덱스가 함께 걸리면 MongoDB는 이름 인덱스(`uniq_owner_name`)만 알려 줘 spec 순서(한도 먼저)와 반대로 `job_name_duplicated`가 나갔다. 이름 중복일 때만 슬롯을 다시 읽어 다 찼으면 한도 초과로 응답.
- 리뷰 4: `uniq_owner_slot` partial과 `_used_slots`의 `quota_slot $exists` 조건 제거. 옛 문서 방어였지만 모델이 `template`·`quota_slot`을 필수로 요구해 어차피 읽을 수 없고, 한도 계산에서도 빠져 문제를 가렸다. spec대로 옛 문서는 마이그레이션 없이 지운다.
  - 리뷰 2·4 로컬 MongoDB 확인(임시 DB `k8s_client_review_check`, 확인 후 삭제, 스크립트도 삭제): partial `{is_deleted: false}`, 9개 + 경합 재현(슬롯을 읽은 직후 다른 요청이 슬롯 9에 같은 이름 저장) → MongoDB는 `{owner_id: 1, name: 1}`을 알려 주지만 결과는 `JobQuotaExceededError`, 빈 슬롯이 있을 때 이름 중복은 `DuplicateJobNameError`, 동시 15개 → 10개 성공. 수정 전 코드로 같은 경합을 돌려 `DuplicateJobNameError`가 나는 것도 확인.
- 리뷰 6: 검증 에러 loc 정규화가 template 아래 세 번째 요소를 무조건 지웠다. 필드 이름(`type`·`image`·`port`…)이 아닐 때만 타입 태그로 보고 지움. 테스트 4개 추가.
- 리뷰 7: `nginx:latest@sha256:...`처럼 digest가 있으면 이미지가 고정되므로 `latest` 태그도 허용. spec 두 곳·에러 메시지·모델 설명 수정, 테스트 1개 추가.
- 리뷰 8(규칙 보완): `services/job_templates.py`가 주입 없이 함수로 import된다는 지적. 외부 의존이 없는 순수 함수라 가짜로 바꿀 이유가 없어 코드는 유지하고, `CLAUDE.md` "의존성 주입"에 순수 함수 모듈 예외를 명시.
- 보류(메모):
  - 리뷰 3: 한 유저가 한도 근처에서 생성·삭제를 동시에 반복하면 10번 연속 슬롯 경합으로 실제로는 빈 슬롯이 있는데도 한도 초과가 날 수 있다. 재시도 상한을 늘리거나 없애면 무한 경합 위험이 있어 그대로 둔다. 실제로 보고되면 상한을 `max_slots * 2`로 늘리는 것부터 검토한다.
  - 리뷰 5: selector가 `app.kubernetes.io/name`뿐이라, 지운 job과 같은 이름의 새 job이 서로의 Pod를 고를 수 있다. domain spec "operator에 넘기는 규칙"(다른 `user-job-id` 라벨의 같은 이름 리소스가 있으면 apply를 미룸)으로 두 job의 리소스가 동시에 존재하지 않게 막는다. selector에 `user-job-id`를 넣는 안은 저장 전에 ID를 만들고 "라벨은 operator가 붙인다" 규칙을 바꿔야 하므로 `component-job-operator`에서 다시 본다.
- 확인: ruff 통과, pytest 213 passed.

## 변경: 2026-10-29 도메인 enum 모으기
- `src/models/enums.py`(신규): `JobStatus`·`JobSize`를 `models/user_job.py`에서 옮기고, 문자열 `"web"`으로 흩어져 있던 job 타입을 `JobType` enum으로 만듦(`WebTemplate.type: Literal[JobType.WEB]`, `KINDS_BY_TYPE`·`_BUILDERS` 키).
- `ErrorEnum`은 `MyApiError`와 짝이고 공통 템플릿이 `my_exception.py`에 두도록 정하고 있어 그대로 둠.
- 동작 변화 없음: 요청·응답·OpenAPI(`type`은 `const: "web"` 그대로), MongoDB 저장 값 동일. import 경로만 바뀜.
- `CLAUDE.md` 고유 구성에 `models/enums.py` 추가, job 타입 추가 시 `JobType`도 늘리도록 보완.
- 확인: ruff 통과, pytest 213 passed.

## 변경: 2026-10-29 OpenAPI example
`/redoc`에 example이 하나도 없어 ReDoc이 `"string"` 같은 샘플을 보여 주고, 400은 어떤 code가 나는지 보이지 않았다.
- `src/schemas/job.py`: 요청 example `JOB_CREATE_EXAMPLES`(`minimal`·`full`), 201 응답 example `JOB_RESPONSE_EXAMPLE`.
- `src/schemas/common.py`: `X-User-Id` 헤더 example(`alice`).
- `src/schemas/error.py`: `error_responses(*ErrorEnum)` — 상태 코드별로 code마다 example 하나, 500(`db_error`·`unknown_error`)은 항상 포함. 500 본문 상수 `DB_ERROR`·`UNKNOWN_ERROR`를 `main.py` 핸들러도 쓴다(문구 중복 제거, 응답 동일).
- `src/routers/job_router.py`: 위 example 연결, 400 example은 spec 에러 표의 11개 code.
- 테스트: 요청 example 2개가 실제로 201, 201 example이 `minimal` 요청 결과와 같은 모양, 400·500 example 목록, 500 example = 핸들러 응답. pytest 218 passed.
- 규칙: `docs/fastapi-sdd-template.md`에 "API 문서 (OpenAPI)" 섹션, `sdd-process.md` 완료 체크리스트에 `/redoc` example 확인, `CLAUDE.md` 고유 구성에 `schemas/error.py`.
- `/redoc` 화면은 브라우저로 직접 확인하지 않았다(OpenAPI JSON의 media type `examples`·`example`만 확인).

## 변경: 2026-10-29 검증 에러 매핑 단순화
옛 방식은 pydantic 에러의 `loc`을 보고 필드를 거꾸로 찾아 code를 정했다. 그래서 타입 태그 제거(`_normalize_loc`·`_TEMPLATE_FIELDS`), env 하위 키를 위한 접두사 탐색, 필드 정의와 떨어진 위치→에러 표가 필요했다.
- `src/core/exception/validation_error.py`: `error_code(ErrorEnum)` 추가. 필드 타입을 `WrapValidator`로 감싸, 그 필드 검증이 어떤 이유로 실패하든 에러 종류를 ErrorEnum code로 바꾼다. `_classify`는 에러 종류만 본다(code → 그 에러, `union_tag_*` → `invalid_job_type`, 그 외 → `invalid_parameter`).
  - 예외 하나: 값이 아예 없으면 필드 검증기가 돌지 않는다. 그래서 누락도 필드 에러로 알려야 하는 필수 필드(`X-User-Id`, `image`, `port`)만 `_MISSING_ERRORS`에서 이름으로 구분한다. 리팩터링 중 이 케이스가 `invalid_parameter`로 바뀌는 것을 발견해 보완했고, router 테스트에 image·port 누락 케이스를 추가했다.
  - 제거: `_normalize_loc`, `_TEMPLATE_LOC`, `_TEMPLATE_FIELDS`, `_FIELD_ERRORS`, `_MISSING_IS_FORMAT_ERROR`, `_FORMAT_ERROR_TYPES`, 접두사 탐색.
- `error_code` 연결: `X-User-Id`(`schemas/common.py`), `name`(`schemas/job.py`), `image`·`port`·`replicas`·`env`·`size`(`models/user_job.py`). OpenAPI 스키마(제약·설명)는 그대로다.
- 응답 동작 변화 없음. spec 에러 표·우선순위 그대로.
- `tests/test_validation_error.py`: 자체 `_Body` 대신 실제 `JobCreateRequest`로 검증. loc 형태 테스트(리뷰 6) 제거, `error_code` 단위 테스트 추가.
- `CLAUDE.md`: "새 필드는 위치→에러 표에 추가" → "필드 타입에 `error_code` 붙이기".
- 확인: ruff 통과, pytest 219 passed.

## 변경: 2026-10-30 에러 응답 문서를 라우터 공통 선언으로
엔드포인트마다 에러 code를 모두 example로 나열하면 같은 목록을 spec·라우터·테스트 세 곳에서 손으로 맞춰야 하고, 엔드포인트가 늘수록 커진다. 흔한 방식대로 줄였다.
- `src/schemas/error.py`: `error_responses()`·`_examples()`·`SERVER_ERRORS` 제거. `COMMON_ERROR_RESPONSES`(400: `ErrorResponse` + `invalid_parameter` example, 500: `db_error` example) 추가.
- `src/routers/job_router.py`: `APIRouter(responses=COMMON_ERROR_RESPONSES)`, 엔드포인트에는 201 example과 `description`(에러 code는 spec 경로)만. 요청·헤더·201 example은 그대로.
- 테스트: code별 에러 example 목록 테스트 → 400·500 모양·대표 example·spec 경로 확인으로. 500 본문 = 핸들러 응답 테스트는 유지.
- 규칙: `docs/fastapi-sdd-template.md` "API 문서 (OpenAPI)"의 에러 응답 항목, `sdd-process.md` 완료 체크리스트, `CLAUDE.md` 고유 구성.

## 변경: 2026-10-30 검증 함수 이름
- `src/services/user_job_service.py`: `_require_user_id` → `_validate_user_id`. `create_job` 안에 있던 이름 검사를 `_validate_job_name`으로 분리. 동작 변화 없음.
- `docs/fastapi-sdd-template.md` Python 규칙: 예외를 던지는 검증 함수는 `validate_<대상>`, bool을 돌려주는 함수는 `is_<대상>`.
- 확인: ruff 통과, pytest 219 passed.
