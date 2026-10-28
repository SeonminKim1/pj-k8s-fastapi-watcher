from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel


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

    api_version: str
    kind: str
    name: str
    manifest: dict[str, Any]


class UserJob(BaseModel):
    """user_jobs 컬렉션의 문서. id는 MongoDB _id(ObjectId)의 문자열이다."""

    id: str
    owner_id: str
    namespace: str
    name: str
    resources: list[JobResource]
    status: JobStatus
    is_deleted: bool
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None
