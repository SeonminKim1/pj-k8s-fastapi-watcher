# 데이터 모델: job 목록 조회 API

모델 전체는 `specs/001-domain-user-job/data-model.md`가 기준이다. 이 기능에서 더한 것만 적는다. `user_jobs` 컬렉션·필드·인덱스는 바꾸지 않는다.

## JobPosition (`src/models/user_job_models.py`) — 신규
cursor가 가리키는 정렬 위치.
| 필드 | 타입 | 필수 | 제약·검증 | 누가 정하나 |
|---|---|---|---|---|
| `created_at` | `datetime` (UTC) | O | job의 생성 시각 | 서버 |
| `id` | `str` | O | 24자리 hex(ObjectId) | 서버 |

## JobPage (`src/models/user_job_models.py`) — 신규
`list_jobs`의 반환값.
| 필드 | 타입 | 필수 | 제약·검증 | 누가 정하나 |
|---|---|---|---|---|
| `items` | `list[UserJob]` | O | 최신순, 최대 `limit`개 | 서버 |
| `next_cursor` | `str \| None` | | 다음 페이지에 항목이 있을 때만 | 서버 |

## 상수
- `JOB_LIST_DEFAULT_LIMIT = 20`, `JOB_LIST_MAX_LIMIT = 100` (`MAX_JOBS_PER_USER` 옆)

## 조회 조건 (`find_active_page(owner_id, status, after, limit)`)
- `{owner_id, is_deleted: false, status?(있으면), $or: [{created_at: {$lt: t}}, {created_at: t, _id: {$lt: oid}}](after가 있으면)}`
- 정렬 `[(created_at, -1), (_id, -1)]`, `limit`(service가 `limit + 1`을 넘긴다)
