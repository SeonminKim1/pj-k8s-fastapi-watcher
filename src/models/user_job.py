from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class JobStatus(StrEnum):
    """operator가 클러스터를 관찰해 갱신하는 job 상태. 삭제는 상태가 아니라 is_deleted로 표시한다."""

    PENDING = "pending"
    RUNNING = "running"
    FAILED = "failed"


# job을 구성할 수 있는 (apiVersion, kind). Secret은 매니페스트가 평문으로 저장되므로 제외한다.
ALLOWED_RESOURCE_KINDS: frozenset[tuple[str, str]] = frozenset(
    {
        ("apps/v1", "Deployment"),
        ("v1", "Service"),
        ("v1", "ConfigMap"),
        ("batch/v1", "Job"),
    }
)

# 이전 상태 → 갈 수 있는 다음 상태. pending으로 돌아가는 전이는 없다.
ALLOWED_STATUS_TRANSITIONS: dict[JobStatus, frozenset[JobStatus]] = {
    JobStatus.PENDING: frozenset({JobStatus.RUNNING, JobStatus.FAILED}),
    JobStatus.RUNNING: frozenset({JobStatus.FAILED}),
    JobStatus.FAILED: frozenset({JobStatus.RUNNING}),
}


class JobResource(BaseModel):
    """job을 구성하는 리소스 하나. api_version·kind·name은 manifest에서 꺼낸 조회용 값이다."""

    api_version: str = Field(description="매니페스트의 apiVersion. 예: apps/v1")
    kind: str = Field(description="매니페스트의 kind. ALLOWED_RESOURCE_KINDS 중 하나")
    name: str = Field(
        description="매니페스트의 metadata.name. DNS-1123 subdomain(1~253자)"
    )
    manifest: dict[str, Any] = Field(
        description="operator가 server-side apply할 매니페스트 원본. metadata.namespace는 job 네임스페이스로 채워진다"
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
        description="유저가 정하는 job 이름. DNS-1123 label(1~63자), 삭제되지 않은 job끼리 유저별 유일"
    )
    resources: list[JobResource] = Field(
        description="구성 리소스. 1개 이상, 모두 namespace에 속한다"
    )
    status: JobStatus = Field(
        description="operator가 클러스터를 관찰해 갱신하는 상태. 생성 시 pending"
    )
    is_deleted: bool = Field(description="soft delete 여부")
    created_at: datetime = Field(description="생성 시각(UTC)")
    updated_at: datetime = Field(description="마지막 변경 시각(UTC)")
    deleted_at: datetime | None = Field(description="삭제 시각(UTC). 삭제 전에는 None")
