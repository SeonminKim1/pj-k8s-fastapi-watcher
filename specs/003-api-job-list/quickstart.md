# 확인 가이드 (Quickstart): job 목록 조회 API

계약은 [contracts/get-jobs.md](contracts/get-jobs.md).

## 준비
- 로컬 MongoDB, kubeconfig
- `MONGO_DB_NAME=<임시 DB> uv run uvicorn src.main:app` 후 `POST /jobs`로 `alice` job 5개, `bob` job 1개를 만든다. 끝나면 임시 DB를 지운다

## 시나리오
### 1. US1 기본 조회
- **실행**: `GET /jobs`, `X-User-Id: alice`
- **기대 결과**: 200, `alice`의 job 5개 최신순, `next_cursor: null`(`bob` 제외)

### 2. US2 나눠 받기
- **실행**: `GET /jobs?limit=2` → 응답의 `next_cursor`로 끝까지
- **기대 결과**: `[2개] [2개] [1개]`, 마지막만 `next_cursor: null`

### 3. US3 상태 필터
- **실행**: `GET /jobs?status=running`
- **기대 결과**: 200, `running` job만(operator가 없으면 `{"items": [], "next_cursor": null}`)

### 4. 잘못된 요청
- **실행**: `limit=0`·`limit=abc` / `status=bad`·`status` 두 번 / `cursor=bad`·`cursor=` / 헤더 없음 + `status` 두 번
- **기대 결과**: 400 `invalid_limit` / `invalid_job_status` / `invalid_cursor` / `invalid_user_id`

### 5. API 문서
- **실행**: `/docs`, `/redoc`
- **기대 결과**: 200·400·500만 있고, 파라미터 4개와 200 응답에 example

## 자동 확인
- `uv run ruff check .`, `uv run ruff format .`, `uv run pytest`
