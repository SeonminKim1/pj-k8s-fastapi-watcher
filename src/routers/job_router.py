from typing import Annotated

from fastapi import APIRouter, Depends, Header

from src.core.dependencies import get_user_job_service
from src.models.k8s_names import UserId
from src.schemas.error import ErrorResponse
from src.schemas.job import JobCreateRequest, JobResponse
from src.services.user_job_service import UserJobService

router = APIRouter(prefix="/jobs", tags=["jobs"])

# 게이트웨이가 넣어 주는 유저 ID 헤더. 형식이 틀리거나 없으면 400 invalid_user_id.
UserIdHeader = Annotated[UserId, Header(alias="X-User-Id")]


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
