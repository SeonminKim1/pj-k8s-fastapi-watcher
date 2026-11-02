from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field

from src.core.exception.my_exception import ErrorEnum
from src.core.exception.validation_error import error_code
from src.models.k8s_names import DnsLabel1035
from src.models.user_job import JobTemplate

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
