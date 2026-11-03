# IMPLEMENT: job 목록 조회 API

## 진행 기록
- ▶ 1단계 (순차) T1 시작 — 다른 작업이 함께 쓰는 모델·limit 상수·에러 종류 정의
- ✔ T1 완료 — `models/user_job.py`(`JobPosition`, `JobPage`, `JOB_LIST_DEFAULT_LIMIT`·`JOB_LIST_MAX_LIMIT`), `ErrorEnum` 3개, `_PRIORITY`, `test_validation_error.py`. ruff 통과, pytest 222 passed (#19)
- ■ 1단계 완료 — 다음: 2단계 T2, T3
- ▶ 2단계 (병렬) T2, T3 시작 — cursor 인코딩 모듈, repository 위치 조회
- ✔ T2 완료 — `services/job_cursor.py`, `tests/test_job_cursor.py`(왕복 3, 잘못된 cursor 11). pytest 236 passed. `encode_cursor` 인자를 plan의 `UserJob`에서 `JobPosition`으로 바꿈(아래 메모) (#20)
- ✔ T3 완료 — `find_active_by_owner` → `find_active_page(owner_id, status, after, limit)`. 로컬 MongoDB 9.0.2 임시 DB에서 6개 항목 확인 후 DB 삭제(아래 메모). service는 T4까지 옛 메서드를 부르므로 이 커밋 시점에는 실제 repository로 `list_jobs`가 동작하지 않는다(쓰는 곳 없음) (#21)

## spec과 달라진 점
- 없음

## 완료 체크리스트
- [ ] `uv run ruff check .` / `uv run ruff format .` 통과
- [ ] 레이어 규칙 준수 (Router → Service → Repository, 비즈니스 에러는 `MyApiError`)
- [ ] spec의 정상 케이스와 에러 케이스를 `/docs`에서 직접 호출해 확인
- [ ] `/redoc`에서 요청·응답 example이 실제 값으로 보이는지 확인 (`docs/fastapi-sdd-template.md`의 "API 문서 (OpenAPI)")
- [ ] `uv run pytest` 통과 (비즈니스 규칙마다 service 테스트 존재)
- [ ] README 등 관련 문서 갱신
- [ ] task.md 체크리스트 모두 완료

## 메모
- `encode_cursor(position: JobPosition)`: plan은 `encode_cursor(job: UserJob)`이었지만, `decode_cursor`와 같은 타입을 주고받게 해 왕복 테스트를 단순하게 했다. service가 마지막 항목으로 `JobPosition`을 만들어 넘긴다. 외부 동작은 같다.
- T3 로컬 MongoDB 확인(9.0.2, 임시 DB `tmp_api_job_list_*`, 확인 후 삭제): alice 7개(같은 `created_at` 3개 포함)·삭제 1개·bob 1개로
  1. 전체 조회가 `created_at`·`_id` 내림차순, 삭제된 job·남의 job 제외
  2. `limit=2`로 끝까지 넘겼을 때 같은 시각 그룹이 페이지 경계에 걸려도 빠짐·겹침 없음
  3. `status=running` 필터
  4. `status=pending` + `limit=1` 페이지 넘김
  5. cursor 위치의 job을 삭제한 뒤에도 그 위치 뒤가 이어짐
  6. 다른 유저(bob)의 위치로 조회해도 alice의 job만 나옴
  - 실행 계획: MongoDB는 `owner_created_at`이 아니라 `uniq_owner_name`(`{owner_id, name}`, `is_deleted: false` partial)을 골랐다. 쿼리에 `is_deleted: false`가 있어 삭제된 문서가 빠진 partial 인덱스가 더 좁기 때문이다. 유저당 최대 10개를 메모리 정렬하므로 문제없고, 인덱스를 바꾸지 않는다는 plan 결정과도 맞다.
