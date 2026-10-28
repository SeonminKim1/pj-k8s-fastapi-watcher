# IMPLEMENT: user-job 도메인 모델

## 진행 기록
- ▶ 1단계 (병렬) T1, T2 시작 — 모델·에러 정의, MongoDB 비동기 전환·K8sService 주입 구조
- ✔ T1 완료 — `src/models/user_job.py` 추가, `ErrorEnum` 4개 추가. ruff·pytest 통과 (#1)
- ✔ T2 완료 — `mongodb.py` → `AsyncMongoClient(tz_aware=True)`, `K8sService(api_client)` 생성자 주입(`batch_v1` 추가) (#2)
- ■ 1단계 완료 — 다음: 2단계 T3
- ▶ 2단계 (순차) T3 시작 — repository 구현과 로컬 MongoDB 확인
- ✔ T3 완료 — `src/repository/user_job_repository.py`. 로컬 MongoDB 9.0.2 임시 DB에서 11개 항목 확인 후 DB 삭제 (#3)
- ■ 2단계 완료 — 다음: 3단계 T4
- ▶ 3단계 (순차) T4 시작 — service와 가짜 repository 주입 테스트
- ✔ T4 완료 — `src/services/user_job_service.py`, `tests/test_user_job_service.py`. pytest 49 passed. spec 보완(아래) (#4)
- ■ 3단계 완료 — 다음: 4단계 T5
- ▶ 4단계 (순차) T5 시작 — dependencies와 lifespan
- ✔ T5 완료 — `src/core/dependencies.py`, `main.py` lifespan, `tests/test_dependencies.py`. pytest 52 passed. 로컬 MongoDB로 앱 기동 확인(`/docs` 200, `k8s_client.user_jobs` 인덱스 생성) (#5)
- ■ 4단계 완료 — 다음: 5단계 T6
- ▶ 5단계 (순차) T6 시작 — 문서 갱신, 완료 체크리스트
- ✔ T6 완료 — `CLAUDE.md` 고유 구성 갱신, 완료 체크리스트 수행 (#6)
- ■ 5단계 완료 — 모든 작업 완료

## spec과 달라진 점
- `update_job_status`의 동시 갱신 재시도에 상한을 두었다. 3번 연속 조건부 갱신이 어긋나면 `INVALID_STATUS_TRANSITION`. spec.md에 반영함.
- 작업 확인(T2) 중 요청으로 앱 종료 시 MongoDB 연결을 닫도록 추가했다: `mongodb.close_client()`, lifespan 종료 시 호출, `tests/test_mongodb.py`. spec.md에 반영함.
- 작업 확인(T4) 전 셀프 리뷰에서 버그 수정: 매니페스트의 `apiVersion`·`kind`가 문자열이 아니면(예: dict) 허용 목록 조회에서 `TypeError`(500)가 났다. 문자열 검사를 먼저 하도록 고치고 테스트 2개 추가.
- 작업 확인(T5) 중 요청으로 클러스터 설정이 없으면 앱 시작을 실패시키도록 했다: lifespan에서 `get_k8s_service()`를 MongoDB보다 먼저 호출, `tests/test_main.py`에 테스트 추가. spec.md·CLAUDE.md에 반영함.
- `K8sService`에 `batch_v1`(`BatchV1Api`)을 추가했다. 허용 리소스에 `batch/v1 Job`이 있어 operator가 쓸 것이므로.

## 완료 체크리스트
- [x] `uv run ruff check .` / `uv run ruff format .` 통과
- [x] 레이어 규칙 준수 (Service → Repository, 비즈니스 에러는 `MyApiError`. 라우터 없음)
- [x] ~~spec의 정상 케이스와 에러 케이스를 `/docs`에서 직접 호출해 확인~~ — API 없는 기능이라 해당 없음. 대신 repository를 로컬 MongoDB로 직접 확인(T3)
- [x] `uv run pytest` 통과 (57 passed, service 테스트에 SPEC의 정상·에러 케이스 포함)
- [x] README 등 관련 문서 갱신 (`CLAUDE.md` 고유 구성. README는 API·환경 변수 변화 없음)
- [x] task.md 체크리스트 모두 완료

## 메모
- repository 테스트는 실제 DB에 붙지 않는다는 규칙 때문에 자동 테스트가 없다. T3의 로컬 확인 스크립트로만 검증했으므로, repository를 고치면 로컬 MongoDB로 다시 확인한다.
- 기본 DB `k8s_client`에 다른 컬렉션(`deploy_jobs`, `deploy_query_logs`)이 이미 있다. 이름은 겹치지 않지만 다른 프로젝트 데이터라면 `MONGO_DB_NAME`을 분리한다.
- `gh issue close`가 `Could not close the issue` 오류를 내면서도 실제로는 닫히는 경우가 있었다(#4, #5). Project의 Status를 Done으로 바꾸면 이슈를 닫는 기본 워크플로와 겹친 것으로 추정한다(원인은 확인하지 않음).
- 다음 기능: `api-job-*`(job 생성·조회·삭제 API, 클러스터 네임스페이스 생성 정책 포함), `component-job-operator`(K8sService 메서드, reconcile, resync).
- **다음 schema 작업 때 할 일**(2026-10-28 결정): 형식 검증(`_is_user_id`, `_is_dns_label`, `_is_dns_subdomain`, `_is_dns_1035_label`)의 정규식을 공용 `Annotated` 타입(예: `src/models/k8s_names.py`)으로 분리해 schema·model·service가 함께 쓴다. FastAPI 기본 422를 400 `invalid_parameter`로 바꾸는 `RequestValidationError` 핸들러를 추가한다. 도메인 규칙(허용 목록, kind별 이름, 네임스페이스, 중복)은 service에 남기고, service의 형식 검사를 뺄지는 그 기능의 PLAN에서 정한다.

## 변경: 2026-10-28 모델 필드 설명 추가
- `src/models/user_job.py`의 `JobResource`·`UserJob` 모든 필드에 `Field(description=...)` 추가(SPEC 모델 표 기준). 동작 변화 없음(필수/기본값 그대로).
- `docs/fastapi-sdd-template.md` Python 규칙에 "models/·schemas/ 필드는 `Field(description=...)`" 추가.
- 확인: ruff, pytest 통과. `UserJob.model_json_schema()`에 설명 포함 확인.

## 변경: 2026-10-28 Service 이름 규칙(DNS-1035) 적용, 에러 규칙 500 명시
- Service 이름이 DNS-1123 subdomain으로만 검사돼 `1web`, `web.v1` 같은 이름이 저장 단계를 통과하고 operator apply에서야 실패하던 문제를 고쳤다. `_is_valid_resource_name(kind, name)`으로 kind별 규칙을 적용(Service는 DNS-1035 label). spec.md·모델 설명 갱신, 테스트 4개 추가.
- 사용자가 PRD의 에러 규칙을 400/404/500으로 수정함 → `CLAUDE.md` "에러 상태 코드"와 spec.md를 맞춤(비즈니스 에러는 400·404, 500은 전역 핸들러만).
