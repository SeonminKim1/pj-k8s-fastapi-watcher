# 구현 계획: job 목록 조회 API

- **브랜치**: `003-api-job-list` | **작성일**: 2026-10-29 | **spec**: [spec.md](spec.md)

## 요약 (Summary)
`GET /jobs`를 추가한다. 위치 기반 불투명 cursor(`(created_at, id)`의 base64url), 같은 쿼리 중복 지정을 막는 요청 파싱 dependency, `limit + 1`개 읽기로 다음 페이지 판단. 인덱스는 새로 만들지 않는다(결정 근거는 [research.md](research.md)).

## 기술 맥락 (Technical Context)
- **언어/버전**: Python (uv)
- **주요 의존성**: FastAPI 0.162.0, Pydantic, `pymongo` 4.19. 표준 라이브러리 `base64`, `datetime`
- **저장소**: MongoDB `user_jobs` (기존 컬렉션·인덱스 사용)
- **테스트**: `uv run pytest`, repository는 로컬 MongoDB 9.0.2 임시 DB로 직접 확인
- **실행 환경**: 로컬 MongoDB + kubeconfig(minikube)
- **유형**: HTTP API
- **성능·제약**: 유저당 job 10개(메모리 정렬로 충분)

## Constitution Check
| 원칙·요구사항 | 이 기능에서 지키는 방법 | 결과 |
|---|---|---|
| II. 레이어 | router는 `Depends(job_list_request)` → `service.list_jobs()` → `JobListResponse.from_page()`. 요청 파싱 dependency는 `schemas/`(스택 파일 schemas 행) | 통과 |
| III. 테스트 | 페이지·cursor·필터·소유권 service 테스트, cursor 단위 테스트, 에러 표 행마다 router 테스트 | 통과 |
| IV. 에러 표현 | `INVALID_LIMIT`·`INVALID_JOB_STATUS`·`INVALID_CURSOR` 400. 에러 표는 [contracts/get-jobs.md](contracts/get-jobs.md) | 통과 |
| V. 단순함 | 인덱스·서명 없이 시작(research) | 통과 |
| `CLAUDE.md`: operator 패턴 | MongoDB만 읽음 | 통과 |

## 프로젝트 구조 (Project Structure)

### 변경 파일 (Source Code)
- `src/schemas/`
  - `job_request.py`: `JobListRequest`(`user_id`, `limit`, `cursor`, `status`), dependency `job_list_request()`(헤더·쿼리 파싱, 모든 쿼리 중복 지정 검출 `_JOB_LIST_QUERY_ERRORS`), `JOB_LIST_CURSOR_EXAMPLE`, 필드에 `error_code`·`Query(openapi_examples=...)`
  - `job_response.py`: `JobSummary`(`from_job()`), `JobListResponse`(`from_page()`), `JOB_LIST_RESPONSE_EXAMPLE`
- `src/models/user_job_models.py`: `JobPosition`, `JobPage`, `JOB_LIST_DEFAULT_LIMIT`, `JOB_LIST_MAX_LIMIT`
- `src/repository/user_job_repository.py`: `find_active_page(owner_id, status, after, limit)`
- `src/services/`
  - `job_cursor.py` (신규): `encode_cursor(position)`, `decode_cursor(cursor)`
  - `user_job_service.py`: `list_jobs(owner_id, limit, cursor, status) -> JobPage`, `_validate_limit()`
- `src/routers/job_router.py`: `GET /jobs`, `description`에 contracts 경로, 200 example
- `src/core/exception/`
  - `my_exception.py`: `INVALID_LIMIT`, `INVALID_JOB_STATUS`, `INVALID_CURSOR`(모두 400)
  - `validation_error.py`: `_PRIORITY` 끝에 `INVALID_LIMIT`, `INVALID_JOB_STATUS`, `INVALID_CURSOR`
- `src/main.py`: 변경 없음
- `tests/`: `test_job_cursor.py`(신규), `test_user_job_service.py`(가짜 `find_active_page`), `test_job_router.py`(list), `test_validation_error.py`(우선순위)
- 문서: `README.md` API 표에 `GET /jobs`, `specs/001-domain-user-job/data-model.md`의 `list_jobs` 반환 타입 `JobPage`, 스택 파일 schemas 행(요청 파싱 dependency)

### DB 변경
- 없음(기존 컬렉션·필드·인덱스 사용, research "인덱스")

### 외부 의존성
- 없음

## 리스크 / 확인 필요
- **repository는 자동 테스트가 없다**. `$or` 위치 조건과 `(created_at, _id)` 정렬, 같은 `created_at` 문서가 페이지 사이에서 빠지거나 겹치지 않는지는 로컬 MongoDB 임시 DB로 확인했다(`implement.md`). 확인 스크립트는 scratchpad에 두고 확인 후 지운다.
- **MongoDB 시각 정밀도**: 밀리초까지만 저장한다. cursor는 항상 DB에서 읽은 값으로 만들므로 왕복이 정확하다. 가짜 repository는 마이크로초 값을 갖지만 같은 값을 비교하므로 테스트에 영향이 없다.
