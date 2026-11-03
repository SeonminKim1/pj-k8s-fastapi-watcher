# API: job 목록 조회
- **Method & Path**: `GET /jobs`
- **설명**: 삭제되지 않은 자기 job의 요약을 최신순으로 돌려준다. cursor 페이지네이션과 `status` 필터를 지원한다. MongoDB만 읽고 클러스터는 조회하지 않는다(`status`는 operator가 마지막으로 기록한 값).

## Request (schema)
**header**
| 필드 | 타입 | 필수 | 제약 |
|---|---|---|---|
| `X-User-Id` | `str` | O | `CLAUDE.md` 유저 ID 형식(소문자·숫자·`-`, 영숫자로 시작·끝, 1~58자). 공용 `UserIdHeader` |

**query**
| 필드 | 타입 | 필수 | 기본값 | 제약 |
|---|---|---|---|---|
| `limit` | `int` | X | `20` | 1~100. 한 페이지에 돌려줄 최대 개수 |
| `cursor` | `str` | X | 없음(첫 페이지) | 직전 응답의 `next_cursor`를 그대로 보낸다. 형식은 불투명(클라이언트가 해석·조립하지 않는다) |
| `status` | `"pending" \| "running" \| "failed"` | X | 없음(모든 상태) | 하나만. 여러 상태를 한 번에 거르지 않는다 |

- 쿼리는 모두 한 번만 지정할 수 있다. `?status=running&status=failed`, `?limit=5&limit=100`처럼 같은 쿼리를 여러 번 보내면 그 필드의 에러로 400이다(FastAPI 기본 동작인 "마지막 값 사용"으로 조용히 넘기지 않는다).

- 정의되지 않은 쿼리 파라미터는 무시한다(FastAPI 기본 동작). 게이트웨이·클라이언트가 붙이는 추가 쿼리에 깨지지 않게 하기 위함이다. 오타(`?stauts=running`)는 필터 없이 전체가 온다.
- 값이 빈 문자열이면(`?limit=`, `?cursor=`, `?status=`) 그 필드의 형식 오류로 400이다.
- 요청 예: `GET /jobs?limit=20&status=running`, 다음 페이지 `GET /jobs?limit=20&status=running&cursor=<next_cursor>`

## Response (schema)
`200 OK`, body `JobListResponse`:
| 필드 | 타입 | 설명 |
|---|---|---|
| `items` | `list[JobSummary]` | 이번 페이지의 job. 최신순. 없으면 `[]` |
| `next_cursor` | `str \| null` | 다음 페이지가 있으면 그 cursor, 없으면 `null` |

**JobSummary**
| 필드 | 타입 | 설명 |
|---|---|---|
| `id` | `str` | job ID |
| `name` | `str` | job 이름 |
| `status` | `"pending" \| "running" \| "failed"` | operator가 마지막으로 기록한 상태 |
| `created_at` | `datetime` (UTC, ISO 8601) | 생성 시각 |

- 템플릿·리소스·`namespace`·`updated_at`은 담지 않는다(상세는 이후 `api-job-get`). 필드는 나중에 추가할 수 있지만 빼기는 어려우므로 최소로 시작한다.
- 목록을 객체로 감싸므로 이후 필드(예: total count)를 추가해도 호환된다.
- 응답 예:
  ```json
  {
    "items": [
      {"id": "6720a1b2c3d4e5f6a7b8c9d1", "name": "api", "status": "running",
       "created_at": "2026-10-29T10:00:00Z"},
      {"id": "6720a1b2c3d4e5f6a7b8c9d0", "name": "my-web", "status": "pending",
       "created_at": "2026-10-29T09:00:00Z"}
    ],
    "next_cursor": null
  }
  ```
- 에러 응답은 기존과 같은 `{code, message}`. `/docs`에는 `200`·`400`·`500`만 문서화한다(`422`는 뺀다, `api-job-create`와 같음).

## 정렬과 cursor
- 정렬: `created_at` 내림차순, 같으면 `id`(ObjectId) 내림차순. 같은 시각에 만든 job도 순서가 정해져 페이지 사이에서 빠지거나 겹치지 않는다.
- cursor는 페이지 마지막 항목의 위치 `(created_at, id)`를 담은 불투명 문자열이다(인코딩은 PLAN에서 정한다). job ID나 DB 조회 없이 위치만으로 다음 페이지를 찾는다.
  - 다음 페이지 = 필터 조건을 만족하고 정렬 순서상 cursor 위치보다 뒤인 job.
  - cursor가 가리키던 job이 그사이 삭제되거나 상태가 바뀌어도 다음 페이지는 정상으로 이어진다(위치만 쓰므로).
  - 페이지를 넘기는 사이에 새로 만든 job은 cursor보다 앞(최신)이라 이어지는 페이지에 나오지 않는다. 첫 페이지를 다시 받으면 보인다.
  - cursor는 소유자 정보를 담지 않는다. 다른 유저가 만든 cursor를 보내도 자기(`X-User-Id`) job 중 그 위치 뒤의 것만 나오므로 남의 job이 드러나지 않는다.
  - 페이지마다 `status`·`limit`을 바꿔 보내도 된다. cursor는 위치만 뜻하므로 바꾼 조건으로 그 위치 뒤를 돌려준다.
