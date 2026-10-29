from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from src.models.enums import JobStatus
from src.models.k8s_names import DnsLabel1035
from src.models.user_job import JobTemplate, UserJob


class JobCreateRequest(BaseModel):
    """POST /jobs body. 정의되지 않은 필드는 받지 않는다(400 invalid_parameter)."""

    model_config = ConfigDict(extra="forbid")

    name: DnsLabel1035 = Field(
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
