# 구현 계획: job 생성 API

- **브랜치**: `002-api-job-create` | **작성일**: 2026-10-28 | **spec**: [spec.md](spec.md)

## 요약 (Summary)
`POST /jobs`를 추가하고, 도메인의 job 입력을 템플릿(`web`)으로 한다. 개수 한도는 `quota_slot` + 유니크 partial 인덱스로, 필드별 검증 에러는 필드 타입에 붙인 `error_code()`로, 매니페스트 생성은 순수 함수 모듈로 한다(결정 근거는 [research.md](research.md)).

## 기술 맥락 (Technical Context)
- **언어/버전**: Python (uv)
- **주요 의존성**: FastAPI 0.162, Pydantic 2.14, `pymongo` 4.19
- **저장소**: MongoDB `user_jobs` (필드 `template`·`quota_slot`, 인덱스 `uniq_owner_slot`)
- **테스트**: `uv run pytest`, repository는 로컬 MongoDB 9.0.2 standalone 임시 DB로 직접 확인
- **실행 환경**: 로컬 MongoDB + kubeconfig(minikube)
- **유형**: HTTP API
- **성능·제약**: 유저당 job 10개. 로컬 MongoDB가 standalone이라 트랜잭션은 쓰지 않는다

## Constitution Check
| 원칙·요구사항 | 이 기능에서 지키는 방법 | 결과 |
|---|---|---|
| II. 레이어 | router는 schema 파싱 → service 하나 호출 → `JobResponse.from_job()`. 매니페스트 생성은 service 쪽, 슬롯 처리는 repository | 통과 |
| III. 테스트 | 템플릿 생성·한도·중복·형식 규칙은 service·템플릿 테스트, 에러 표 행마다 router 테스트 | 통과 |
| IV. 에러 표현 | 필드별 `ErrorEnum` 400, 500은 전역 핸들러. 에러 표는 [contracts/post-jobs.md](contracts/post-jobs.md) | 통과 |
| V. 단순함 | 개수 한도에 카운터 문서·트랜잭션 대신 슬롯 인덱스(research) | 통과 |
| `CLAUDE.md`: job 입력은 템플릿 방식 | `extra="forbid"`, 고정 값은 `job_templates.py` | 통과 |
| `CLAUDE.md`: 유저별 job 개수 제한 | `quota_slot` 유니크 partial 인덱스 | 통과 |
| `CLAUDE.md`: operator 패턴 | API는 MongoDB에만 쓰고 바로 응답 | 통과 |

## 프로젝트 구조 (Project Structure)

### 변경 파일 (Source Code)
- `src/schemas/`
  - `job_request.py`: `JobCreateRequest`(`extra="forbid"`, `name: DnsLabel1035` + `error_code(INVALID_JOB_NAME)`, `template: JobTemplate`), `JOB_CREATE_EXAMPLES`(`minimal`·`full`)
  - `job_response.py`: `JobResourceSummary`, `JobResponse`(`from_job()`), `JOB_RESPONSE_EXAMPLE`
  - `common_request.py`: `UserIdHeader`(`X-User-Id`, `error_code(INVALID_USER_ID)`, example `alice`)
  - `error_response.py`: `ErrorResponse`, `COMMON_ERROR_RESPONSES`(400·500 문서), 500 본문 상수 `DB_ERROR`·`UNKNOWN_ERROR`
- `src/models/`
  - `k8s_names.py` (신규): 형식 정규식과 `Annotated` 타입(`UserId`, `DnsLabel1035`, `ImageRef`, `EnvName`), `is_user_id()`·`is_dns_1035_label()` 등
  - `enums.py`: `JobType`, `JobSize`
  - `user_job_models.py`: `WebTemplate`(`extra="forbid"`, 필드마다 `error_code`·`Field(description=...)`), `JobTemplate`(discriminator `type`), `MAX_JOBS_PER_USER = 10`, `UserJob.template`·`quota_slot`
- `src/repository/user_job_repository.py`: `ensure_indexes()`에 `uniq_owner_slot`, `insert_with_slot(job_doc, max_slots)`, `_used_slots(owner_id)`, `JobQuotaExceededError`
- `src/services/`
  - `job_templates.py` (신규): `SIZE_PRESETS`, `KINDS_BY_TYPE`, `build_resources(name, namespace, template)`, `_build_web()`
  - `user_job_service.py`: `create_job(owner_id, name, template)`. 템플릿을 쓰지 않는 매니페스트 직접 입력 경로는 두지 않는다
- `src/routers/job_router.py` (신규): `APIRouter(responses=COMMON_ERROR_RESPONSES)`, `POST /jobs`(`status_code=201`, `response_model=JobResponse`, `description`에 contracts 경로, 요청·201 example)
- `src/core/exception/`
  - `my_exception.py`: `INVALID_PARAMETER`, `INVALID_USER_ID`, `INVALID_JOB_NAME`, `INVALID_JOB_TYPE`, `INVALID_IMAGE`, `INVALID_PORT`, `INVALID_REPLICAS`, `INVALID_ENV`, `INVALID_SIZE`, `JOB_QUOTA_EXCEEDED`(모두 400). 메시지는 contracts의 "message 예"
  - `validation_error.py` (신규): `error_code(ErrorEnum)`(`WrapValidator`), `_MISSING_ERRORS`(누락도 필드 에러인 필수 필드), `_PRIORITY`, `to_error_enum()`
- `src/main.py`: `job_router` 등록, `RequestValidationError` → 400 핸들러(`json_invalid`이면 `X-User-Id`를 먼저 확인), `_openapi_without_422()`
- `tests/`: `test_user_job_models.py`, `test_validation_error.py`, `test_job_templates.py`, `test_user_job_service.py`(가짜 repository 슬롯 규칙), `test_job_router.py`(에러 표 행마다, 우선순위, example), `test_main.py`(422 없음, 500 본문)
- 문서: `README.md` API 표, `CLAUDE.md` 고유 모듈(`validation_error.py`, `job_templates.py`, `enums.py`, `error_response.py`)·의존성 주입 예외

### DB 변경
- `user_jobs` 필드: `template`(object), `quota_slot`(int)
- 인덱스: `uniq_owner_slot` `{owner_id: 1, quota_slot: 1}`, `unique: true`, `partialFilterExpression: {is_deleted: false}`
- 데이터 마이그레이션: 없음(운영 데이터 없음)

### 외부 의존성
- 새 패키지 없음

## 리스크 / 확인 필요
- **repository는 자동 테스트가 없다**. 슬롯 인덱스 충돌의 `keyPattern` 구분, 동시 insert 재시도, soft delete 후 슬롯 재사용은 로컬 MongoDB 임시 DB로 확인한다(`implement.md`). repository를 고치면 다시 확인한다.
- **한도 근처 경합**: 한 유저가 생성·삭제를 동시에 반복하면 10번 연속 슬롯 경합으로 빈 슬롯이 있는데도 한도 초과가 날 수 있다. 실제로 보고되면 재시도 상한을 `max_slots * 2`로 늘리는 것부터 검토한다.
- **pydantic·FastAPI 에러 형태 의존**: 매핑은 에러 종류(`error_code`가 넣은 code, `union_tag_*`, `missing`)에 기댄다. 버전이 오르면 router 테스트의 에러 표 행별 확인으로 드러난다.
