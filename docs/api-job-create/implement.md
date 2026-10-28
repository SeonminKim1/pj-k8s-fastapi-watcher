# IMPLEMENT: job 생성 API

## 진행 기록
- ▶ 1단계 (병렬) T1, T2 시작 — 형식 타입·템플릿 모델, ErrorEnum·검증 에러 매핑(이후 작업의 기반)
- ✔ T1 완료 — `src/models/k8s_names.py` 추가, `src/models/user_job.py`에 `JobSize`·`WebTemplate`·`JobTemplate`·`MAX_JOBS_PER_USER` 추가, `tests/test_user_job_model.py`. pytest 146 passed (#8)
- ✔ T2 완료 — `ErrorEnum` 9개 추가·`INVALID_PARAMETER` 메시지 변경, `src/core/exception/validation_error.py`(`to_error_enum`), `tests/test_validation_error.py`. pytest 174 passed (#9)
- ■ 1단계 완료 — 다음: 2단계 T3, T4
- ▶ 2단계 (병렬) T3, T4 시작 — web 템플릿 매니페스트 생성, repository 슬롯 저장
- ✔ T3 완료 — `src/services/job_templates.py`(`build_resources`, `SIZE_PRESETS`, `KINDS_BY_TYPE`), `tests/test_job_templates.py`. pytest 185 passed (#10)
- ✔ T4 완료 — `src/repository/user_job_repository.py`에 `insert_with_slot`·`JobQuotaExceededError`·`uniq_owner_slot` 인덱스 추가. 로컬 MongoDB 9.0.2 임시 DB에서 9개 항목 확인 후 DB 삭제(아래 메모). pytest 185 passed (#11)

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
- **T4 로컬 MongoDB 확인**(9.0.2 standalone, 임시 DB `k8s_client_t4_check`, 확인 후 삭제): 인덱스 3개 생성(`uniq_owner_slot` partial `{is_deleted: false, quota_slot: {$exists: true}}`), 10개 저장 시 슬롯 0~9, 11번째 한도 초과, 한도가 찬 상태의 중복 이름은 한도 초과가 먼저, soft delete 후 비운 슬롯(3) 재사용, 빈 슬롯이 있을 때 중복 이름은 이름 중복, **동시 15개 → 정확히 10개 성공·나머지 한도 초과**, 같은 이름 동시 5개 → 1개 성공, `quota_slot` 없는 옛 문서 여러 개 저장 가능. 확인 스크립트는 저장소에 두지 않고 확인 후 scratchpad에서도 지웠다. repository를 고치면 같은 항목을 다시 확인한다.
