# 데이터 모델: job 생성 API

모델 전체는 `specs/001-domain-user-job/data-model.md`가 기준이다. 이 기능에서 바꾼 것만 적는다.

## UserJob (`user_jobs`, `src/models/user_job_models.py`) — 변경
| 필드 | 타입 | 필수 | 제약·검증 | 누가 정하나 |
|---|---|---|---|---|
| `template` (추가) | `JobTemplate` | O | `WebTemplate`(아래). 기본값이 채워진 상태로 저장 | 유저 |
| `quota_slot` (추가) | `int` | O | `0`~`MAX_JOBS_PER_USER - 1`. 응답하지 않는다 | 서버 |
| `name` (규칙 변경) | `str` | O | DNS-1123 label → DNS-1035 label(Service 이름으로 그대로 쓰이므로) | 유저 |
| `resources` (생성 방식 변경) | `list[JobResource]` | O | 유저 입력이 아니라 `build_resources()`가 생성 | 서버 |

- **인덱스·유니크 제약**: `uniq_owner_slot` `{owner_id: 1, quota_slot: 1}` 유니크, partial `{is_deleted: false}` 추가
- **관계**: 변경 없음

## WebTemplate (`type: "web"`, `extra="forbid"`) — 신규
| 필드 | 타입 | 필수 | 제약·검증 (에러) | 누가 정하나 |
|---|---|---|---|---|
| `type` | `"web"` | O | 판별자 (`invalid_job_type`) | 유저 |
| `image` | `str` | O | 태그·digest 필수, digest 없는 `latest` 불가, 1~512자 (`invalid_image`) | 유저 |
| `port` | `int` | O | 1~65535 (`invalid_port`) | 유저 |
| `replicas` | `int` | X(기본 1) | 1~2 (`invalid_replicas`) | 유저 |
| `env` | `dict[str, str]` | X(기본 `{}`) | 최대 20개, 이름 `[A-Za-z_][A-Za-z0-9_]*` 1~63자, 값 0~1024자 (`invalid_env`) | 유저 |
| `size` | `JobSize` | X(기본 `small`) | `small`/`medium` (`invalid_size`) | 유저 |

## 비즈니스 규칙
- 개수 한도 `MAX_JOBS_PER_USER = 10`(`src/models/user_job_models.py`). 슬롯 방식은 [research.md](research.md).
- 매니페스트의 고정 값(크기 프리셋, 보안 설정, 라벨, probe)은 `src/services/job_templates.py`가 정의한다(`specs/001-domain-user-job/data-model.md` "템플릿 → 매니페스트").
- 기존 데이터: `template`이 없는 문서는 마이그레이션하지 않고 지운다(운영 데이터 없음).
