# 리서치: job 목록 조회 API

## cursor 인코딩
- **결정**: `base64url(f"{created_at.isoformat()}|{id}")`, padding 없음. 풀 때는 256자 초과 거절 → base64url 문자만 허용(정규식) → 디코딩 → `|`로 둘로 나눔 → `datetime.fromisoformat`(타임존 있는 값만) → UTC로 맞춤(범위를 벗어나면 `OverflowError` → 거절) → `id`가 24자리 hex(ObjectId)인지 확인. 하나라도 실패하면 `INVALID_CURSOR`. `encode_cursor(position: JobPosition)`·`decode_cursor(cursor) -> JobPosition`(`src/services/job_cursor.py`).
- **근거**: isoformat은 마이크로초·타임존까지 그대로 왕복된다. cursor는 항상 DB에서 읽은 값(밀리초)으로 만들므로 정확하다. base64url 문자 검사가 없으면 표준 base64 문자(`+`, `/`)도 통과하고, UTC로 바꾸면 1년 이전이 되는 시각은 MongoDB 쿼리에서 500이 된다. 인코딩·디코딩이 같은 `JobPosition`을 주고받아 왕복 테스트가 단순하다.
- **서명하지 않는다**: cursor는 위치만 담고 소유자 조건은 항상 `X-User-Id`로 붙으므로, 조작해도 자기 job의 다른 위치를 볼 뿐이다.
- **위치**: 순수 함수라 service가 직접 import한다(스택 파일 "의존성 주입" 예외, `job_templates.py`와 같음).

## 같은 쿼리 중복 지정 검출
- **결정**: `src/schemas/job_request.py`에 dependency `job_list_request()`를 두고, `request.query_params.getlist(<이름>)`가 2개 이상이면 그 필드의 code로 `RequestValidationError`를 던진다(`_JOB_LIST_QUERY_ERRORS`: `limit`·`cursor`·`status`). 헤더도 이 dependency 파라미터로 받아 결과를 `JobListRequest`(`user_id`, `limit`, `cursor`, `status`)로 돌려준다.
- **근거**: FastAPI는 같은 쿼리가 여러 번 오면 조용히 마지막 값을 쓴다(0.162.0에서 개별 파라미터·쿼리 모델 모두 확인). FastAPI는 dependency를 엔드포인트 파라미터보다 먼저 실행하므로, 헤더를 엔드포인트에 두면 헤더가 없어도 중복 에러가 먼저 나가 우선순위(헤더 1순위)가 깨진다.
- **검토한 대안**: `status: list[JobStatus]` + `max_length=1` — `/docs`에 배열(다중 선택)로 보여 "하나만" 규칙과 어긋난다.

## `limit` 범위 제약 위치
- **결정**: `Annotated[int, Field(ge, le), error_code(INVALID_LIMIT), Query(...)]`처럼 제약을 `error_code` 앞에 둔다.
- **근거**: `Query(ge=1, le=100)`에 둔 제약은 `error_code()`의 감싸기 밖에서 적용돼 pydantic 기본 에러(`greater_than_equal`)가 나간다(직접 확인).

## 인덱스
- **결정**: 새로 만들지 않는다. 기존 `owner_created_at`을 쓴다.
- **근거**: 조건에 맞는 문서는 유저당 삭제되지 않은 job(최대 10개)뿐이라 같은 시각의 `_id` 순서는 메모리 정렬로 충분하다. 실제 실행 계획은 `uniq_owner_name`(partial `is_deleted: false`)을 골라 삭제된 job은 훑지 않는다(로컬 MongoDB 확인).
- **나중에**: 한도가 커지면 partial `{owner_id: 1, created_at: -1, _id: -1}` 인덱스를 추가한다(API 형태와 무관).

## service 반환 타입과 상수
- **결정**: 튜플 대신 `JobPage(items, next_cursor)`. `limit` 기본값 `JOB_LIST_DEFAULT_LIMIT = 20`, 상한 `JOB_LIST_MAX_LIMIT = 100`을 `src/models/user_job_models.py`에 `MAX_JOBS_PER_USER`와 나란히 두고 schema·service가 함께 쓴다.
- **근거**: 필드 이름으로 의미가 드러나고 응답 schema로 옮기기 쉽다. 같은 상수라 service의 이중 검사(schema를 거치지 않는 호출자 대비)가 어긋나지 않는다. `ErrorEnum.INVALID_LIMIT` 메시지의 숫자는 상수 옆 주석으로 함께 고치게 한다.
