# API: job 생성
- **Method & Path**: `POST /jobs`
- **설명**: 유저가 job 이름과 템플릿 입력(`template.type`과 그 타입이 허용하는 필드)으로 job을 등록한다. 서버가 매니페스트를 생성해 `pending` 상태로 MongoDB에 저장하고 바로 응답한다. 클러스터에는 쓰지 않는다(operator가 반영).

## Request (schema)
**header**
| 필드 | 타입 | 필수 | 제약 |
|---|---|---|---|
| `X-User-Id` | `str` | O | `CLAUDE.md` 유저 ID 형식(소문자·숫자·`-`, 영숫자로 시작·끝, 1~58자) |

**body** (`application/json`)
| 필드 | 타입 | 필수 | 기본값 | 제약 |
|---|---|---|---|---|
| `name` | `str` | O | | DNS-1035 label: 영문 소문자로 시작, 소문자·숫자·`-`, 영숫자로 끝, 1~63자. Deployment·Service 이름으로 그대로 쓰인다 |
| `template` | `JobTemplate` | O | | `type`으로 구분하는 템플릿 입력. 지금은 `web`만 |

**`template` (`type: "web"`)**
| 필드 | 타입 | 필수 | 기본값 | 제약 |
|---|---|---|---|---|
| `type` | `"web"` | O | | |
| `image` | `str` | O | | 이미지 참조 `[레지스트리[:포트]/]경로(:태그 \| @sha256:digest \| :태그@sha256:digest)`, 1~512자, 공백 불가. 태그나 digest가 꼭 있어야 하며 digest 없이 태그 `latest`만 있으면 안 된다(digest가 있으면 이미지가 고정되므로 허용) |
| `port` | `int` | O | | 컨테이너 포트 1~65535. Service port도 같은 값 |
| `replicas` | `int` | X | `1` | 1~2 |
| `env` | `dict[str, str]` | X | `{}` | 최대 20개. 이름 `[A-Za-z_][A-Za-z0-9_]*`(1~63자), 값 0~1024자. MongoDB에 평문으로 저장되므로 비밀값을 넣지 않는다(`/docs` 필드 설명에 명시) |
| `size` | `"small" \| "medium"` | X | `"small"` | 크기 프리셋(아래 표) |

- body·`template`에 위 표에 없는 필드가 있으면 400(유저가 고정 값을 바꾸려는 시도를 조용히 무시하지 않는다).
- 요청 예:
  ```json
  {
    "name": "my-web",
    "template": {"type": "web", "image": "nginx:1.27", "port": 80,
                 "replicas": 2, "env": {"MODE": "prod"}, "size": "small"}
  }
  ```

**크기 프리셋** (requests = limits)
| size | cpu | memory |
|---|---|---|
| `small` | `100m` | `128Mi` |
| `medium` | `250m` | `256Mi` |

## Response (schema)
`201 Created`, body `JobResponse`:
| 필드 | 타입 | 설명 |
|---|---|---|
| `id` | `str` | job ID |
| `name` | `str` | job 이름 |
| `namespace` | `str` | `user-{유저 ID}` |
| `status` | `"pending" \| "running" \| "failed"` | 생성 직후에는 항상 `pending` |
| `template` | `JobTemplate` | 요청의 `template`과 같은 모양. 기본값이 채워진 상태 |
| `resources` | `list[{kind: str, name: str}]` | 서버가 만든 리소스 요약. 매니페스트 본문은 응답하지 않는다 |
| `created_at` | `datetime` (UTC, ISO 8601) | 생성 시각 |
| `updated_at` | `datetime` (UTC, ISO 8601) | 마지막 변경 시각 |

- `owner_id`, `is_deleted`, `deleted_at`, 매니페스트 본문은 응답하지 않는다. 필드는 나중에 추가할 수 있지만 빼기는 어려우므로 최소로 시작한다.
- 에러 응답은 기존과 같은 `{code, message}`.
- `/docs`(OpenAPI)에는 실제로 돌려주는 `201`·`400`·`500`만 문서화한다. 검증 에러를 400으로 바꿔 응답하므로 FastAPI가 자동으로 넣는 `422`는 문서에서 뺀다.

## 생성되는 매니페스트 (`web`)
`docs/domain-user-job/spec.md`의 "템플릿 → 매니페스트"를 따른다. 요약: Deployment 1개 + Service 1개(ClusterIP), 이름은 job 이름, 리소스·보안 설정·readinessProbe는 서버 고정.

