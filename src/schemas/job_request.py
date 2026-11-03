from typing import Annotated, Any

from fastapi import Query, Request
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel, ConfigDict, Field

from src.core.exception.my_exception import ErrorEnum
from src.core.exception.validation_error import error_code
from src.models.enums import JobStatus
from src.models.k8s_names import DnsLabel1035
from src.models.user_job import (
    JOB_LIST_DEFAULT_LIMIT,
    JOB_LIST_MAX_LIMIT,
    JobTemplate,
)
from src.schemas.common_request import UserIdHeader

# /jobs 요청 schema. 응답은 job_response.py.


class JobCreateRequest(BaseModel):
    """POST /jobs body. 정의되지 않은 필드는 받지 않는다(400 invalid_parameter)."""

    model_config = ConfigDict(extra="forbid")

    name: Annotated[DnsLabel1035, error_code(ErrorEnum.INVALID_JOB_NAME)] = Field(
        description="job 이름. DNS-1035 label(영문 소문자로 시작, 소문자·숫자·'-', 영숫자로 끝, 1~63자). 유저별로 삭제되지 않은 job끼리 유일하며, 생성되는 Deployment·Service 이름으로 쓰인다"
    )
    template: JobTemplate = Field(
        description="type으로 구분하는 템플릿 입력. 지금은 web만 지원"
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


class JobListRequest(BaseModel):
    """GET /jobs 요청 값(헤더 + 쿼리). job_list_request()가 검증해서 만든다."""

    user_id: str = Field(description="X-User-Id 헤더의 유저 ID")
    limit: int = Field(description=f"한 페이지 최대 개수 1~{JOB_LIST_MAX_LIMIT}")
    cursor: str | None = Field(description="직전 응답의 next_cursor. 없으면 첫 페이지")
    status: JobStatus | None = Field(description="이 상태의 job만. 없으면 모든 상태")


# /docs·/redoc에 보여 줄 쿼리 예. cursor 예는 실제 encode_cursor 결과다(테스트가 디코딩되는지 확인한다).
JOB_LIST_CURSOR_EXAMPLE = (
    "MjAyNi0xMC0yOVQwOTowMDowMC4xMjMwMDArMDA6MDB8NjcyMGExYjJjM2Q0ZTVmNmE3YjhjOWQw"
)


# GET /jobs 쿼리 → 여러 번 지정됐을 때의 에러. 쿼리를 추가하면 여기에도 넣는다.
_JOB_LIST_QUERY_ERRORS: dict[str, ErrorEnum] = {
    "limit": ErrorEnum.INVALID_LIMIT,
    "cursor": ErrorEnum.INVALID_CURSOR,
    "status": ErrorEnum.INVALID_JOB_STATUS,
}


# GET /jobs의 헤더·쿼리를 검증해 JobListRequest로 만드는 dependency(docs/api-job-list/plan.md "status 중복 지정 검출").
# - FastAPI는 같은 쿼리가 여러 번 오면 조용히 마지막 값을 쓰므로, 쿼리가 두 번 이상이면 직접 그 필드의 검증 에러를 낸다.
#   중복 검사는 함수 본문에서 하므로 다른 형식 에러가 없을 때만 돈다(spec "요청 검증 에러").
# - 헤더를 엔드포인트가 아니라 여기서 받는 이유: FastAPI는 dependency를 엔드포인트 파라미터보다 먼저 실행한다.
#   헤더가 엔드포인트에 있으면 헤더가 틀려도 이 함수의 중복 에러가 먼저 나가 우선순위(헤더 먼저)가 깨진다.
#   여기 두면 헤더·limit·status 형식 에러가 있을 때 이 함수 본문이 실행되지 않고 함께 모여 우선순위대로 하나가 골라진다.
# - limit의 범위 제약(Field)은 error_code 앞에 둬야 범위 에러도 invalid_limit이 된다(Query에 두면 감싸지지 않는다).
def job_list_request(
    request: Request,
    user_id: UserIdHeader,
    limit: Annotated[
        int,
        Field(ge=1, le=JOB_LIST_MAX_LIMIT),
        error_code(ErrorEnum.INVALID_LIMIT),
        Query(
            description=f"한 페이지에 돌려줄 최대 개수. 1~{JOB_LIST_MAX_LIMIT}, 기본 {JOB_LIST_DEFAULT_LIMIT}",
            openapi_examples={
                "default": {"summary": "기본값", "value": JOB_LIST_DEFAULT_LIMIT}
            },
        ),
    ] = JOB_LIST_DEFAULT_LIMIT,
    cursor: Annotated[
        str | None,
        Query(
            description="직전 응답의 next_cursor를 그대로 보낸다. 없으면 첫 페이지. 형식은 불투명하다",
            openapi_examples={
                "first": {"summary": "첫 페이지(보내지 않음)", "value": None},
                "next": {"summary": "다음 페이지", "value": JOB_LIST_CURSOR_EXAMPLE},
            },
        ),
    ] = None,
    status: Annotated[
        JobStatus | None,
        error_code(ErrorEnum.INVALID_JOB_STATUS),
        Query(
            description="이 상태의 job만 돌려준다. 한 번만 지정할 수 있다. 없으면 모든 상태",
            openapi_examples={
                "all": {"summary": "모든 상태(보내지 않음)", "value": None},
                "running": {"summary": "running만", "value": "running"},
            },
        ),
    ] = None,
) -> JobListRequest:
    repeated = [
        {"type": error.code, "loc": ("query", name), "msg": error.message}
        for name, error in _JOB_LIST_QUERY_ERRORS.items()
        if len(request.query_params.getlist(name)) > 1
    ]
    if repeated:
        raise RequestValidationError(repeated)
    return JobListRequest(user_id=user_id, limit=limit, cursor=cursor, status=status)
