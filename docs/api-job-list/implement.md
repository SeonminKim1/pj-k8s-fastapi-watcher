# IMPLEMENT: job 목록 조회 API

## 진행 기록
- ▶ 1단계 (순차) T1 시작 — 다른 작업이 함께 쓰는 모델·limit 상수·에러 종류 정의
- ✔ T1 완료 — `models/user_job.py`(`JobPosition`, `JobPage`, `JOB_LIST_DEFAULT_LIMIT`·`JOB_LIST_MAX_LIMIT`), `ErrorEnum` 3개, `_PRIORITY`, `test_validation_error.py`. ruff 통과, pytest 222 passed (#19)

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
