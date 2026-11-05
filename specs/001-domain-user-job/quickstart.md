# 확인 가이드 (Quickstart): user-job 도메인 모델

API가 없는 domain 기능이라 service 테스트와 로컬 MongoDB 확인으로 검증한다. 규칙은 [data-model.md](data-model.md).

## 준비
- 로컬 MongoDB(9.0.2 standalone에서 확인), `MONGO_DB_NAME`은 임시 DB 이름으로
- kubeconfig(앱 기동 확인 시)

## 시나리오
### 1. 규칙별 service 테스트
- **실행**: `uv run pytest tests/test_user_job_service.py`
- **기대 결과**: 생성·목록·단건·상태 갱신·삭제의 정상·에러 케이스 통과

### 2. repository를 실제 MongoDB로 (repository를 고쳤을 때)
- **실행**: scratchpad 스크립트로 임시 DB에 `UserJobRepository`를 붙여 확인하고, 끝나면 DB와 스크립트를 지운다
- **기대 결과**: 이름 partial 유니크(삭제 후 재사용 가능), 슬롯 한도(동시 15개 → 10개 성공), `update_status_from`의 `$in` 조건부 갱신 성공·빗나감(`None`), 이름 외 유니크 위반은 `DuplicateKeyError` 그대로

### 3. 앱 기동
- **실행**: `MONGO_DB_NAME=<임시 DB> uv run uvicorn src.main:app`
- **기대 결과**: `/docs` 200, `user_jobs` 인덱스 생성. 클러스터 설정이 없으면 시작 실패

## 자동 확인
- `uv run ruff check .`, `uv run ruff format .`, `uv run pytest`
