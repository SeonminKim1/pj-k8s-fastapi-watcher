# Domain: user-job
- **설명**: 유저가 만든 쿠버네티스 리소스 묶음을 job 하나로 저장·조회·상태 갱신·삭제하는 도메인 모델과 service, 그리고 service·repository·`K8sService`를 생성자로 주입하는 구조. 유저는 템플릿 입력(`CLAUDE.md`의 "job 입력은 템플릿 방식")만 보내고, 매니페스트는 서버가 생성한다. HTTP API와 operator는 이 service를 주입받아 호출한다.

## 모델 (`user_jobs` 컬렉션)
| 필드 | 타입 | 설명 |
|---|---|---|
| `id` | `str` | MongoDB `_id`(ObjectId)의 문자열 |
| `owner_id` | `str` | 소유자 유저 ID(`X-User-Id` 값). `CLAUDE.md`의 유저 ID 형식(소문자·숫자·`-`, 영숫자로 시작·끝, 1~58자) |
| `namespace` | `str` | 소유자 네임스페이스 `user-{owner_id}`. 생성 시 서버가 정하며 입력받지 않는다 |
| `name` | `str` | 유저가 정하는 job 이름. DNS-1035 label(영문 소문자로 시작, 소문자·숫자·`-`, 영숫자로 끝, 1~63자). 생성되는 Deployment·Service 이름으로 그대로 쓰인다 |
| `template` | `JobTemplate` | 유저가 보낸 템플릿 입력(기본값이 채워진 상태). 매니페스트를 다시 만들거나 보여줄 때 쓴다 |
| `resources` | `list[JobResource]` | 템플릿으로 서버가 생성한 리소스. 1개 이상. 모두 `namespace`에 속한다 |
| `status` | `JobStatus` | `pending` / `running` / `failed` |
| `quota_slot` | `int` | 개수 한도용 슬롯 번호 `0`~`9`. 생성 시 서버가 빈 슬롯을 골라 정한다. 응답하지 않는다 |
| `is_deleted` | `bool` | soft delete 여부. 기본 `false` |
| `created_at` | `datetime` (UTC) | 생성 시각 |
| `updated_at` | `datetime` (UTC) | 마지막 변경 시각 |
| `deleted_at` | `datetime \| None` (UTC) | 삭제 시각. 삭제 전에는 `None` |

**JobTemplate**: `type`으로 구분하는 템플릿 입력. 지금은 `WebTemplate` 하나다.

**WebTemplate** (`type: "web"`)
| 필드 | 타입 | 기본값 | 제약 |
|---|---|---|---|
| `type` | `"web"` | | |
| `image` | `str` | | 이미지 참조 `[레지스트리[:포트]/]경로(:태그 \| @sha256:digest \| :태그@sha256:digest)`, 1~512자, 공백 불가. 태그나 digest 필수, digest 없는 태그 `latest` 불가(`imagePullPolicy: IfNotPresent`라 노드마다 다른 이미지가 돌 수 있음) |
| `port` | `int` | | 1~65535 |
| `replicas` | `int` | `1` | 1~2 |
| `env` | `dict[str, str]` | `{}` | 최대 20개. 이름 `[A-Za-z_][A-Za-z0-9_]*`(1~63자), 값 0~1024자. MongoDB에 평문으로 저장되므로 비밀값을 넣지 않는다 |
| `size` | `"small" \| "medium"` | `"small"` | 크기 프리셋 |
- 정의되지 않은 필드는 받지 않는다(검증 에러).
- 타입을 추가할 때(예: `db`)는 `XxxTemplate`, 그 타입의 매니페스트 생성 함수, 그 타입이 만드는 kind 목록을 함께 추가한다. operator와 개수 한도·상태 전이는 타입과 무관하다.

**JobResource**
| 필드 | 타입 | 설명 |
|---|---|---|
| `api_version` | `str` | 예: `apps/v1` |
| `kind` | `str` | 허용 목록 중 하나 |
| `name` | `str` | 리소스 이름. `web` 템플릿은 job 이름 |
| `manifest` | `dict` | operator가 server-side apply할 매니페스트(서버가 생성) |

- 라벨 중 `managed-by`, `user-job-id`는 저장하지 않는다. operator가 apply할 때 붙인다.

**허용 리소스 (apiVersion, kind)**: 템플릿 타입마다 자기가 만드는 kind 목록을 가진다. 전체 허용 목록은 그 합이다.
- `web`: `apps/v1 Deployment`, `v1 Service`
- `v1 Secret`은 매니페스트(`data`)가 MongoDB에 평문으로 남기 때문에 제외한다.
- `v1 ConfigMap`, `batch/v1 Job`은 매니페스트 직접 입력을 없애면서 뺐다. 이를 쓰는 템플릿을 추가할 때 다시 넣는다.

