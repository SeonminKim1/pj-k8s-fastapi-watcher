from typing import Annotated

from fastapi import APIRouter, Body, Depends

from src.core.dependencies import get_user_job_service
from src.schemas.common import UserIdHeader
from src.schemas.error import COMMON_ERROR_RESPONSES
from src.schemas.job import (
    JOB_CREATE_EXAMPLES,
    JOB_RESPONSE_EXAMPLE,
    JobCreateRequest,
    JobResponse,
)
from src.services.user_job_service import UserJobService

router = APIRouter(prefix="/jobs", tags=["jobs"], responses=COMMON_ERROR_RESPONSES)


# job을 등록한다. MongoDB에 pending으로 저장만 하고 바로 응답한다(클러스터 반영은 operator).
@router.post(
    "",
    status_code=201,
    response_model=JobResponse,
    description='에러 code: `docs/api-job-create/spec.md` "에러 케이스"',
    responses={
        201: {"content": {"application/json": {"example": JOB_RESPONSE_EXAMPLE}}}
    },
)
async def create_job(
    body: Annotated[JobCreateRequest, Body(openapi_examples=JOB_CREATE_EXAMPLES)],
    user_id: UserIdHeader,
    service: Annotated[UserJobService, Depends(get_user_job_service)],
) -> JobResponse:
    job = await service.create_job(user_id, body.name, body.template)
    return JobResponse.from_job(job)
