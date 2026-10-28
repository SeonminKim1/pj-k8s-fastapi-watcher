from enum import Enum


class ErrorEnum(Enum):
    """비즈니스 에러 종류별로 (코드, HTTP 상태 코드, 메시지)를 한 번에 정의한다."""

    INVALID_PARAMETER = ("invalid_parameter", 400, "요청 형식이 올바르지 않습니다.")
    INVALID_USER_ID = (
        "invalid_user_id",
        400,
        "유저 ID는 소문자·숫자·'-'로 된 1~58자여야 합니다.",
    )
    INVALID_JOB_NAME = (
        "invalid_job_name",
        400,
        "job 이름은 영문 소문자로 시작하는 1~63자(소문자·숫자·'-')여야 합니다.",
    )
    INVALID_JOB_TYPE = (
        "invalid_job_type",
        400,
        "지원하지 않는 job 타입입니다. (지원: web)",
    )
    INVALID_IMAGE = (
        "invalid_image",
        400,
        "이미지는 태그나 digest를 포함해야 하며 latest 태그는 쓸 수 없습니다.",
    )
    INVALID_PORT = ("invalid_port", 400, "port는 1~65535 사이의 정수여야 합니다.")
    INVALID_REPLICAS = (
        "invalid_replicas",
        400,
        "replicas는 1~2 사이의 정수여야 합니다.",
    )
    INVALID_ENV = (
        "invalid_env",
        400,
        "env는 최대 20개, 이름은 [A-Za-z_][A-Za-z0-9_]*, 값은 1024자 이하여야 합니다.",
    )
    INVALID_SIZE = ("invalid_size", 400, "size는 small, medium 중 하나여야 합니다.")
    JOB_QUOTA_EXCEEDED = (
        "job_quota_exceeded",
        400,
        "job은 유저당 10개까지 만들 수 있습니다.",
    )
    INVALID_JOB_RESOURCE = (
        "invalid_job_resource",
        400,
        "job 리소스 매니페스트가 유효하지 않습니다.",
    )
    JOB_NAME_DUPLICATED = (
        "job_name_duplicated",
        400,
        "같은 이름의 job이 이미 있습니다.",
    )
    INVALID_STATUS_TRANSITION = (
        "invalid_status_transition",
        400,
        "허용되지 않는 job 상태 변경입니다.",
    )
    JOB_NOT_FOUND = ("job_not_found", 404, "job을 찾을 수 없습니다.")

    def __init__(self, code: str, status_code: int, message: str) -> None:
        self.code = code
        self.status_code = status_code
        self.message = message


class MyApiError(Exception):
    """services에서 발생시키는 모든 비즈니스 에러는 이 예외로 감싸서 던진다."""

    def __init__(self, error_enum: ErrorEnum) -> None:
        self.error_enum = error_enum
        super().__init__(error_enum.message)