**인덱스**
- `(owner_id, name)` 유니크, `partialFilterExpression: {is_deleted: false}`. 삭제되지 않은 job끼리만 이름 중복을 막는다. 삭제된 job의 이름은 다시 쓸 수 있다.
- `(owner_id, quota_slot)` 유니크, `partialFilterExpression: {is_deleted: false}`. 개수 한도(아래)를 동시 요청에서도 지킨다
- `(owner_id, created_at desc)`: 유저별 목록 조회용(cursor 페이지네이션에 맞춘 인덱스 조정은 `api-job-list`에서 정한다)

**기존 데이터**: `template` 필드가 없는 문서는 마이그레이션하지 않는다(운영 데이터 없음). 개발 DB에 남아 있으면 지운다.

## 템플릿 → 매니페스트 (`web`)
크기 프리셋(requests = limits): `small` = cpu `100m` / memory `128Mi`, `medium` = cpu `250m` / memory `256Mi`

**Deployment** (`apps/v1`)
- `metadata`: `name` = job 이름, `namespace` = job 네임스페이스, `labels` = `{app.kubernetes.io/name: <job 이름>}`
- `spec.replicas` = `replicas`, `spec.selector.matchLabels` = `{app.kubernetes.io/name: <job 이름>}`
- Pod template
  - `metadata.labels` = `{app.kubernetes.io/name: <job 이름>}`
  - `spec.automountServiceAccountToken: false`
  - `spec.securityContext.seccompProfile.type: RuntimeDefault`
  - 컨테이너 1개(`name: app`)
    - `image` = `image`, `imagePullPolicy: IfNotPresent`
    - `ports` = `[{containerPort: port, protocol: TCP}]`
    - `env` = `env`를 이름순으로 `[{name, value}]`
    - `resources.requests` = `resources.limits` = 크기 프리셋
    - `securityContext`: `privileged: false`, `allowPrivilegeEscalation: false`, `capabilities.drop: [ALL]` (root 실행은 허용)
    - `readinessProbe`: `tcpSocket.port` = `port`(나머지는 쿠버네티스 기본값). operator의 `running`이 "포트가 열려 응답 가능"을 뜻하게 한다. livenessProbe는 잘못 잡으면 재시작이 반복되므로 두지 않는다

**Service** (`v1`)
- `metadata`: Deployment와 같은 `name`·`namespace`·`labels`
- `spec.type: ClusterIP`, `spec.selector` = `{app.kubernetes.io/name: <job 이름>}`, `spec.ports` = `[{port: port, targetPort: port, protocol: TCP}]`

## 상태
- 상태 값은 3개다. 삭제는 상태가 아니라 `is_deleted`로 표시한다(soft delete).
- 생성 시 `pending`. operator가 클러스터를 관찰해 바꾼다.
- 전이: `pending → running`, `pending → failed`, `running → failed`, `failed → running`(operator 재시도로 복구). `pending`으로 돌아가는 전이는 없다.
- 같은 상태로의 갱신은 아무것도 바꾸지 않고 성공으로 본다(이벤트 재전송·resync에 대한 멱등성).

## 개수 한도
- 유저당 삭제되지 않은 job은 10개까지다(`CLAUDE.md`의 "유저별 job 개수 제한"). 동시 요청에서도 넘지 않는다.
- soft delete된 job은 개수에서 빠진다.
- 구현: 삭제되지 않은 job은 서로 다른 `quota_slot`(0~9)을 하나씩 차지한다(유니크 partial 인덱스). 생성 시 빈 슬롯을 골라 저장하고, 동시 요청과 슬롯이 겹치면 다시 골라 재시도한다. 빈 슬롯이 없으면 한도 초과다. soft delete하면 인덱스에서 빠져 슬롯이 비므로 별도로 개수를 되돌릴 필요가 없다.

## Service (`src/services/user_job_service.py`)
`UserJobService(repository: UserJobRepository)`. MongoDB 접근은 주입받은 repository로만 한다.

1. **`create_job(owner_id, name, template: JobTemplate) -> UserJob`**
   1. `owner_id`가 유저 ID 형식이 아니면 `INVALID_USER_ID`, `name`이 DNS-1035 label이 아니면 `INVALID_JOB_NAME`
   2. 템플릿으로 매니페스트를 생성한다(위 "템플릿 → 매니페스트"). `template`은 이미 검증된 모델이다
   3. `namespace=user-{owner_id}`, `status=pending`, `is_deleted=false`, `created_at=updated_at=now`, `deleted_at=None`, 빈 `quota_slot`으로 저장
   4. 빈 슬롯이 없으면 `JOB_QUOTA_EXCEEDED`
   5. 이름 유니크 인덱스 위반(동시 요청 포함)이면 `JOB_NAME_DUPLICATED`. 저장이 안 됐으므로 슬롯도 차지하지 않는다
