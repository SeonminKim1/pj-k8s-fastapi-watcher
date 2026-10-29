from collections.abc import Mapping, Sequence
from typing import Any

from src.core.exception.my_exception import ErrorEnum

# FastAPI 요청 검증 에러(RequestValidationError)를 ErrorEnum 하나로 바꾼다.
# 에러가 여러 개면 아래 우선순위에서 가장 앞선 하나만 쓴다(docs/api-job-create/spec.md "요청 검증 에러").

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

# 필드 위치(템플릿 타입 태그를 뺀 loc 앞부분) → 에러. 엔드포인트·필드가 늘면 여기에 추가한다.
_FIELD_ERRORS: dict[tuple[str, ...], ErrorEnum] = {
    ("header", "x-user-id"): ErrorEnum.INVALID_USER_ID,
    ("body", "name"): ErrorEnum.INVALID_JOB_NAME,
    ("body", "template", "image"): ErrorEnum.INVALID_IMAGE,
    ("body", "template", "port"): ErrorEnum.INVALID_PORT,
    ("body", "template", "replicas"): ErrorEnum.INVALID_REPLICAS,
    ("body", "template", "env"): ErrorEnum.INVALID_ENV,
    ("body", "template", "size"): ErrorEnum.INVALID_SIZE,
}

# 이 위치에서 값 자체가 없으면 필드 에러가 아니라 요청 형식 에러로 본다(spec: name·template 누락).
_MISSING_IS_FORMAT_ERROR = {("body", "name"), ("body", "template")}

# 위치와 상관없이 요청 형식 에러로 보는 pydantic 에러 종류.
_FORMAT_ERROR_TYPES = {"json_invalid", "extra_forbidden"}

# template 아래 loc에는 discriminated union의 타입 태그가 끼어 있다: ("body", "template", "web", "port")
_TEMPLATE_LOC = ("body", "template")
# template 바로 아래에 올 수 있는 필드 이름. loc의 세 번째 요소가 이 중 하나면 타입 태그가 없는 것이다.
_TEMPLATE_FIELDS = {"type"} | {
    key[2] for key in _FIELD_ERRORS if key[:2] == _TEMPLATE_LOC and len(key) == 3
}


# loc을 비교하기 쉬운 형태로 바꾼다: 문자열로, 헤더 이름은 소문자로, template 아래의 타입 태그는 뺀다.
# 타입 태그는 discriminated union일 때만 끼어 있으므로, 세 번째 요소가 필드 이름이면 그대로 둔다
# (union 구성이 바뀌어 태그가 사라져도 필드 에러가 invalid_parameter로 뭉개지지 않게).
def _normalize_loc(loc: Sequence[Any]) -> tuple[str, ...]:
    parts = tuple(str(p) for p in loc)
    if parts[:1] == ("header",):
        parts = tuple(p.lower() for p in parts)
    if (
        parts[:2] == _TEMPLATE_LOC
        and len(parts) >= 3
        and parts[2] not in _TEMPLATE_FIELDS
    ):
        parts = _TEMPLATE_LOC + parts[3:]
    return parts


# pydantic 에러 하나를 ErrorEnum으로 바꾼다. 표에 없는 위치는 요청 형식 에러.
def _classify(error: Mapping[str, Any]) -> ErrorEnum:
    loc = _normalize_loc(error.get("loc", ()))
    error_type = error.get("type")
    if error_type in _FORMAT_ERROR_TYPES:
        return ErrorEnum.INVALID_PARAMETER
    if error_type == "missing" and loc in _MISSING_IS_FORMAT_ERROR:
        return ErrorEnum.INVALID_PARAMETER
    if loc == _TEMPLATE_LOC:
        # type 누락·미지원은 union_tag_not_found/union_tag_invalid로 온다. 그 외(객체가 아님 등)는 형식 에러.
        if str(error_type).startswith("union_tag"):
            return ErrorEnum.INVALID_JOB_TYPE
        return ErrorEnum.INVALID_PARAMETER
    # 가장 긴 접두사부터 찾는다(env 아래 키 위치 같은 깊은 loc도 env 에러로).
    for end in range(len(loc), 1, -1):
        found = _FIELD_ERRORS.get(loc[:end])
        if found is not None:
            return found
    return ErrorEnum.INVALID_PARAMETER


# 검증 에러 목록에서 우선순위가 가장 높은 ErrorEnum 하나를 고른다. 목록이 비면 요청 형식 에러.
def to_error_enum(errors: Sequence[Mapping[str, Any]]) -> ErrorEnum:
    found = {_classify(e) for e in errors}
    for candidate in _PRIORITY:
        if candidate in found:
            return candidate
    return ErrorEnum.INVALID_PARAMETER
