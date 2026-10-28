from datetime import datetime
from enum import StrEnum
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from src.models.k8s_names import EnvName, ImageRef

# 유저 한 명이 가질 수 있는 삭제되지 않은 job 수(CLAUDE.md "유저별 job 개수 제한").
MAX_JOBS_PER_USER = 10


class JobStatus(StrEnum):
    """operator가 클러스터를 관찰해 갱신하는 job 상태. 삭제는 상태가 아니라 is_deleted로 표시한다."""

    PENDING = "pending"
    RUNNING = "running"
    FAILED = "failed"


# 이전 상태 → 갈 수 있는 다음 상태. pending으로 돌아가는 전이는 없다.
ALLOWED_STATUS_TRANSITIONS: dict[JobStatus, frozenset[JobStatus]] = {
    JobStatus.PENDING: frozenset({JobStatus.RUNNING, JobStatus.FAILED}),
    JobStatus.RUNNING: frozenset({JobStatus.FAILED}),
    JobStatus.FAILED: frozenset({JobStatus.RUNNING}),
}


class JobSize(StrEnum):
    """컨테이너 크기 프리셋. 실제 cpu·memory 값은 매니페스트를 만들 때 정한다."""

    SMALL = "small"
    MEDIUM = "medium"


class WebTemplate(BaseModel):
    """web 타입 템플릿 입력: 상시 실행 서비스(Deployment + ClusterIP Service). 정의되지 않은 필드는 받지 않는다."""

    model_config = ConfigDict(extra="forbid")

    type: Literal["web"] = Field(description="job 타입. web")
    image: ImageRef
    port: int = Field(
        ge=1,
        le=65535,
        strict=True,
        description="컨테이너 포트 1~65535. Service port도 같은 값",
    )
    replicas: int = Field(
        default=1, ge=1, le=2, strict=True, description="레플리카 수 1~2. 기본 1"
    )
    env: dict[EnvName, Annotated[str, Field(max_length=1024)]] = Field(
        default_factory=dict,
        max_length=20,
        description="환경 변수(최대 20개, 값 1024자 이하). MongoDB에 평문으로 저장되므로 비밀값을 넣지 않는다",
    )
    size: JobSize = Field(
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