2. **`list_jobs(owner_id, limit, cursor) -> (list[UserJob], next_cursor)`**: `owner_id`가 유저 ID 형식이 아니면 `INVALID_USER_ID`. 삭제되지 않은 자기 job을 최신순(`created_at` 내림차순, 같으면 `id` 내림차순)으로 `limit`개 반환한다. cursor 페이지네이션
   - `cursor`는 직전 페이지 마지막 항목을 가리키는 불투명 문자열. 없으면 첫 페이지. 다음 페이지가 없으면 `next_cursor=None`. 없으면 빈 목록
   - `limit`의 기본값·상한, cursor 인코딩, 잘못된 cursor의 에러는 `api-job-list`에서 정하고 그때 구현한다(현재 코드는 cursor 없이 전체 반환)
3. **`get_job(owner_id, job_id) -> UserJob`**: `owner_id` 형식 오류는 `INVALID_USER_ID`. 자기 job이 아니거나, 없거나, 삭제됐거나, `job_id`가 ObjectId 형식이 아니면 모두 `JOB_NOT_FOUND`(다른 유저 job의 존재를 드러내지 않음)
4. **`update_job_status(job_id, status) -> UserJob`**: operator 전용이라 소유자 확인 없음
   1. 전이 표에서 목표 `status`로 갈 수 있는 이전 상태 목록을 구하고, "현재 상태가 그 목록 중 하나일 때만" 조건부 갱신(`status: {$in: [...]}`) 한 번으로 원자적으로 바꾸고 `updated_at` 갱신. 재시도하지 않는다
   2. 갱신되지 않았으면 다시 읽어 판단: job이 없거나 삭제됐으면 `JOB_NOT_FOUND`, 현재 상태와 같으면 변경 없이 그대로 반환(멱등), 그 외는 `INVALID_STATUS_TRANSITION`
5. **`delete_job(owner_id, job_id) -> None`**: `owner_id` 형식 오류는 `INVALID_USER_ID`. `get_job`과 같은 조건이면 `JOB_NOT_FOUND`. 아니면 `is_deleted=true`, `deleted_at=updated_at=now`로 바꾼다(슬롯이 비어 개수에서 빠진다). 클러스터 리소스 정리는 operator가 한다

## 의존성 주입
- **`K8sService(api_client: ApiClient)`**: 생성자에서 kubeconfig를 읽지 않고, 받은 `ApiClient`로 `CoreV1Api`·`AppsV1Api` 등을 만든다.
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
| owner_id 형식 오류(모든 owner_id 인자) | `INVALID_USER_ID` (`invalid_user_id`) | 400 |
| job 이름 형식 오류 | `INVALID_JOB_NAME` (`invalid_job_name`) | 400 |
| 삭제되지 않은 job이 이미 10개 | `JOB_QUOTA_EXCEEDED` (`job_quota_exceeded`) | 400 |
| 삭제되지 않은 job 중 같은 이름 존재 | `JOB_NAME_DUPLICATED` (`job_name_duplicated`) | 400 |
| 허용되지 않는 상태 전이 | `INVALID_STATUS_TRANSITION` (`invalid_status_transition`) | 400 |
| job 없음·다른 유저 job·삭제됨·잘못된 ID | `JOB_NOT_FOUND` (`job_not_found`) | 404 |
| MongoDB 오류 | (전역 핸들러) `db_error` | 500 |

- 템플릿 필드 오류는 `WebTemplate` 모델 검증에서 걸린다. API에서는 필드별 400 에러(`invalid_job_type`, `invalid_image`, `invalid_port`, `invalid_replicas`, `invalid_env`, `invalid_size`)로 바뀐다(`docs/api-job-create/spec.md`).
- 매니페스트 직접 입력이 없어지면서 `INVALID_JOB_RESOURCE`(`invalid_job_resource`)는 쓰지 않는다.

## 의존 리소스
- MongoDB `user_jobs` 컬렉션 (`src/core/db/mongodb.py`)
- `K8sService`: 주입 구조만 두고 호출하지 않는다.

## operator에 넘기는 규칙
- **이름 재사용과 정리 순서**: job을 지운 직후 같은 이름으로 다시 만들면 옛 리소스가 아직 클러스터에 남아 있을 수 있다. operator는 apply 전에 같은 이름의 리소스가 다른 `user-job-id` 라벨을 갖고 있으면 apply하지 않고 다음 resync까지 미룬다(옛 job 정리를 기다림). API는 이를 위해 바뀌지 않는다. 상세는 `component-job-operator`에서 정한다.
