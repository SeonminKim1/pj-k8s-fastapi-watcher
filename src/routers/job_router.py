from typing import Annotated

from fastapi import APIRouter, Body, Depends

from src.core.dependencies import get_user_job_service
from src.schemas.common_request import UserIdHeader
from src.schemas.error_response import COMMON_ERROR_RESPONSES
from src.schemas.job_request import (
    JOB_CREATE_EXAMPLES,
    JobCreateRequest,
    JobListRequest,
    job_list_request,
)
from src.schemas.job_response import (
    JOB_LIST_RESPONSE_EXAMPLE,
    JOB_RESPONSE_EXAMPLE,
    JobListResponse,
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
    job = await service.create_job(
        owner_id=user_id, name=body.name, template=body.template
    )
    return JobResponse.from_job(job)


# 삭제되지 않은 자기 job의 요약을 최신순으로 돌려준다. cursor 페이지네이션, status 필터. MongoDB만 읽는다.
@router.get(
    "",
    response_model=JobListResponse,
    description='에러 code: `docs/api-job-list/spec.md` "에러 케이스"',
    responses={
        200: {"content": {"application/json": {"example": JOB_LIST_RESPONSE_EXAMPLE}}}
    },
)
async def list_jobs(
    query: Annotated[JobListRequest, Depends(job_list_request)],
    service: Annotated[UserJobService, Depends(get_user_job_service)],
) -> JobListResponse:
    page = await service.list_jobs(
        owner_id=query.user_id,
        limit=query.limit,
        cursor=query.cursor,
        status=query.status,
    )
    return JobListResponse.from_page(page)
