# 확인 가이드 (Quickstart): job 단건 조회 API

계약은 [contracts/get-job.md](contracts/get-job.md).

## 준비
- 로컬 MongoDB, kubeconfig
- `MONGO_DB_NAME=<임시 DB> uv run uvicorn src.main:app` 후 `/docs`에서 `POST /jobs`로 `alice`의 job 하나(example `minimal`), `bob`의 job 하나를 만든다. 끝나면 임시 DB를 지운다

## 시나리오
### 1. US1 내 job 상세
- **실행**: `GET /jobs/{alice의 job id}`, `X-User-Id: alice`
- **기대 결과**: 200, 생성 응답과 같은 본문(이름, `namespace: user-alice`, `status: pending`, 기본값이 채워진 `template`, Deployment·Service 요약)

### 2. US2 없음
- **실행**: `alice`로 `bob`의 job id / 형식은 맞지만 없는 id(`6720a1b2c3d4e5f6a7b8c9d0`) / `abc`
- **기대 결과**: 셋 다 404 `job_not_found`, 같은 본문

### 3. 헤더 오류
- **실행**: `X-User-Id` 없이 `GET /jobs/abc`
- **기대 결과**: 400 `invalid_user_id`

### 4. API 문서
- **실행**: `/docs`, `/redoc`
- **기대 결과**: `GET /jobs/{job_id}`에 200·400·404·500, 200·404 example이 실제 값. `POST /jobs`·`GET /jobs`에는 404가 없다

## 자동 확인
- `uv run ruff check .`, `uv run ruff format .`, `uv run pytest`
