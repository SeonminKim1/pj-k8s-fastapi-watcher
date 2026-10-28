# Domain: user-job
- **설명**: 유저가 만든 쿠버네티스 리소스 묶음을 job 하나로 저장·조회·상태 갱신·삭제하는 도메인 모델과 service, 그리고 service·repository·`K8sService`를 생성자로 주입하는 구조. HTTP API와 operator는 이 service를 주입받아 호출한다.

## 모델 (`user_jobs` 컬렉션)
| 필드 | 타입 | 설명 |
|---|---|---|
| `id` | `str` | MongoDB `_id`(ObjectId)의 문자열 |
| `owner_id` | `str` | 소유자 유저 ID(`X-User-Id` 값). `CLAUDE.md`의 유저 ID 형식(소문자·숫자·`-`, 영숫자로 시작·끝, 1~58자) |
| `namespace` | `str` | 소유자 네임스페이스 `user-{owner_id}`. 생성 시 서버가 정하며 입력받지 않는다 |
| `name` | `str` | 유저가 정하는 job 이름. DNS-1123 label(소문자·숫자·`-`, 영숫자로 시작·끝, 1~63자) |
| `resources` | `list[JobResource]` | 구성 리소스. 1개 이상. 모두 `namespace`에 속한다 |
| `status` | `JobStatus` | `pending` / `running` / `failed` |
| `is_deleted` | `bool` | soft delete 여부. 기본 `false` |
| `created_at` | `datetime` (UTC) | 생성 시각 |
| `updated_at` | `datetime` (UTC) | 마지막 변경 시각 |
| `deleted_at` | `datetime \| None` (UTC) | 삭제 시각. 삭제 전에는 `None` |

**JobResource**
| 필드 | 타입 | 설명 |
|---|---|---|
| `api_version` | `str` | 예: `apps/v1` |
| `kind` | `str` | 허용 목록 중 하나 |
| `name` | `str` | kind별 쿠버네티스 이름 규칙. `Service`는 DNS-1035 label(영문 소문자로 시작, 소문자·숫자·`-`, 영숫자로 끝, 1~63자), `Job`은 DNS-1123 label(1~63자, 이름이 Pod 라벨 `job-name` 값으로 복사됨), 나머지는 DNS-1123 subdomain(소문자·숫자·`-`·`.`, 1~253자) |
| `manifest` | `dict` | operator가 server-side apply할 매니페스트 원본 |

- `api_version`·`kind`·`name`은 `manifest`에서 꺼낸 값이며 조회·인덱싱용이다. 입력으로는 `manifest`만 받는다.
- `manifest.metadata.namespace`는 없거나 job의 `namespace`와 같아야 한다. 저장 시 job의 `namespace`로 채운다.
- 라벨(`managed-by`, `user-job-id`)은 저장하지 않는다. operator가 apply할 때 붙인다.

**허용 리소스 (apiVersion, kind)**: `apps/v1 Deployment`, `v1 Service`, `v1 ConfigMap`, `batch/v1 Job`
- `v1 Secret`은 매니페스트 원본(`data`)이 MongoDB에 평문으로 남기 때문에 제외한다. 필요해지면 암호화 방식과 함께 다시 정한다.

**인덱스**
- `(owner_id, name)` 유니크, `partialFilterExpression: {is_deleted: false}`. 삭제되지 않은 job끼리만 이름 중복을 막는다. 삭제된 job의 이름은 다시 쓸 수 있다.
- `(owner_id, created_at desc)`: 유저별 목록 조회용

## 상태
- 상태 값은 3개다. 삭제는 상태가 아니라 `is_deleted`로 표시한다(soft delete).
- 생성 시 `pending`. operator가 클러스터를 관찰해 바꾼다.
- 전이: `pending → running`, `pending → failed`, `running → failed`, `failed → running`(operator 재시도로 복구). `pending`으로 돌아가는 전이는 없다.
- 같은 상태로의 갱신은 아무것도 바꾸지 않고 성공으로 본다(이벤트 재전송·resync에 대한 멱등성).

## Service (`src/services/user_job_service.py`)
`UserJobService(repository: UserJobRepository)`. MongoDB 접근은 주입받은 repository로만 한다.

1. **`create_job(owner_id, name, manifests: list[dict]) -> UserJob`**
   1. `owner_id`가 유저 ID 형식이 아니거나 `name`이 DNS-1123 label이 아니면 `INVALID_PARAMETER`
   2. 매니페스트마다 다음 중 하나라도 해당하면 `INVALID_JOB_RESOURCE`
      - 목록이 비었음
      - `apiVersion`·`kind`·`metadata.name`이 없거나 형식이 틀림
      - (apiVersion, kind)가 허용 목록 밖
      - `metadata.namespace`가 job 네임스페이스와 다름
      - 같은 `(kind, name)`이 job 안에서 중복
   3. `namespace=user-{owner_id}`, `status=pending`, `is_deleted=false`, `created_at=updated_at=now`, `deleted_at=None`으로 저장
   4. 유니크 인덱스 위반(동시 요청 포함)이면 `JOB_NAME_DUPLICATED`
