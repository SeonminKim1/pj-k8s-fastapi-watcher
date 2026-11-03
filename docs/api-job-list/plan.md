# PLAN: job 목록 조회 API

## 결정 사항
- **cursor 인코딩**: `base64url(f"{created_at.isoformat()}|{id}")`, padding 없음. isoformat은 마이크로초·타임존까지 그대로 왕복되므로 위치가 정확히 복원된다.
  - 풀 때는 base64url 디코딩 → `|`로 둘로 나눔 → `datetime.fromisoformat`(타임존 있는 값만) → `id`가 24자리 hex(ObjectId)인지 확인. 하나라도 실패하면 `INVALID_CURSOR`. 256자를 넘는 cursor는 디코딩 전에 거절한다.
  - 서명하지 않는다. cursor는 위치만 담고 소유자 조건은 항상 `X-User-Id`로 붙으므로, 조작해도 자기 job의 다른 위치를 볼 뿐이다(spec "정렬과 cursor").
  - 순수 함수라 `src/services/job_cursor.py`에 두고 service가 직접 import한다(`CLAUDE.md` "의존성 주입"의 순수 함수 모듈 예외, `job_templates.py`와 같음).
- **`status` 중복 지정 검출**: FastAPI는 같은 쿼리가 여러 번 오면 조용히 마지막 값을 쓴다(FastAPI 0.162.0에서 개별 파라미터·쿼리 모델 모두 확인함). 그래서 `schemas/job_request.py`에 쿼리 파싱용 dependency `job_list_query()`를 두고, `request.query_params.getlist("status")`가 2개 이상이면 `RequestValidationError`(type `invalid_job_status`)를 던진다. 전역 핸들러가 다른 검증 에러와 같은 우선순위 규칙으로 처리한다.
  - 대안 `status: list[JobStatus]` + `max_length=1`은 코드가 짧지만 `/docs`에 배열(다중 선택)로 보여 "하나만"이라는 규칙과 어긋나서 쓰지 않는다.
- **인덱스는 바꾸지 않는다**: 기존 `owner_created_at` `{owner_id: 1, created_at: -1}`을 그대로 쓴다. 조건에 맞는 문서는 유저당 삭제되지 않은 job(최대 10개)뿐이라, 같은 시각일 때의 `_id` 순서는 메모리 정렬로 충분하다. 한도가 커지면 `{owner_id: 1, created_at: -1, _id: -1}`로 바꾸면 된다(API 형태와 무관, 이름이 다른 새 인덱스를 만들고 옛 인덱스를 지운다).
- **service 반환 타입**: 튜플 대신 `JobPage(items: list[UserJob], next_cursor: str | None)` 모델을 쓴다. 필드 이름으로 의미가 드러나고 응답 schema로 옮기기 쉽다. `docs/domain-user-job/spec.md`의 `list_jobs` 반환 타입도 `JobPage`로 맞춘다.
- **`limit` 상수**: 기본값 `20`, 상한 `100`을 `models/user_job.py`에 `MAX_JOBS_PER_USER`와 나란히 둔다. schema(`Query` 기본값·범위)와 service(범위 검사)가 같은 상수를 쓴다.

## 변경 파일
- `src/schemas/`
  - `job_request.py`: `JobListQuery`(`limit`, `cursor`, `status`) 모델과 dependency `job_list_query()`. 필드에 `error_code(INVALID_LIMIT)`·`error_code(INVALID_JOB_STATUS)`, `Query(openapi_examples=...)`(예: `limit` 20, `status` running)
  - `job_response.py`: `JobSummary`(`id`, `name`, `status`, `created_at`, `from_job()`), `JobListResponse`(`items`, `next_cursor`, `from_page()`), `JOB_LIST_RESPONSE_EXAMPLE`
- `src/models/user_job.py`: `JobPosition`(`created_at`, `id`. cursor가 가리키는 정렬 위치), `JobPage`, `JOB_LIST_DEFAULT_LIMIT = 20`, `JOB_LIST_MAX_LIMIT = 100`
- `src/repository/user_job_repository.py`
  - `find_active_by_owner(owner_id)` → `find_active_page(owner_id, status, after: JobPosition | None, limit) -> list[UserJob]`(기존 메서드는 `list_jobs`만 쓰므로 바꾼다)
  - 쿼리: `{owner_id, is_deleted: false, status?(있으면), $or: [{created_at: {$lt: t}}, {created_at: t, _id: {$lt: oid}}](after가 있으면)}`, 정렬 `[(created_at, -1), (_id, -1)]`, `limit`
