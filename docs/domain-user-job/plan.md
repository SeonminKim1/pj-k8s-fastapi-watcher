# PLAN: user-job 도메인 모델

## 결정 사항
- **MongoDB는 비동기(`AsyncMongoClient`)로 접근한다.** repository·service 메서드는 모두 `async def`. 이후 라우터도 `async def`로 쓴다. operator에서 동기 `kubernetes` 클라이언트를 부를 때는 `asyncio.to_thread`로 감싼다(operator 기능에서 다룸).
- **시각은 UTC aware `datetime`.** `AsyncMongoClient(tz_aware=True)`로 읽을 때도 UTC aware로 받는다.
- **중복 이름은 repository 전용 예외로 전달한다.** repository가 `DuplicateKeyError`를 잡아 `DuplicateJobNameError`로 바꾸고, service가 `JOB_NAME_DUPLICATED`로 바꾼다. service가 pymongo 예외에 의존하지 않게 하기 위함이다.
- **잘못된 ObjectId는 repository가 `None`으로 처리한다.** service는 "없음"과 같게 보고 `JOB_NOT_FOUND`를 던진다.

## 변경 파일
- `src/schemas/`: 없음(라우터 없음)
- `src/models/user_job.py` (신규)
  - `JobStatus(StrEnum)`: `pending` / `running` / `failed`
  - `JobResource`, `UserJob` Pydantic 모델(`UserJob.id`는 `str`)
  - `ALLOWED_RESOURCE_KINDS`: `{("apps/v1", "Deployment"), ("v1", "Service"), ("v1", "ConfigMap"), ("batch/v1", "Job")}`
  - `ALLOWED_STATUS_TRANSITIONS`: 이전 상태 → 허용되는 다음 상태
- `src/repository/user_job_repository.py` (신규): `UserJobRepository(collection: AsyncCollection)`
  - `ensure_indexes()`: 유니크 partial 인덱스 `(owner_id, name)`, 목록 인덱스 `(owner_id, created_at desc)`
  - `insert(job_doc) -> UserJob`: 유니크 위반이면 `DuplicateJobNameError`
  - `find_active_by_owner(owner_id) -> list[UserJob]`
  - `find_active_by_id(job_id) -> UserJob | None`: 잘못된 ObjectId·없음·삭제됨이면 `None`
  - `update_status_if(job_id, from_status, to_status, now) -> UserJob | None`: `status == from_status`이고 삭제되지 않았을 때만 `find_one_and_update`(갱신 후 문서 반환)
  - `soft_delete(owner_id, job_id, now) -> bool`: 자기 job이고 삭제되지 않았을 때만 갱신, 갱신 여부 반환
- `src/services/user_job_service.py` (신규): `UserJobService(repository)`. SPEC의 5개 메서드, 입력 검증(유저 ID·job 이름·매니페스트), 상태 전이 판단
- `src/services/k8s_service.py` (수정): `K8sService(api_client: ApiClient)`. 생성자에서 설정 로딩 제거
- `src/core/db/mongodb.py` (수정): `MongoClient` → `AsyncMongoClient(tz_aware=True)`. `get_database()`는 `AsyncDatabase` 반환
- `src/core/dependencies.py` (신규)
  - `get_k8s_service()`: `functools.cache`로 한 번만 생성. in-cluster → kubeconfig 순으로 설정을 읽어 `ApiClient` 생성
  - `get_user_job_repository()`, `get_user_job_service()`: `get_database()["user_jobs"]`로 조립
- `src/core/exception/my_exception.py` (수정): `INVALID_JOB_RESOURCE`, `JOB_NAME_DUPLICATED`, `INVALID_STATUS_TRANSITION`(모두 400), `JOB_NOT_FOUND`(404) 추가
- `src/main.py` (수정): `lifespan`에서 `get_user_job_repository().ensure_indexes()` 호출
- `tests/` (신규)
  - `tests/test_user_job_service.py`: 가짜 repository(메모리 dict, 유니크·조건부 갱신 흉내)를 주입해 SPEC의 정상·에러 케이스 확인
  - `tests/test_dependencies.py`: `get_k8s_service()`가 import 시점에 설정을 읽지 않고, 두 번 호출해도 같은 객체인지(`kubernetes.config`를 monkeypatch)
- 문서: `CLAUDE.md` "프로젝트 고유 구성"의 MongoDB 설명을 `AsyncMongoClient`·`dependencies.py` 기준으로 갱신

## DB 변경
- 컬렉션 `user_jobs` 신규
- 인덱스
  - `uniq_owner_name`: `{owner_id: 1, name: 1}`, `unique: true`, `partialFilterExpression: {is_deleted: false}`
  - `owner_created_at`: `{owner_id: 1, created_at: -1}`
- 기존 데이터 마이그레이션: 없음

## 외부 의존성
- 새 패키지 없음(`pymongo` 4.19의 `AsyncMongoClient`, `kubernetes` 사용)

## 리스크 / 확인할 것
- **repository는 실제 MongoDB로 테스트하지 않는다**(테스트 규칙). partial 유니크 인덱스와 조건부 갱신이 실제로 동작하는지는 로컬 MongoDB에 붙여 한 번 직접 확인하고 `implement.md`에 남긴다.
- **앱 시작에 MongoDB가 필요해진다.** lifespan의 `ensure_indexes()` 때문에 MongoDB 없이는 앱이 뜨지 않는다. 스모크 테스트는 `TestClient(app)`를 `with` 없이 써서 lifespan을 타지 않으므로 영향 없다.
- 기존 `get_client()`/`get_database()`의 반환 타입이 바뀐다. 아직 사용처가 없어 영향 없다.
