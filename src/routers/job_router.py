from typing import Annotated

from fastapi import APIRouter, Body, Depends

from src.core.dependencies import get_user_job_service
from src.core.exception.my_exception import ErrorEnum
from src.schemas.common import UserIdHeader
from src.schemas.error import error_responses
from src.schemas.job import (
    JOB_CREATE_EXAMPLES,
    JOB_RESPONSE_EXAMPLE,
    JobCreateRequest,
    JobResponse,
)
from src.services.user_job_service import UserJobService

router = APIRouter(prefix="/jobs", tags=["jobs"])


# job을 등록한다. MongoDB에 pending으로 저장만 하고 바로 응답한다(클러스터 반영은 operator).
@router.post(
    "",
    status_code=201,
    response_model=JobResponse,
    responses={
        201: {"content": {"application/json": {"example": JOB_RESPONSE_EXAMPLE}}},
        **error_responses(
            # 요청 검증 에러(우선순위 순)
            ErrorEnum.INVALID_USER_ID,
            ErrorEnum.INVALID_PARAMETER,
            ErrorEnum.INVALID_JOB_NAME,
            ErrorEnum.INVALID_JOB_TYPE,
            ErrorEnum.INVALID_IMAGE,
            ErrorEnum.INVALID_PORT,
            ErrorEnum.INVALID_REPLICAS,
            ErrorEnum.INVALID_ENV,
            ErrorEnum.INVALID_SIZE,
            # 비즈니스 에러
            ErrorEnum.JOB_QUOTA_EXCEEDED,
            ErrorEnum.JOB_NAME_DUPLICATED,
        ),
    },
)
async def create_job(
    body: Annotated[JobCreateRequest, Body(openapi_examples=JOB_CREATE_EXAMPLES)],
    user_id: UserIdHeader,
    service: Annotated[UserJobService, Depends(get_user_job_service)],
) -> JobResponse:
    job = await service.create_job(user_id, body.name, body.template)
    return JobResponse.from_job(job)
