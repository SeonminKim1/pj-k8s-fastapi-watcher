from datetime import datetime
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field

from src.core.exception.my_exception import ErrorEnum
from src.core.exception.validation_error import error_code
from src.models.enums import JobStatus
from src.models.k8s_names import DnsLabel1035
from src.models.user_job import JobTemplate, UserJob


class JobCreateRequest(BaseModel):
    """POST /jobs body. 정의되지 않은 필드는 받지 않는다(400 invalid_parameter)."""

    model_config = ConfigDict(extra="forbid")

    name: Annotated[DnsLabel1035, error_code(ErrorEnum.INVALID_JOB_NAME)] = Field(
        description="job 이름. DNS-1035 label(영문 소문자로 시작, 소문자·숫자·'-', 영숫자로 끝, 1~63자). 유저별로 삭제되지 않은 job끼리 유일하며, 생성되는 Deployment·Service 이름으로 쓰인다"
    )
    template: JobTemplate = Field(
        description="type으로 구분하는 템플릿 입력. 지금은 web만 지원"
    )


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


# /docs·/redoc에 보여 줄 요청 body 예. 테스트가 JobCreateRequest로 검증한다.
JOB_CREATE_EXAMPLES: dict[str, dict[str, Any]] = {
    "minimal": {
        "summary": "필수 필드만 (replicas 1, env 없음, size small)",
        "value": {
            "name": "my-web",
            "template": {"type": "web", "image": "nginx:1.27", "port": 80},
        },
    },
    "full": {
        "summary": "모든 필드",
        "value": {
            "name": "my-api",
            "template": {
                "type": "web",
                "image": "ghcr.io/example/api:1.4.2",
                "port": 8080,
                "replicas": 2,
                "env": {"LOG_LEVEL": "info", "APP_MODE": "production"},
                "size": "medium",
            },
        },
    },
}

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
