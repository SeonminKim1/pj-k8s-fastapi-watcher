from collections.abc import Callable, Mapping, Sequence
from typing import Any

from pydantic import ValidationError, WrapValidator
from pydantic_core import PydanticCustomError

from src.core.exception.my_exception import ErrorEnum

# FastAPI 요청 검증 에러(RequestValidationError)를 ErrorEnum 하나로 바꾼다.
# 필드가 error_code()로 자기 에러를 직접 내므로, 여기서는 에러 종류(type)만 보고 우선순위로 하나를 고른다
# (docs/api-job-create/spec.md "요청 검증 에러").

# 우선순위: 앞에 있을수록 먼저 알려준다.
_PRIORITY: tuple[ErrorEnum, ...] = (
    ErrorEnum.INVALID_USER_ID,
    ErrorEnum.INVALID_PARAMETER,
    ErrorEnum.INVALID_JOB_NAME,
    ErrorEnum.INVALID_JOB_TYPE,
    ErrorEnum.INVALID_IMAGE,
    ErrorEnum.INVALID_PORT,
    ErrorEnum.INVALID_REPLICAS,
    ErrorEnum.INVALID_ENV,
    ErrorEnum.INVALID_SIZE,
)

_BY_CODE: dict[str, ErrorEnum] = {e.code: e for e in ErrorEnum}

# 값이 아예 없으면(missing) 필드 검증기가 돌지 않으므로, 필드 에러로 알려야 하는 필수 필드만 이름으로 구분한다.
# 여기 없는 필드(name·template 등)의 누락은 요청 형식 에러다(spec "요청 검증 에러").
_MISSING_ERRORS: dict[str, ErrorEnum] = {
    "x-user-id": ErrorEnum.INVALID_USER_ID,
    "image": ErrorEnum.INVALID_IMAGE,
    "port": ErrorEnum.INVALID_PORT,
}


# 필드 타입에 붙이는 검증기: 그 필드의 검증(형식·범위·개수 등)이 하나라도 실패하면 에러 종류를 ErrorEnum code로 바꾼다.
# 예: port: Annotated[int, error_code(ErrorEnum.INVALID_PORT)] = Field(ge=1, ...)
# 값이 아예 없으면(missing) 필드 검증이 돌지 않으므로 pydantic 기본 에러가 그대로 남는다.
def error_code(error: ErrorEnum) -> WrapValidator:
    def validate(value: Any, handler: Callable[[Any], Any]) -> Any:
        try:
            return handler(value)
        except ValidationError:
            raise PydanticCustomError(error.code, error.message) from None

    return WrapValidator(validate)


# pydantic 에러 하나를 ErrorEnum으로 바꾼다.
def _classify(error: Mapping[str, Any]) -> ErrorEnum:
    error_type = str(error.get("type"))
    # error_code()를 붙인 필드의 에러
    if error_type in _BY_CODE:
        return _BY_CODE[error_type]
    # template.type 누락(union_tag_not_found)·미지원(union_tag_invalid)
    if error_type.startswith("union_tag"):
        return ErrorEnum.INVALID_JOB_TYPE
    # 필수 필드 누락. FastAPI는 헤더 이름을 소문자로 넣지만 대소문자와 상관없이 비교한다.
    loc = error.get("loc") or ("",)
    if error_type == "missing":
        found = _MISSING_ERRORS.get(str(loc[-1]).lower())
        if found is not None:
            return found
    # 그 외(body 필드 누락, 정의되지 않은 필드, JSON 아님, 객체 아님 등)는 요청 형식 에러
    return ErrorEnum.INVALID_PARAMETER


# 검증 에러 목록에서 우선순위가 가장 높은 ErrorEnum 하나를 고른다. 목록이 비면 요청 형식 에러.
def to_error_enum(errors: Sequence[Mapping[str, Any]]) -> ErrorEnum:
    found = {_classify(e) for e in errors}
    for candidate in _PRIORITY:
        if candidate in found:
            return candidate
    return ErrorEnum.INVALID_PARAMETER
