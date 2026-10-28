# TASK: job 생성 API

## 실행 흐름
1. (병렬) T1, T2
2. (병렬) T3, T4
3. (순차) T5
4. (순차) T6
5. (순차) T7
6. (순차) T8

## 작업
- [ ] T1 [api-job-create] 형식 타입(`models/k8s_names.py`)과 템플릿 모델(`WebTemplate`·`JobTemplate`·`JobSize`·`MAX_JOBS_PER_USER`) 정의 + 모델 검증 테스트 — 선행: 없음 — #8
- [ ] T2 [api-job-create] `ErrorEnum` 추가(필드별 9개, `INVALID_PARAMETER` 메시지)와 요청 검증 에러 매핑(`core/exception/validation_error.py`) + 매핑 테스트 — 선행: 없음 — #9
- [ ] T3 [api-job-create] `web` 템플릿 → Deployment·Service 매니페스트 생성(`services/job_templates.py`) + 생성 테스트 — 선행: T1 — #10
- [ ] T4 [api-job-create] repository 슬롯 저장(`insert_with_slot`, `uniq_owner_slot` 인덱스) + 로컬 MongoDB 확인 — 선행: T1 — #11
- [ ] T5 [api-job-create] `UserJob`에 `template`·`quota_slot` 추가, `create_job`을 템플릿 입력·개수 한도·`INVALID_USER_ID`·`INVALID_JOB_NAME`으로 변경 + service 테스트 갱신(옛 매니페스트 검증 테스트 제거) — 선행: T2, T3, T4 — #12
- [ ] T6 [api-job-create] 쓰지 않게 된 옛 코드 제거(`_build_resources`·이름 검사 함수·정규식 상수, repository `insert`, `ALLOWED_RESOURCE_KINDS`, `INVALID_JOB_RESOURCE`) — 선행: T5 — #13
- [ ] T7 [api-job-create] `schemas/job.py`, `routers/job_router.py`(`POST /jobs`), `main.py` 라우터·검증 에러 핸들러 등록 + router 테스트(에러 표 행마다) — 선행: T6 — #14
- [ ] T8 [api-job-create] 문서 갱신(README API 표, `CLAUDE.md` 고유 구성, `domain-user-job` 변경 섹션), `/docs`에서 정상·에러 케이스 직접 호출, 완료 체크리스트 — 선행: T7 — #15

## 메모
- 커밋마다 `ruff`·`pytest`가 통과해야 하므로, 기존 동작을 바꾸는 변경(`UserJob` 필수 필드 추가, `create_job` 시그니처)은 T5에 모으고, 그 결과 쓰지 않게 된 코드 제거는 T6으로 분리했다(사용자 요청: 리뷰 단위를 작게). T1·T2·T4는 기존 코드를 건드리지 않고 추가만 한다.
