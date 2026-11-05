# 구현 기록: job 단건 조회 API

## 진행 기록
- ▶ 1단계 (순차) T001 시작 — 404 응답 문서와 `GET /jobs/{job_id}` 라우터, router 테스트. 기존 service·schema를 엔드포인트로 연결
- ✔ T001 완료 — `src/schemas/error_response.py`(`NOT_FOUND_RESPONSES`), `src/routers/job_router.py`(`GET /jobs/{job_id}`), `tests/test_job_router.py`(8개). ruff 통과, pytest 295 passed
- ■ 1단계 완료 — 다음: 2단계 T002 (README, quickstart 직접 확인, 완료 체크리스트)

## spec과 달라진 점
- 없음

## 완료 체크리스트
- [ ] `uv run ruff check .` / `uv run ruff format .` 통과
- [ ] 레이어 규칙·에러 표현 준수 (Router → Service → Repository, 비즈니스 에러는 `MyApiError`)
- [ ] quickstart 시나리오(정상·에러)를 직접 실행해 확인 (`/docs`)
- [ ] `/redoc`에서 요청·응답 example이 실제 값으로 보이는지 확인
- [ ] `uv run pytest` 통과 (비즈니스 규칙·에러 케이스마다 테스트)
- [ ] README 등 관련 문서 갱신
- [ ] tasks.md 모두 완료, converge `✅ 수렴`

## 메모
- 이슈 트래커: 이 기능은 이슈를 만들지 않는다(tasks.md).
