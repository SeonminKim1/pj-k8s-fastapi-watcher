# IMPLEMENT: job 생성 API

## 진행 기록
- ▶ 1단계 (병렬) T1, T2 시작 — 형식 타입·템플릿 모델, ErrorEnum·검증 에러 매핑(이후 작업의 기반)
- ✔ T1 완료 — `src/models/k8s_names.py` 추가, `src/models/user_job.py`에 `JobSize`·`WebTemplate`·`JobTemplate`·`MAX_JOBS_PER_USER` 추가, `tests/test_user_job_model.py`. pytest 146 passed (#8)
- ✔ T2 완료 — `ErrorEnum` 9개 추가·`INVALID_PARAMETER` 메시지 변경, `src/core/exception/validation_error.py`(`to_error_enum`), `tests/test_validation_error.py`. pytest 174 passed (#9)

## spec과 달라진 점
- 없음

## 완료 체크리스트
- [ ] `uv run ruff check .` / `uv run ruff format .` 통과
- [ ] 레이어 규칙 준수 (Router → Service → Repository, 비즈니스 에러는 `MyApiError`)
- [ ] spec의 정상 케이스와 에러 케이스를 `/docs`에서 직접 호출해 확인
- [ ] `uv run pytest` 통과 (비즈니스 규칙마다 service 테스트 존재)
- [ ] README 등 관련 문서 갱신
- [ ] task.md 체크리스트 모두 완료

## 메모
