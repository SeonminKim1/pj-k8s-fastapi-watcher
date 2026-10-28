# PLAN: job 생성 API

## 결정 사항
- **개수 한도는 슬롯 + 유니크 partial 인덱스로 지킨다.** job 문서에 `quota_slot`(0~9)을 두고 `(owner_id, quota_slot)` 유니크(`is_deleted: false`만). 쓰기가 문서 하나라 카운터 문서처럼 어긋날 일이 없고, soft delete하면 슬롯이 저절로 빈다. 트랜잭션은 로컬 MongoDB가 standalone(9.0.2)이라 쓰지 않는다.
  - 저장 절차(repository): 사용 중 슬롯 조회 → 가장 작은 빈 슬롯으로 insert → 슬롯 인덱스 충돌이면 다시 조회해 재시도. 시도는 최대 10회. 충돌은 다른 요청이 슬롯을 하나 차지했다는 뜻이므로, 10번 충돌하면 슬롯이 다 찬 것으로 보고 한도 초과로 처리한다.
  - 한도 값 `MAX_JOBS_PER_USER = 10`은 service가 정해 repository에 넘긴다(비즈니스 규칙은 service, 슬롯 처리는 DB 접근이라 repository).
- **형식 규칙은 공용 `Annotated` 타입 하나로 정의한다**(domain-user-job 메모의 결정). `src/models/k8s_names.py`의 정규식·타입을 schema·model·service가 함께 쓴다. service는 schema를 거치지 않는 호출자(operator 등)를 위해 `owner_id`·`name` 형식 검사를 유지하되 같은 정규식을 쓴다.
- **요청 검증 에러 → `ErrorEnum` 매핑은 별도 모듈에 둔다.** pydantic 에러의 `loc`·`type`을 spec의 우선순위 표에 맞춰 `ErrorEnum`으로 바꾸고, 가장 높은 우선순위 하나를 고른다. `main.py`는 핸들러만 등록한다.
  - `loc` 예: `("body", "template")` + `union_tag_invalid`/`union_tag_not_found`(type 오류), `("body", "template", "web", "port")`, `extra_forbidden`(정의되지 않은 필드)는 pydantic 2.14로 확인함. `("header", "x-user-id")`, `("body", "name")`, `json_invalid`는 FastAPI 기준 예상이며 구현 때 테스트로 확인한다.
- **매니페스트 생성은 service 쪽 순수 함수로 둔다.** `src/services/job_templates.py`에 타입별 생성 함수와 "타입 → 만드는 kind" 표를 둔다. 타입을 추가하면 이 파일에 함수 하나와 표 한 줄을 더한다. 클러스터·DB에 접근하지 않으므로 단독으로 테스트한다.
- **응답 변환은 schema가 한다.** `JobResponse.from_job(job)`으로 `UserJob` → 응답 schema. 라우터는 service 호출 결과를 이것으로 감싸 반환만 한다(라우터가 `models/` 객체를 직접 반환하지 않음).

## 변경 파일
- `src/models/k8s_names.py` (신규): 형식 정규식과 `Annotated` 타입
  - `UserId`, `DnsLabel1035`(job 이름), `ImageRef`(태그·digest 필수, `latest` 불가), `EnvName`
  - 정규식 기반 `is_user_id()`, `is_dns_1035_label()` 함수(service용)
- `src/models/user_job.py` (수정)
  - `JobSize(StrEnum)`: `small` / `medium`
  - `WebTemplate`(`extra="forbid"`, 필드: `type: Literal["web"]`, `image`, `port`, `replicas=1`, `env={}`, `size=small`, `Field(description=...)`)
  - `JobTemplate = Annotated[WebTemplate, Field(discriminator="type")]`(지금은 멤버 하나인 union)
  - `UserJob`에 `template: JobTemplate`, `quota_slot: int` 추가. `name` 설명을 DNS-1035로
  - `MAX_JOBS_PER_USER = 10`
  - `ALLOWED_RESOURCE_KINDS` 제거(→ `job_templates.py`의 타입별 표)
- `src/services/job_templates.py` (신규)
  - `SIZE_PRESETS`: size → `{cpu, memory}`
  - `KINDS_BY_TYPE`: `{"web": {("apps/v1", "Deployment"), ("v1", "Service")}}`
  - `build_resources(name, namespace, template) -> list[JobResource]`: `type`별 생성 함수로 분기
  - `_build_web(...)`: spec의 "템플릿 → 매니페스트"대로 Deployment·Service(readinessProbe, securityContext 등)
- `src/repository/user_job_repository.py` (수정)
  - `ensure_indexes()`: `uniq_owner_slot` 인덱스 추가
  - `insert(job_doc)` → `insert_with_slot(job_doc, max_slots) -> UserJob`: 위 저장 절차. 빈 슬롯이 없으면 `JobQuotaExceededError`, 이름 인덱스 위반이면 `DuplicateJobNameError`, 그 외 유니크 위반은 그대로 올림(500)
  - `_used_slots(owner_id) -> set[int]`
- `src/services/user_job_service.py` (수정)
  - `create_job(owner_id, name, template)`: 형식 검사(`INVALID_USER_ID`·`INVALID_JOB_NAME`) → `build_resources` → `insert_with_slot(..., MAX_JOBS_PER_USER)` → 예외를 `JOB_QUOTA_EXCEEDED`·`JOB_NAME_DUPLICATED`로
  - `_require_user_id`의 에러를 `INVALID_USER_ID`로
  - 제거: `_build_resources`, `_is_dns_label`, `_is_dns_subdomain`, `_is_dns_1035_label`, `_is_valid_resource_name`, 정규식 상수(→ `k8s_names.py`)
