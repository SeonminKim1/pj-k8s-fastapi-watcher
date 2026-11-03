from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from src.models.enums import JobStatus
from src.models.user_job import JobPage, JobTemplate, UserJob

# /jobs 응답 schema. 요청은 job_request.py.


class JobResourceSummary(BaseModel):
    """서버가 만든 리소스 요약. 매니페스트 본문은 응답하지 않는다."""

    kind: str = Field(description="리소스 kind. 예: Deployment, Service")
    name: str = Field(description="리소스 이름")


class JobResponse(BaseModel):
    """job 응답. 소유자·삭제 정보·매니페스트 본문은 응답하지 않는다."""

    id: str = Field(description="job ID")
    name: str = Field(description="job 이름")
    namespace: str = Field(
        description="job 리소스가 만들어질 네임스페이스 user-{유저 ID}"
    )
    status: JobStatus = Field(
        description="operator가 클러스터를 관찰해 갱신하는 상태. 생성 직후에는 pending"
    )
    template: JobTemplate = Field(
        description="요청한 템플릿 입력(기본값이 채워진 상태)"
    )
    resources: list[JobResourceSummary] = Field(description="서버가 만든 리소스 요약")
    created_at: datetime = Field(description="생성 시각(UTC)")
    updated_at: datetime = Field(description="마지막 변경 시각(UTC)")

    # 도메인 모델(UserJob)에서 응답에 내보낼 필드만 골라 만든다.
    @classmethod
    def from_job(cls, job: UserJob) -> "JobResponse":
        return cls(
            id=job.id,
            name=job.name,
            namespace=job.namespace,
            status=job.status,
            template=job.template,
            resources=[
                JobResourceSummary(kind=r.kind, name=r.name) for r in job.resources
            ],
            created_at=job.created_at,
            updated_at=job.updated_at,
        )


# 201 응답 예("minimal" 요청의 결과). 테스트가 JobResponse로 검증한다.
JOB_RESPONSE_EXAMPLE: dict[str, Any] = {
    "id": "6720a1b2c3d4e5f6a7b8c9d0",
    "name": "my-web",
    "namespace": "user-alice",
    "status": "pending",
    "template": {
        "type": "web",
        "image": "nginx:1.27",
        "port": 80,
        "replicas": 1,
        "env": {},
        "size": "small",
    },
    "resources": [
        {"kind": "Deployment", "name": "my-web"},
        {"kind": "Service", "name": "my-web"},
    ],
    "created_at": "2026-10-29T09:00:00Z",
    "updated_at": "2026-10-29T09:00:00Z",
}


class JobSummary(BaseModel):
    """목록용 job 요약. 템플릿·리소스 등 상세는 담지 않는다."""

    id: str = Field(description="job ID")
    name: str = Field(description="job 이름")
    status: JobStatus = Field(
        description="operator가 마지막으로 기록한 상태(클러스터를 직접 조회하지 않는다)"
    )
    created_at: datetime = Field(description="생성 시각(UTC)")

    # 도메인 모델(UserJob)에서 요약 필드만 골라 만든다.
    @classmethod
    def from_job(cls, job: UserJob) -> "JobSummary":
        return cls(
            id=job.id, name=job.name, status=job.status, created_at=job.created_at
        )


class JobListResponse(BaseModel):
    """GET /jobs 응답. 목록을 객체로 감싸 이후 필드를 추가해도 호환되게 한다."""

    items: list[JobSummary] = Field(
        description="이번 페이지의 job. 최신순(created_at 내림차순, 같으면 id 내림차순). 없으면 []"
    )
    next_cursor: str | None = Field(
        description="다음 페이지가 있으면 그 cursor(다음 요청의 cursor 쿼리로 그대로 보낸다), 없으면 null"
    )

    # service의 JobPage를 응답 모양으로 바꾼다.
    @classmethod
    def from_page(cls, page: JobPage) -> "JobListResponse":
        return cls(
            items=[JobSummary.from_job(job) for job in page.items],
            next_cursor=page.next_cursor,
        )


# 200 응답 예(마지막 페이지). 테스트가 JobListResponse로 검증한다.
JOB_LIST_RESPONSE_EXAMPLE: dict[str, Any] = {
    "items": [
        {
            "id": "6720a1b2c3d4e5f6a7b8c9d1",
            "name": "api",
            "status": "running",
            "created_at": "2026-10-29T10:00:00Z",
        },
        {
            "id": "6720a1b2c3d4e5f6a7b8c9d0",
            "name": "my-web",
            "status": "pending",
            "created_at": "2026-10-29T09:00:00Z",
        },
    ],
    "next_cursor": None,
}