## 비즈니스 로직 단계
1. router: `X-User-Id` 헤더와 body를 schema로 파싱한다. 검증에 실패하면 `RequestValidationError` → 전역 핸들러가 첫 번째 에러 하나를 아래 "요청 검증 에러"의 `ErrorEnum`으로 바꿔 400으로 응답한다.
2. router가 `UserJobService.create_job(owner_id, name, template)`을 호출한다.
3. service(`docs/domain-user-job/spec.md`의 `create_job`):
   1. `owner_id`·`name` 형식 확인(schema를 거치지 않는 호출자 대비) → `INVALID_USER_ID`·`INVALID_JOB_NAME`
   2. 템플릿으로 매니페스트 생성
   3. 빈 개수 슬롯(유저당 10개)을 골라 `pending` 상태로 저장. 동시 요청에서도 10개를 넘지 않는다. 빈 슬롯이 없으면 `JOB_QUOTA_EXCEEDED`
   4. 이름이 중복이면 `JOB_NAME_DUPLICATED`(저장되지 않으므로 슬롯도 차지하지 않는다)
4. router가 저장된 job을 `JobResponse`로 바꿔 201로 응답한다.

- 검사 순서: 요청 형식 → 개수 한도 → 이름 중복. 개수가 꽉 찬 유저가 중복 이름을 보내면 `job_quota_exceeded`.
- 멱등성: 같은 요청을 다시 보내면 이름 중복으로 400. 별도 멱등성 키는 없다.

## 에러 케이스
에러 응답은 `{code, message}` 하나다. 요청에 틀린 곳이 여러 개면 아래 표의 위에서부터 **첫 번째 하나만** 알려준다. `message`는 `ErrorEnum`에 고정된 문장으로, 무엇이 왜 틀렸는지(허용 범위)를 담는다.

**요청 검증 에러** (전역 `RequestValidationError` 핸들러, 모두 400)
| 우선순위 | 상황 | `ErrorEnum` (`code`) | message 예 |
|---|---|---|---|
| 1 | `X-User-Id` 없음·형식 오류 | `INVALID_USER_ID` (`invalid_user_id`) | 유저 ID는 소문자·숫자·'-'로 된 1~58자여야 합니다. |
| 2 | body가 JSON이 아님·객체가 아님, `name`·`template` 누락, 정의되지 않은 필드 | `INVALID_PARAMETER` (`invalid_parameter`) | 요청 형식이 올바르지 않습니다. |
| 3 | `name` 형식 오류 | `INVALID_JOB_NAME` (`invalid_job_name`) | job 이름은 영문 소문자로 시작하는 1~63자(소문자·숫자·'-')여야 합니다. |
| 4 | `template.type` 누락·지원하지 않는 값 | `INVALID_JOB_TYPE` (`invalid_job_type`) | 지원하지 않는 job 타입입니다. (지원: web) |
| 5 | `template.image` 누락·형식 오류·태그 없음·digest 없는 `latest` | `INVALID_IMAGE` (`invalid_image`) | 이미지는 태그나 digest를 포함해야 하며, digest 없이 latest 태그는 쓸 수 없습니다. |
| 6 | `template.port` 누락·정수 아님·범위 밖 | `INVALID_PORT` (`invalid_port`) | port는 1~65535 사이의 정수여야 합니다. |
| 7 | `template.replicas` 정수 아님·범위 밖 | `INVALID_REPLICAS` (`invalid_replicas`) | replicas는 1~2 사이의 정수여야 합니다. |
| 8 | `template.env` 객체 아님·20개 초과·이름 형식·값 길이 | `INVALID_ENV` (`invalid_env`) | env는 최대 20개, 이름은 [A-Za-z_][A-Za-z0-9_]*, 값은 1024자 이하여야 합니다. |
| 9 | `template.size` 지원하지 않는 값 | `INVALID_SIZE` (`invalid_size`) | size는 small, medium 중 하나여야 합니다. |

- `template` 안의 정의되지 않은 필드는 2(`invalid_parameter`)로 본다.

**비즈니스 에러** (service)
| 상황 | `ErrorEnum` (`code`) | 상태 코드 |
|---|---|---|
| 삭제되지 않은 job이 이미 10개 | `JOB_QUOTA_EXCEEDED` (`job_quota_exceeded`) | 400 |
| 삭제되지 않은 job 중 같은 이름 존재(동시 요청 포함) | `JOB_NAME_DUPLICATED` (`job_name_duplicated`) | 400 |

**서버 오류** (전역 핸들러)
| 상황 | `code` | 상태 코드 |
|---|---|---|
| MongoDB 오류 | `db_error` | 500 |
| 그 외 예외 | `unknown_error` | 500 |

## 의존 리소스
- `UserJobService` (`Depends(get_user_job_service)`)
- MongoDB `user_jobs` 컬렉션(개수 한도는 `quota_slot` 유니크 인덱스, `docs/domain-user-job/spec.md`)
- 클러스터: 사용하지 않음. 유저 네임스페이스가 없어도 성공한다(네임스페이스 생성은 operator).

## 확인 필요
- **이미지 레지스트리 제한**: 형식만 검사하고 어느 레지스트리든 허용한다. 사내 레지스트리만 허용해야 하면 서비스 전체 규칙으로 `CLAUDE.md`에 추가한다.
- **비밀값**: env에 비밀값을 넣지 말라고 안내만 한다. 비밀값 저장 방식은 비밀번호가 필요한 템플릿(`db` 등)을 추가할 때 함께 정한다.
