# 리서치: job 생성 API

## 개수 한도를 지키는 방법
- **결정**: job 문서에 `quota_slot`(0~9)을 두고 `(owner_id, quota_slot)` 유니크 partial 인덱스(`is_deleted: false`). 저장 절차(repository): 사용 중 슬롯 조회 → 가장 작은 빈 슬롯으로 insert → 슬롯 인덱스 충돌이면 다시 조회해 재시도(최대 10회). 10번 충돌하면 슬롯이 다 찬 것으로 보고 한도 초과. 한도 값 `MAX_JOBS_PER_USER`는 service가 정해 repository에 넘긴다.
- **근거**: 쓰기가 문서 하나라 카운터 문서처럼 어긋날 일이 없고, soft delete하면 슬롯이 저절로 빈다.
- **검토한 대안**: 카운터 문서 + 트랜잭션 — 로컬 MongoDB가 standalone(9.0.2)이라 트랜잭션을 쓸 수 없다. 개수 조회 후 insert — 동시 요청에서 넘는다.

## 한도와 이름 중복이 함께 걸릴 때
- **결정**: 이름 중복일 때 슬롯을 다시 읽어 다 찼으면 `JobQuotaExceededError`.
- **근거**: 동시 요청으로 두 인덱스가 함께 걸리면 MongoDB는 이름 인덱스만 알려 준다. 그대로 두면 spec 순서(한도 먼저)와 반대가 된다.

## 형식 규칙의 위치
- **결정**: `src/models/k8s_names.py`의 정규식·`Annotated` 타입 하나를 schema·model·service가 함께 쓴다. service는 schema를 거치지 않는 호출자(operator 등)를 위해 `owner_id`·`name` 형식 검사를 하되 같은 정규식을 쓴다.
- **근거**: 규칙이 여러 곳에 복사되면 어긋난다.

## 요청 검증 에러 → `ErrorEnum`
- **결정**: 필드 타입에 `error_code(ErrorEnum)`(`WrapValidator`)를 붙여, 그 필드 검증이 어떤 이유로 실패하든 에러 종류를 code로 바꾼다. `_classify`는 에러 종류만 본다(code → 그 에러, `union_tag_*` → `invalid_job_type`, 그 외 → `invalid_parameter`). 값이 아예 없으면 필드 검증기가 돌지 않으므로, 누락도 필드 에러로 알려야 하는 필수 필드(`X-User-Id`, `image`, `port`)만 `_MISSING_ERRORS`에 이름으로 둔다. 여러 개면 `_PRIORITY`의 첫 번째.
- **근거**: 필드 정의 옆에 code가 있어 새 필드도 한 곳만 고친다.
- **검토한 대안**: pydantic 에러의 `loc`으로 필드를 찾아 매핑 — 타입 태그 제거, env 하위 키 접두사 탐색, 필드와 떨어진 위치→에러 표가 필요하다.

## body JSON 파싱 실패 시 헤더 우선순위
- **결정**: 검증 에러 핸들러가 `json_invalid`일 때 `X-User-Id`를 `is_user_id`로 직접 확인해 `invalid_user_id`를 먼저 응답한다.
- **근거**: body JSON 파싱이 실패하면 FastAPI가 헤더 검증을 건너뛴다.

## 매니페스트 생성 위치
- **결정**: `src/services/job_templates.py`에 타입별 생성 함수와 "타입 → 만드는 kind" 표. 클래스·주입 없이 import하는 순수 함수 모듈.
- **근거**: 클러스터·DB에 접근하지 않아 가짜로 바꿀 이유가 없다(스택 파일 "의존성 주입" 예외). 타입을 추가하면 함수 하나와 표 한 줄을 더한다.

## 응답 변환
- **결정**: `JobResponse.from_job(job)`으로 `UserJob` → 응답 schema. 라우터는 감싸 반환만 한다.
- **근거**: 라우터가 `models/` 객체를 직접 반환하지 않는다(레이어 규칙).

## OpenAPI의 422
- **결정**: `app.openapi`를 감싸 모든 경로의 `422` 응답과 `HTTPValidationError`·`ValidationError` 스키마를 뺀다(`_openapi_without_422`, 결과는 `app.openapi_schema`에 캐시).
- **근거**: 검증 에러를 400으로 응답하므로 422는 실제로 나가지 않는다.
- **검토한 대안**: 엔드포인트마다 `responses={422: ...}` — FastAPI가 422를 계속 추가해 뺄 수 없다.

## 에러 응답 문서
- **결정**: 엔드포인트마다 에러 code를 나열하지 않고 `COMMON_ERROR_RESPONSES`(400·500 모양 + 대표 example)를 `APIRouter(responses=...)`로 한 번 붙인다. 엔드포인트별 code 목록은 contracts 에러 표이고 `description`에 경로만 적는다.
- **근거**: 같은 목록을 spec·라우터·테스트 세 곳에서 손으로 맞추지 않는다.

## `latest` 태그
- **결정**: digest 없는 `latest`만 거절하고, `nginx:latest@sha256:...`처럼 digest가 있으면 허용한다.
- **근거**: `imagePullPolicy: IfNotPresent`라 `latest`는 노드마다 다른 이미지가 돌 수 있지만, digest가 있으면 이미지가 고정된다.