- `src/services/`
  - `job_cursor.py` (신규): `encode_cursor(job: UserJob) -> str`, `decode_cursor(cursor: str) -> JobPosition`(실패 시 `MyApiError(INVALID_CURSOR)`)
  - `user_job_service.py`: `list_jobs(owner_id, limit=20, cursor=None, status=None) -> JobPage`. `_validate_limit()` 추가. `limit + 1`개를 읽어 `next_cursor` 판단
- `src/routers/job_router.py`: `GET /jobs`. `Depends(job_list_query)`로 쿼리를 받아 `service.list_jobs()` 호출 → `JobListResponse.from_page()`. `description`에 spec 경로, 200 example
- `src/core/exception/`
  - `my_exception.py`: `INVALID_LIMIT`, `INVALID_JOB_STATUS`, `INVALID_CURSOR`(모두 400)
  - `validation_error.py`: `_PRIORITY` 끝에 `INVALID_LIMIT`, `INVALID_JOB_STATUS`
- `src/main.py`: 변경 없음
- `tests/`
  - `test_job_cursor.py` (신규): 인코딩 왕복(마이크로초·타임존 유지), 잘못된 cursor(빈 값, base64 아님, `|` 없음, 날짜 형식·타임존 없음, id 형식, 256자 초과) → `INVALID_CURSOR`
  - `test_user_job_service.py`: 가짜 repository의 `find_active_by_owner`를 `find_active_page`로 교체(정렬·위치·필터를 실제와 같게). 첫 페이지·다음 페이지 이어짐·마지막 페이지 `next_cursor=None`·정확히 `limit`개일 때 `None`·같은 `created_at` 순서·`status` 필터·cursor 위치 job 삭제 후 이어짐·남의 job 제외·빈 목록·`limit` 범위 밖 `INVALID_LIMIT`·잘못된 cursor `INVALID_CURSOR`
  - `test_job_router.py`: 가짜 service에 `list_jobs` 추가. 200 응답 형태, 기본값 전달(`limit` 20), 쿼리 값 전달, 요청 검증 에러(spec 표의 각 줄 + `status` 두 번, 정의되지 않은 쿼리 무시), `INVALID_CURSOR` 400, 응답 example이 `JobListResponse`로 검증되는지
  - `test_validation_error.py`: 새 code의 우선순위(`invalid_user_id` > `invalid_limit` > `invalid_job_status`)
- 문서: `README.md` API 표에 `GET /jobs`, `docs/domain-user-job/spec.md`의 `list_jobs` 반환 타입 `JobPage`

## DB 변경
- 없음(컬렉션·필드·인덱스 그대로. 위 "인덱스는 바꾸지 않는다")

## 외부 의존성
- 없음(표준 라이브러리 `base64`, `datetime`만 추가로 사용)

## 리스크 / 확인할 것
- **repository는 자동 테스트가 없다**(테스트 규칙). `$or` 위치 조건과 `(created_at, _id)` 정렬이 실제 MongoDB에서 맞게 동작하는지, 같은 `created_at`을 가진 문서가 페이지 사이에서 빠지거나 겹치지 않는지 로컬 MongoDB 임시 DB로 확인하고 `implement.md`에 남긴다. 확인용 스크립트는 scratchpad에 두고 확인 후 지운다.
- **MongoDB 시각 정밀도**: MongoDB는 밀리초까지만 저장한다. cursor는 항상 DB에서 읽은 값으로 만들므로 왕복이 정확하다. 단, 가짜 repository는 마이크로초 값을 가지므로 service 테스트도 그대로 통과한다(정밀도와 무관하게 같은 값을 비교).
- **기존 기능 영향**: `UserJobService.list_jobs`·`find_active_by_owner`의 시그니처가 바뀐다. 아직 라우터·operator에서 쓰는 곳이 없어 service 테스트만 고치면 된다.
