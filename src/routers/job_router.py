from typing import Annotated

from fastapi import APIRouter, Depends

from src.core.dependencies import get_user_job_service
from src.schemas.common import UserIdHeader
from src.schemas.error import ErrorResponse
from src.schemas.job import JobCreateRequest, JobResponse
from src.services.user_job_service import UserJobService

router = APIRouter(prefix="/jobs", tags=["jobs"])


# job을 등록한다. MongoDB에 pending으로 저장만 하고 바로 응답한다(클러스터 반영은 operator).
@router.post(
    "",
    status_code=201,
    response_model=JobResponse,
    responses={400: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
)
async def create_job(
    body: JobCreateRequest,
    user_id: UserIdHeader,
    service: Annotated[UserJobService, Depends(get_user_job_service)],
) -> JobResponse:
    job = await service.create_job(user_id, body.name, body.template)
    return JobResponse.from_job(job)