- `next_cursor`는 다음 페이지에 항목이 실제로 있을 때만 준다(`limit + 1`개를 읽어 판단). 마지막 페이지의 `next_cursor`는 `null`이다.

## 비즈니스 로직 단계
1. router: `X-User-Id` 헤더와 쿼리를 schema로 파싱한다. 검증에 실패하면 `RequestValidationError` → 전역 핸들러가 아래 "요청 검증 에러"의 우선순위로 `ErrorEnum` 하나를 골라 400으로 응답한다.
2. router가 `UserJobService.list_jobs(owner_id, limit, cursor, status)`를 호출한다.
3. service(`docs/domain-user-job/spec.md`의 `list_jobs`):
   1. `owner_id` 형식 확인 → `INVALID_USER_ID`, `limit` 범위 확인 → `INVALID_LIMIT`(schema를 거치지 않는 호출자 대비)
   2. `cursor`가 있으면 위치로 풀고, 풀 수 없으면 `INVALID_CURSOR`
   3. 삭제되지 않은 자기 job 중 `status`(있으면) 조건과 cursor 위치 뒤를 정렬 순서로 `limit + 1`개 읽는다
   4. `limit`개를 넘게 읽혔으면 앞의 `limit`개를 돌려주고 마지막 항목으로 `next_cursor`를 만든다. 아니면 `next_cursor=None`
4. router가 결과를 `JobListResponse`로 바꿔 200으로 응답한다.

- 읽기 전용이라 동시성·멱등성 문제는 없다. 같은 요청은 그사이 데이터가 바뀌지 않았으면 같은 결과를 준다.
- job이 하나도 없거나 필터에 맞는 job이 없으면 `items: []`, `next_cursor: null`로 200(404 아님).

## 에러 케이스
에러 응답은 `{code, message}` 하나다. 틀린 곳이 여러 개면 아래 표의 위에서부터 **첫 번째 하나만** 알려준다.

**요청 검증 에러** (전역 `RequestValidationError` 핸들러, 모두 400)
| 우선순위 | 상황 | `ErrorEnum` (`code`) | message 예 |
|---|---|---|---|
| 1 | `X-User-Id` 없음·형식 오류 | `INVALID_USER_ID` (`invalid_user_id`) | 유저 ID는 소문자·숫자·'-'로 된 1~58자여야 합니다. |
| 2 | `limit` 정수 아님·1~100 밖·빈 값 | `INVALID_LIMIT` (`invalid_limit`) | limit은 1~100 사이의 정수여야 합니다. |
| 3 | `status` 지원하지 않는 값·빈 값·여러 번 지정 | `INVALID_JOB_STATUS` (`invalid_job_status`) | status는 pending, running, failed 중 하나만 지정할 수 있습니다. |
| 4 | `cursor` 여러 번 지정 | `INVALID_CURSOR` (`invalid_cursor`) | cursor가 올바르지 않습니다. 직전 응답의 next_cursor를 그대로 보내야 합니다. |

- `_PRIORITY`(`src/core/exception/validation_error.py`)에서 `INVALID_LIMIT`·`INVALID_JOB_STATUS`·`INVALID_CURSOR`는 `INVALID_PARAMETER` 뒤에 둔다. 이 API에는 body가 없어 `INVALID_PARAMETER`가 나올 일이 없으므로 위 순서가 그대로 적용된다.
- "여러 번 지정" 검사는 헤더·값 형식 검사가 모두 통과한 뒤에 한다. 그래서 `?limit=5&limit=6&status=bad`는 표 순서와 달리 `invalid_job_status`다(중복된 `limit` 값 자체는 올바르므로). 둘 다 고쳐야 하는 요청이라 실사용에 영향은 없다.

**비즈니스 에러** (service)
| 상황 | `ErrorEnum` (`code`) | 상태 코드 |
|---|---|---|
| `cursor`를 풀 수 없음(빈 값, base64url이 아님, 형식 오류, 조작된 값, UTC로 바꾸면 날짜 범위를 벗어나는 시각) | `INVALID_CURSOR` (`invalid_cursor`) | 400 |

- message 예: "cursor가 올바르지 않습니다. 직전 응답의 next_cursor를 그대로 보내야 합니다."
- cursor 검사는 service에서 하므로 요청 검증 에러(위 표)가 있으면 그쪽이 먼저 나온다.
- 형식은 맞지만 어떤 job도 가리키지 않는 cursor(삭제된 job, 남의 job의 위치 등)는 에러가 아니다(위 "정렬과 cursor").

**서버 오류** (전역 핸들러)
| 상황 | `code` | 상태 코드 |
|---|---|---|
| MongoDB 오류 | `db_error` | 500 |
| 그 외 예외 | `unknown_error` | 500 |

## 의존 리소스
- `UserJobService` (`Depends(get_user_job_service)`)
- MongoDB `user_jobs` 컬렉션(목록 인덱스는 PLAN에서 정렬·cursor 조건에 맞게 조정)
- 클러스터: 사용하지 않음