2. **`list_jobs(owner_id) -> list[UserJob]`**: `owner_id`가 유저 ID 형식이 아니면 `INVALID_PARAMETER`. 삭제되지 않은 자기 job을 `created_at` 내림차순으로 반환. 없으면 빈 목록
3. **`get_job(owner_id, job_id) -> UserJob`**: `owner_id` 형식 오류는 `INVALID_PARAMETER`. 자기 job이 아니거나, 없거나, 삭제됐거나, `job_id`가 ObjectId 형식이 아니면 모두 `JOB_NOT_FOUND`(다른 유저 job의 존재를 드러내지 않음)
4. **`update_job_status(job_id, status) -> UserJob`**: operator 전용이라 소유자 확인 없음
   1. 전이 표에서 목표 `status`로 갈 수 있는 이전 상태 목록을 구하고, "현재 상태가 그 목록 중 하나일 때만" 조건부 갱신(`status: {$in: [...]}`) 한 번으로 원자적으로 바꾸고 `updated_at` 갱신. 재시도하지 않는다
   2. 갱신되지 않았으면 다시 읽어 판단: job이 없거나 삭제됐으면 `JOB_NOT_FOUND`, 현재 상태와 같으면 변경 없이 그대로 반환(멱등), 그 외는 `INVALID_STATUS_TRANSITION`
5. **`delete_job(owner_id, job_id) -> None`**: `owner_id` 형식 오류는 `INVALID_PARAMETER`. `get_job`과 같은 조건이면 `JOB_NOT_FOUND`. 아니면 `is_deleted=true`, `deleted_at=updated_at=now`. 클러스터 리소스 정리는 operator가 한다

## 의존성 주입
- **`K8sService(api_client: ApiClient)`**: 생성자에서 kubeconfig를 읽지 않고, 받은 `ApiClient`로 `CoreV1Api`·`AppsV1Api` 등을 만든다. 이번 기능에서는 메서드를 추가하지 않는다.
- **`UserJobRepository(collection: Collection)`**: `user_jobs` 컬렉션을 받는다. 인덱스 생성 메서드(`ensure_indexes()`)를 가진다.
- **`src/core/dependencies.py`**: 실제 객체를 조립하는 유일한 곳
  - `get_k8s_service()`: 처음 호출할 때 in-cluster 설정 → 실패하면 kubeconfig를 읽어 `ApiClient`를 만들고, 이후 같은 객체를 반환. import 시점에는 클러스터에 접근하지 않는다.
  - `get_user_job_repository()`, `get_user_job_service()`: `get_database()`로 조립
  - FastAPI 라우터는 `Depends(get_user_job_service)`로 받고, 테스트는 `app.dependency_overrides` 또는 생성자 인자로 가짜 객체를 넣는다.
- 앱 시작(lifespan) 시 `get_k8s_service()`로 클러스터 설정을 먼저 읽고(설정이 없으면 앱 시작 실패), `ensure_indexes()`를 호출하고, 종료 시(시작 도중 실패 포함) `close_client()`로 MongoDB 연결을, `close_k8s_service()`로 K8s `ApiClient`를 닫는다.

## 에러 케이스
`CLAUDE.md`의 "에러 상태 코드" 규칙대로 비즈니스 에러는 400/404, 서버 내부 오류는 500(전역 핸들러)이다.

| 상황 | `ErrorEnum` (`code`) | 상태 코드 |
|---|---|---|
| owner_id 형식 오류(모든 owner_id 인자), job 이름 형식 오류 | `INVALID_PARAMETER` (`invalid_parameter`) | 400 |
| 매니페스트 없음·허용 목록 밖·형식 오류·네임스페이스 불일치·중복 | `INVALID_JOB_RESOURCE` (`invalid_job_resource`) | 400 |
| 삭제되지 않은 job 중 같은 이름 존재 | `JOB_NAME_DUPLICATED` (`job_name_duplicated`) | 400 |
| 허용되지 않는 상태 전이 | `INVALID_STATUS_TRANSITION` (`invalid_status_transition`) | 400 |
| job 없음·다른 유저 job·삭제됨·잘못된 ID | `JOB_NOT_FOUND` (`job_not_found`) | 404 |
| MongoDB 오류 | (전역 핸들러) `db_error` | 500 |

## 의존 리소스
- MongoDB `user_jobs` 컬렉션 (`src/core/db/mongodb.py`)
- `K8sService`: 주입 구조만 바꾸고 호출하지 않는다.

## 확인 필요
- **허용 리소스 목록**: 위 4종은 일반적인 웹 서비스 구성을 기준으로 정한 가정이다.
- **목록 페이지네이션**: 지금은 전체를 반환한다. 유저당 job이 많아지면 목록 API에서 정한다.
