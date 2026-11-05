# API 계약: job 단건 조회

- **Method & Path**: `GET /jobs/{job_id}`
- **설명**: 삭제되지 않은 자기 job 하나의 상세를 돌려준다. 남의 job·없는 job·삭제된 job·형식이 틀린 ID는 모두 `job_not_found`. MongoDB만 읽고 클러스터는 조회하지 않는다(`status`는 operator가 마지막으로 기록한 값).
- **관련 요구사항**: FR-001~FR-005, US1, US2

## 요청 (Request)
| 필드 | 위치 | 타입 | 필수 | 기본값 | 설명 |
|---|---|---|---|---|---|
| `X-User-Id` | header | `str` | O | | `CLAUDE.md` 유저 ID 형식(소문자·숫자·`-`, 영숫자로 시작·끝, 1~58자). 공용 `UserIdHeader` |
| `job_id` | path | `str` | O | | job ID(생성·목록 응답의 `id`). 형식을 검사하지 않는다(틀리면 없음) |

- 요청 예: `GET /jobs/6720a1b2c3d4e5f6a7b8c9d0`

## 응답 (Response)
- **상태 코드**: `200 OK`, body `JobResponse`(`src/schemas/job_response.py`, example `JOB_RESPONSE_EXAMPLE`)

| 필드 | 타입 | 설명 |
|---|---|---|
| `id` | `str` | job ID |
| `name` | `str` | job 이름 |
| `namespace` | `str` | `user-{유저 ID}` |
| `status` | `"pending" \| "running" \| "failed"` | operator가 마지막으로 기록한 상태 |
| `template` | `JobTemplate` | 생성 요청의 `template`(기본값이 채워진 상태) |
| `resources` | `list[{kind: str, name: str}]` | 서버가 만든 리소스 요약. 매니페스트 본문은 응답하지 않는다 |
| `created_at` | `datetime` (UTC, ISO 8601) | 생성 시각 |
| `updated_at` | `datetime` (UTC, ISO 8601) | 마지막 변경 시각 |

- `POST /jobs`의 201 응답과 같은 모양이다. `owner_id`, `is_deleted`, `deleted_at`, `quota_slot`, 매니페스트 본문은 응답하지 않는다.
- 에러 응답은 `{code, message}`. `/docs`에는 `200`·`400`·`404`·`500`만 문서화한다(404는 이 엔드포인트에만, research "404 응답 문서").

## 처리 단계
1. router: `X-User-Id` 헤더를 `UserIdHeader`로 파싱한다. 실패하면 전역 `RequestValidationError` 핸들러가 400 `invalid_user_id`.
2. router가 `UserJobService.get_job(owner_id, job_id)`를 호출한다.
3. service(`specs/001-domain-user-job/data-model.md`의 `get_job`):
   1. `owner_id` 형식 확인 → `INVALID_USER_ID`(schema를 거치지 않는 호출자 대비)
   2. `find_active_by_id(job_id)`로 읽고, 없거나(잘못된 ID·삭제됨 포함) 소유자가 다르면 `JOB_NOT_FOUND`
4. router가 job을 `JobResponse.from_job()`으로 바꿔 200으로 응답한다.

- 읽기 전용이라 동시성·멱등성 문제는 없다.

## 에러 (Errors)
에러 응답은 `{code, message}` 하나다. 이 표가 `GET /jobs/{job_id}` 에러 code 목록의 기준이다.

| 상황 | 에러 식별자 (`code`) | 상태 코드 | 관련 엣지 케이스 |
|---|---|---|---|
| `X-User-Id` 없음·형식 오류(job ID가 틀려도 먼저) | `INVALID_USER_ID` (`invalid_user_id`) | 400 | 유저 ID 없음·형식 오류 |
| 남의 job | `JOB_NOT_FOUND` (`job_not_found`) | 404 | 남의 job ID |
| 없는 job(형식은 맞음) | `JOB_NOT_FOUND` (`job_not_found`) | 404 | 없는 ID |
| 삭제된 job | `JOB_NOT_FOUND` (`job_not_found`) | 404 | 삭제된 job |
| job ID가 ObjectId 형식이 아님 | `JOB_NOT_FOUND` (`job_not_found`) | 404 | 형식이 틀린 ID |
| MongoDB 오류 | `db_error` (전역 핸들러) | 500 | DB 오류 |
| 그 외 예외 | `unknown_error` (전역 핸들러) | 500 | |

- message: `job_not_found`는 "job을 찾을 수 없습니다."(`ErrorEnum.JOB_NOT_FOUND`). 네 경우 모두 같은 본문이다.
- 삭제 후 같은 이름으로 새로 만든 job은 ID가 다르므로 옛 ID로는 404, 새 ID로는 새 job이 나온다.

## 의존 리소스
- `UserJobService` (`Depends(get_user_job_service)`)
- MongoDB `user_jobs` 컬렉션(`_id` 조회)
- 클러스터: 사용하지 않음
