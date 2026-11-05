# 구현 계획: user-job 도메인 모델

- **브랜치**: (이관 전 `feature/domain-user-job`) | **작성일**: 2026-10-27 (2026-11-06 이관) | **spec**: [spec.md](spec.md)

## 요약 (Summary)
user-job 모델·repository·service와 생성자 주입 구조를 만든다. MongoDB는 비동기로 접근하고, 한도·이름 중복은 partial 유니크 인덱스로, 상태 전이는 조건부 갱신 한 번으로 지킨다(결정 근거는 [research.md](research.md)). 이후 `002-api-job-create`에서 템플릿 입력과 개수 한도가, `003-api-job-list`에서 cursor 목록 조회가 이 도메인에 더해졌고, 이 문서는 그 결과를 포함한 현재 상태다.

## 기술 맥락 (Technical Context)
- **언어/버전**: Python (uv)
- **주요 의존성**: FastAPI, Pydantic, `pymongo` 4.19(`AsyncMongoClient`), `kubernetes`
- **저장소**: MongoDB `user_jobs` 컬렉션
- **테스트**: `uv run pytest`(가짜 repository 주입), repository는 로컬 MongoDB 임시 DB로 직접 확인
- **실행 환경**: 클러스터 설정(in-cluster 또는 kubeconfig)과 MongoDB가 있어야 앱이 뜬다
- **유형**: 도메인 모델
- **성능·제약**: 유저당 job 10개

## Constitution Check
| 원칙·요구사항 | 이 기능에서 지키는 방법 | 결과 |
|---|---|---|
| II. 레이어 | Service → Repository, MongoDB는 repository로만, `K8sService`는 주입 | 통과 |
| III. 테스트 | 소유권·한도·이름 중복·상태 전이·soft delete마다 service 테스트(가짜 repository) | 통과 |
| IV. 에러 표현 | `MyApiError(ErrorEnum.XXX)`, 400/404, 500은 전역 핸들러 | 통과 |
| `CLAUDE.md`: 유저별 job 개수 제한 | `quota_slot` 유니크 partial 인덱스 | 통과 |
| `CLAUDE.md`: 유저별 네임스페이스 | `namespace`는 서버가 `user-{owner_id}`로 정함 | 통과 |
| `CLAUDE.md`: operator 패턴 | 상태 갱신은 operator 전용 메서드, 라벨은 operator가 apply 때 붙임 | 통과 |

## 프로젝트 구조 (Project Structure)

### 변경 파일 (Source Code)
- `src/schemas/`: 없음(라우터 없음)
- `src/models/`
  - `user_job_models.py` (신규): `JobResource`, `UserJob`(`id`는 `str`), 상태 전이 표. 이후 `WebTemplate`·`JobTemplate`·`MAX_JOBS_PER_USER`(002), `JobPosition`·`JobPage`·limit 상수(003)
  - `enums.py`: `JobStatus`(`pending`/`running`/`failed`), 이후 `JobType`·`JobSize`
  - `k8s_names.py`: 형식 규칙(002에서 service에서 옮김)
- `src/repository/user_job_repository.py` (신규): `UserJobRepository(collection: AsyncCollection)`
  - `ensure_indexes()`: `uniq_owner_name`, `owner_created_at`(+ `uniq_owner_slot`, 002)
  - `insert_with_slot(job_doc, max_slots) -> UserJob`(002에서 `insert`를 바꿈): 이름 인덱스 위반이면 `DuplicateJobNameError`, 슬롯이 없으면 `JobQuotaExceededError`
  - `find_active_page(owner_id, status, after, limit)`(003에서 `find_active_by_owner`를 바꿈)
  - `find_active_by_id(job_id) -> UserJob | None`: 잘못된 ObjectId·없음·삭제됨이면 `None`
  - `update_status_from(job_id, from_statuses, to_status, now) -> UserJob | None`: `status: {$in: from_statuses}`이고 삭제되지 않았을 때만 `find_one_and_update`
  - `soft_delete(owner_id, job_id, now) -> bool`
- `src/services/`
  - `user_job_service.py` (신규): `UserJobService(repository)`. data-model의 5개 메서드, 입력 검증(`_validate_user_id`, `_validate_job_name`), 상태 전이 판단
  - `k8s_service.py` (수정): `K8sService(api_client: ApiClient)`. 생성자에서 설정 로딩 제거, `batch_v1` 추가
- `src/core/`
  - `db/mongodb.py` (수정): `MongoClient` → `AsyncMongoClient(tz_aware=True)`, `get_database()`는 `AsyncDatabase`, `close_client()`
  - `dependencies.py` (신규): `get_k8s_service()`(`functools.cache`), `close_k8s_service()`, `get_user_job_repository()`, `get_user_job_service()`
  - `exception/my_exception.py` (수정): `JOB_NAME_DUPLICATED`, `INVALID_STATUS_TRANSITION`(400), `JOB_NOT_FOUND`(404)
- `src/main.py` (수정): lifespan에서 `get_k8s_service()` → `ensure_indexes()`를 `try` 안에서, 종료 시 `close_client()`·`close_k8s_service()`
- `tests/`: `test_user_job_service.py`(가짜 repository: 메모리 dict, 유니크·조건부 갱신 흉내), `test_dependencies.py`, `test_mongodb.py`, `test_main.py`
- 문서: `CLAUDE.md` 고유 모듈(MongoDB, `dependencies.py`)

### DB 변경
- 컬렉션 `user_jobs` 신규
- 인덱스: `uniq_owner_name` `{owner_id: 1, name: 1}` unique, partial `{is_deleted: false}` / `owner_created_at` `{owner_id: 1, created_at: -1}` (+ `uniq_owner_slot`, 002)
- 기존 데이터 마이그레이션: 없음

### 외부 의존성
- 새 패키지 없음(`pymongo`의 `AsyncMongoClient`, `kubernetes` 사용)

## 리스크 / 확인 필요
- **repository는 자동 테스트가 없다**(실제 DB 금지 규칙). partial 유니크 인덱스와 조건부 갱신은 로컬 MongoDB 임시 DB로 직접 확인하고 `implement.md`에 남긴다. repository를 고치면 다시 확인한다.
- **앱 시작에 MongoDB와 클러스터 설정이 필요하다.** 스모크 테스트는 `TestClient(app)`를 `with` 없이 써서 lifespan을 타지 않는다.
