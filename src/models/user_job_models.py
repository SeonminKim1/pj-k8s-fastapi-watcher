from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from src.core.exception.my_exception import ErrorEnum
from src.core.exception.validation_error import error_code
from src.models.enums import JobSize, JobStatus, JobType
from src.models.k8s_names import EnvName, ImageRef

# 유저 한 명이 가질 수 있는 삭제되지 않은 job 수(CLAUDE.md "유저별 job 개수 제한").
MAX_JOBS_PER_USER = 10

# job 목록 한 페이지의 기본 개수와 상한(docs/api-job-list/spec.md). schema와 service가 함께 쓴다.
# 상한을 바꾸면 ErrorEnum.INVALID_LIMIT 메시지(enum 값이라 상수로 만들 수 없음)도 함께 고친다.
JOB_LIST_DEFAULT_LIMIT = 20
JOB_LIST_MAX_LIMIT = 100


# 이전 상태 → 갈 수 있는 다음 상태. pending으로 돌아가는 전이는 없다.
ALLOWED_STATUS_TRANSITIONS: dict[JobStatus, frozenset[JobStatus]] = {
    JobStatus.PENDING: frozenset({JobStatus.RUNNING, JobStatus.FAILED}),
    JobStatus.RUNNING: frozenset({JobStatus.FAILED}),
    JobStatus.FAILED: frozenset({JobStatus.RUNNING}),
}


class WebTemplate(BaseModel):
    """web 타입 템플릿 입력: 상시 실행 서비스(Deployment + ClusterIP Service). 정의되지 않은 필드는 받지 않는다."""

    model_config = ConfigDict(extra="forbid")

    type: Literal[JobType.WEB] = Field(description="job 타입. web")
    image: Annotated[ImageRef, error_code(ErrorEnum.INVALID_IMAGE)]
    port: Annotated[int, error_code(ErrorEnum.INVALID_PORT)] = Field(
        ge=1,
        le=65535,
        strict=True,
        description="컨테이너 포트 1~65535. Service port도 같은 값",
    )
    replicas: Annotated[int, error_code(ErrorEnum.INVALID_REPLICAS)] = Field(
        default=1, ge=1, le=2, strict=True, description="레플리카 수 1~2. 기본 1"
    )
    env: Annotated[
        dict[EnvName, Annotated[str, Field(max_length=1024)]],
        error_code(ErrorEnum.INVALID_ENV),
    ] = Field(
        default_factory=dict,
        max_length=20,
        description="환경 변수(최대 20개, 값 1024자 이하). MongoDB에 평문으로 저장되므로 비밀값을 넣지 않는다",
    )
    size: Annotated[JobSize, error_code(ErrorEnum.INVALID_SIZE)] = Field(
        default=JobSize.SMALL,
        description="크기 프리셋(requests = limits). small: cpu 100m / memory 128Mi, medium: cpu 250m / memory 256Mi. 기본 small",
    )


# type으로 구분하는 템플릿 입력. 타입을 추가하면 Union에 넣는다(예: WebTemplate | DbTemplate).
JobTemplate = Annotated[WebTemplate, Field(discriminator="type")]


class JobResource(BaseModel):
    """job을 구성하는 리소스 하나. api_version·kind·name은 manifest에서 꺼낸 조회용 값이다."""

    api_version: str = Field(description="매니페스트의 apiVersion. 예: apps/v1")
    kind: str = Field(
        description="매니페스트의 kind. 템플릿 타입별 목록(services/job_templates.py의 KINDS_BY_TYPE) 중 하나"
    )
    name: str = Field(description="매니페스트의 metadata.name. web 템플릿은 job 이름")
    manifest: dict[str, Any] = Field(
        description="operator가 server-side apply할 매니페스트. 템플릿으로 서버가 생성한다"
    )


class UserJob(BaseModel):
    """user_jobs 컬렉션의 문서."""

    id: str = Field(description="MongoDB _id(ObjectId)의 문자열")
    owner_id: str = Field(
        description="소유자 유저 ID(X-User-Id 값). 소문자·숫자·'-', 영숫자로 시작·끝, 1~58자"
    )
    namespace: str = Field(
        description="소유자 네임스페이스 user-{owner_id}. 생성 시 서버가 정한다"
    )
    name: str = Field(
        description="유저가 정하는 job 이름. DNS-1035 label(영문 소문자로 시작, 1~63자), 삭제되지 않은 job끼리 유저별 유일. 생성되는 리소스 이름으로 쓰인다"
    )
    template: JobTemplate = Field(
        description="유저가 보낸 템플릿 입력(기본값이 채워진 상태)"
    )
    resources: list[JobResource] = Field(
        description="템플릿으로 서버가 생성한 리소스. 1개 이상, 모두 namespace에 속한다"
    )
    quota_slot: int = Field(
        description="개수 한도용 슬롯 번호 0~MAX_JOBS_PER_USER-1. 저장 시 서버가 빈 슬롯을 고른다"
    )
    status: JobStatus = Field(
        description="operator가 클러스터를 관찰해 갱신하는 상태. 생성 시 pending"
    )
    is_deleted: bool = Field(description="soft delete 여부")
    created_at: datetime = Field(description="생성 시각(UTC)")
    updated_at: datetime = Field(description="마지막 변경 시각(UTC)")
    deleted_at: datetime | None = Field(description="삭제 시각(UTC). 삭제 전에는 None")


class JobPosition(BaseModel):
    """목록 정렬(created_at 내림차순, 같으면 id 내림차순)에서의 위치. cursor가 가리키는 지점이다."""

    created_at: datetime = Field(description="위치를 정하는 job의 생성 시각(UTC)")
    id: str = Field(
        description="위치를 정하는 job의 ID(ObjectId 문자열). 같은 시각일 때 순서를 정한다"
    )


class JobPage(BaseModel):
    """job 목록 한 페이지."""

    items: list[UserJob] = Field(description="이번 페이지의 job. 최신순")
    next_cursor: str | None = Field(
        description="다음 페이지 cursor. 다음 페이지에 항목이 없으면 None"
    )