- `src/core/exception/my_exception.py` (수정)
  - 추가(모두 400): `INVALID_USER_ID`, `INVALID_JOB_NAME`, `INVALID_JOB_TYPE`, `INVALID_IMAGE`, `INVALID_PORT`, `INVALID_REPLICAS`, `INVALID_ENV`, `INVALID_SIZE`, `JOB_QUOTA_EXCEEDED`. 메시지는 spec의 "message 예"
  - `INVALID_PARAMETER` 메시지를 "요청 형식이 올바르지 않습니다."로
  - 제거: `INVALID_JOB_RESOURCE`
- `src/core/exception/validation_error.py` (신규): `to_error_enum(errors: Sequence[dict]) -> ErrorEnum`(우선순위 표 매핑)
- `src/schemas/job.py` (신규)
  - `JobCreateRequest`(`extra="forbid"`): `name: DnsLabel1035`, `template: JobTemplate`
  - `JobResourceSummary`: `kind`, `name`
  - `JobResponse`: spec의 Response 필드 + `from_job(job: UserJob) -> JobResponse`
- `src/routers/job_router.py` (신규): `POST /jobs`, `status_code=201`, `response_model=JobResponse`
  - `x_user_id: Annotated[UserId, Header(alias="X-User-Id")]`, `body: JobCreateRequest`, `service = Depends(get_user_job_service)`
- `src/main.py` (수정): `job_router` 등록, `RequestValidationError` 핸들러(→ `to_error_enum` → `{code, message}` 400)
- `tests/`
  - `tests/test_job_templates.py` (신규): 생성된 Deployment·Service의 고정 값(라벨·selector·resources·securityContext·probe·ClusterIP·port), size·env 반영
  - `tests/test_user_job_service.py` (수정): 가짜 repository에 슬롯 규칙 추가. create 테스트를 템플릿 입력으로 바꾸고 매니페스트 검증 테스트 제거. 한도(10개 성공·11번째 거절·삭제 후 다시 가능), 동시 슬롯 충돌 재시도, 이름 중복, `invalid_user_id` 케이스
  - `tests/test_job_router.py` (신규): `app.dependency_overrides`로 가짜 service. 201 응답 형태, spec 에러 표의 행마다 `code` 확인, 여러 개 틀렸을 때 우선순위
  - `tests/test_validation_error.py` (신규, 필요하면 router 테스트에 합침): `to_error_enum` 매핑 단위 테스트
- 문서
  - `README.md`: API 표에 `POST /jobs`
  - `CLAUDE.md` 프로젝트 고유 구성: 요청 검증 에러 매핑(`validation_error.py`), 템플릿(`job_templates.py`) 한 줄씩
  - `docs/domain-user-job/plan.md`·`task.md`·`implement.md`: `## 변경: 2026-10-28 템플릿 입력·개수 한도(api-job-create)` 섹션으로 이 기능에서 바꾼 내용을 가리킨다

## DB 변경
- `user_jobs` 필드 추가: `template`(object), `quota_slot`(int)
- 인덱스 추가: `uniq_owner_slot`: `{owner_id: 1, quota_slot: 1}`, `unique: true`, `partialFilterExpression: {is_deleted: false}`
- 기존 인덱스 `uniq_owner_name`, `owner_created_at`은 그대로
- 기존 데이터 마이그레이션: 없음(로컬 `k8s_client.user_jobs` 문서 0개 확인)

## 외부 의존성
- 새 패키지 없음

## 리스크 / 확인할 것
- **repository는 자동 테스트가 없다**(실제 DB 금지 규칙). 슬롯 인덱스 충돌의 `keyPattern` 구분, 동시 insert 재시도, soft delete 후 슬롯 재사용은 로컬 MongoDB 임시 DB로 직접 확인하고 `implement.md`에 남긴다.
- **기존 동작 변경**: `create_job` 시그니처, `INVALID_PARAMETER` → `INVALID_USER_ID`(owner_id 형식), `INVALID_JOB_RESOURCE` 제거, job 이름 규칙 DNS-1123 → DNS-1035. 아직 API·operator가 없어 외부 영향은 없고, 기존 service 테스트를 함께 고친다.
- **pydantic 에러 `loc` 형태 의존**: 매핑이 `("body", "template", "web", ...)` 같은 형태에 기대므로 pydantic·FastAPI 버전이 오르면 깨질 수 있다. router 테스트가 에러 표 행마다 `code`를 확인해 깨지면 바로 드러나게 한다.
- **`X-User-Id` 헤더 이름**: FastAPI는 `loc`에 소문자 `x-user-id`로 넣는다(대소문자 무관 매칭).

## 변경: 2026-10-28 /docs 422 제거
- `src/main.py`: `app.openapi`를 감싸, FastAPI 기본 OpenAPI를 만든 뒤 모든 경로의 `422` 응답과 `HTTPValidationError`·`ValidationError` 스키마를 뺀다. 한 번 만든 결과는 FastAPI처럼 `app.openapi_schema`에 캐시한다. 이후 추가되는 엔드포인트에도 그대로 적용된다.
- `tests/test_main.py`: OpenAPI 전체에 `422`와 두 스키마가 없는지, `POST /jobs`의 400 응답이 `ErrorResponse`인지 확인.
- 대안: 엔드포인트마다 `responses={422: ...}`를 지정하는 방법은 FastAPI가 422를 계속 추가하므로 뺄 수 없어 쓰지 않는다.
