# 확인 가이드 (Quickstart): job 생성 API

계약은 [contracts/post-jobs.md](contracts/post-jobs.md).

## 준비
- 로컬 MongoDB, kubeconfig
- `MONGO_DB_NAME=<임시 DB> uv run uvicorn src.main:app` 후 `/docs`(Swagger UI). 끝나면 임시 DB를 지운다

## 시나리오
### 1. US1 정상 생성
- **실행**: `/docs`에서 `POST /jobs`, 헤더 `X-User-Id: alice`, 요청 example `minimal`
- **기대 결과**: 201, `status: pending`, `namespace: user-alice`, `resources`에 Deployment·Service, 기본값(`replicas: 1`, `env: {}`, `size: small`)

### 2. US2 잘못된 요청
- **실행**: 이미지 `nginx:latest` / `template`에 `hostNetwork: true` / 헤더 없이 JSON이 아닌 body
- **기대 결과**: 400 `invalid_image` / `invalid_parameter` / `invalid_user_id`

### 3. US3 한도와 중복
- **실행**: 같은 유저로 서로 다른 이름 10개 생성 후 11번째, 같은 이름 다시 생성, 새 유저로 동시 15개 생성
- **기대 결과**: 400 `job_quota_exceeded` / 400 `job_name_duplicated` / 201 10개·400 5개

### 4. API 문서
- **실행**: `/docs`, `/redoc`
- **기대 결과**: `POST /jobs`에 201·400·500만 있고 422 없음, 요청·응답 example이 실제 값

## 자동 확인
- `uv run ruff check .`, `uv run ruff format .`, `uv run pytest`
