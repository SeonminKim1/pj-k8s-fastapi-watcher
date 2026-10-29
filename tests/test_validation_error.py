from typing import Annotated, Any

import pytest
from pydantic import BaseModel, Field, ValidationError

from src.core.exception.my_exception import ErrorEnum
from src.core.exception.validation_error import error_code, to_error_enum
from src.schemas.job import JobCreateRequest


# body를 검증해 FastAPI처럼 loc 앞에 "body"를 붙인 에러 목록을 만든다.
def body_errors(body: Any) -> list[dict[str, Any]]:
    with pytest.raises(ValidationError) as exc:
        JobCreateRequest.model_validate(body)
    return [{**e, "loc": ("body", *e["loc"])} for e in exc.value.errors()]


def web(**fields: Any) -> dict[str, Any]:
    return {"type": "web", "image": "nginx:1.27", "port": 80, **fields}


def body(name: Any = "my-web", template: Any = None, **extra: Any) -> dict[str, Any]:
    return {"name": name, "template": web() if template is None else template, **extra}


# spec "요청 검증 에러" 표의 행마다 하나씩
@pytest.mark.parametrize(
    ("data", "expected"),
    [
        ({"template": web()}, ErrorEnum.INVALID_PARAMETER),  # name 누락
        ({"name": "my-web"}, ErrorEnum.INVALID_PARAMETER),  # template 누락
        (body(extra_field=1), ErrorEnum.INVALID_PARAMETER),  # 정의되지 않은 body 필드
        (body(template=web(resources={})), ErrorEnum.INVALID_PARAMETER),  # template 안
        (body(template="web"), ErrorEnum.INVALID_PARAMETER),  # template이 객체 아님
        (body(name="1web"), ErrorEnum.INVALID_JOB_NAME),
        (body(name=123), ErrorEnum.INVALID_JOB_NAME),
        (
            body(template={"image": "nginx:1.27", "port": 80}),
            ErrorEnum.INVALID_JOB_TYPE,
        ),
        (body(template=web(type="db")), ErrorEnum.INVALID_JOB_TYPE),
        (body(template=web(image="nginx:latest")), ErrorEnum.INVALID_IMAGE),
        (body(template={"type": "web", "port": 80}), ErrorEnum.INVALID_IMAGE),  # 누락
        (body(template=web(port=0)), ErrorEnum.INVALID_PORT),
        (body(template={"type": "web", "image": "nginx:1"}), ErrorEnum.INVALID_PORT),
        (body(template=web(replicas=3)), ErrorEnum.INVALID_REPLICAS),
        (body(template=web(env={"1A": "v"})), ErrorEnum.INVALID_ENV),  # 키 위치 에러
        (body(template=web(env={"A": "x" * 1025})), ErrorEnum.INVALID_ENV),  # 값 위치
        (body(template=web(env="A=1")), ErrorEnum.INVALID_ENV),
        (body(template=web(size="large")), ErrorEnum.INVALID_SIZE),
    ],
)
def test_body_error_mapping(data: dict[str, Any], expected: ErrorEnum) -> None:
    assert to_error_enum(body_errors(data)) == expected


# 여러 개가 틀리면 표의 위쪽(우선순위가 높은) 에러 하나만
@pytest.mark.parametrize(
    ("data", "expected"),
    [
        (body(name="1web", template=web(port=0)), ErrorEnum.INVALID_JOB_NAME),
        (body(name="1web", unknown=1), ErrorEnum.INVALID_PARAMETER),
        (body(template=web(size="large", image="x", port=0)), ErrorEnum.INVALID_IMAGE),
        (body(template=web(env={"1A": "v"}, replicas=9)), ErrorEnum.INVALID_REPLICAS),
    ],
)
def test_priority(data: dict[str, Any], expected: ErrorEnum) -> None:
    assert to_error_enum(body_errors(data)) == expected


# 헤더 에러는 가장 먼저. FastAPI는 헤더 이름을 소문자로 넣지만 대소문자와 상관없이 매칭한다.
@pytest.mark.parametrize("header", ["x-user-id", "X-User-Id"])
def test_header_error_first(header: str) -> None:
    errors = [
        {"type": "missing", "loc": ("header", header)},
        *body_errors(body(name="1web")),
    ]
    assert to_error_enum(errors) == ErrorEnum.INVALID_USER_ID


# body 자체가 JSON이 아니거나 없거나 객체가 아니면 요청 형식 에러
@pytest.mark.parametrize(
    "error",
    [
        {"type": "json_invalid", "loc": ("body", 1)},
        {"type": "missing", "loc": ("body",)},
        {"type": "model_attributes_type", "loc": ("body",)},
    ],
)
def test_body_format_errors(error: dict[str, Any]) -> None:
    assert to_error_enum([error]) == ErrorEnum.INVALID_PARAMETER


# error_code(): 필드 검증이 어떤 이유로 실패하든 지정한 code 하나로 바뀐다. 값이 없으면 기본 missing 그대로.
class _Port(BaseModel):
    port: Annotated[int, error_code(ErrorEnum.INVALID_PORT)] = Field(ge=1, strict=True)


@pytest.mark.parametrize(
    ("data", "expected_type"),
    [({"port": 0}, "invalid_port"), ({"port": "80"}, "invalid_port"), ({}, "missing")],
)
def test_error_code(data: dict[str, Any], expected_type: str) -> None:
    with pytest.raises(ValidationError) as exc:
        _Port.model_validate(data)
    [error] = exc.value.errors()
    assert error["type"] == expected_type
    if expected_type == "invalid_port":
        assert error["msg"] == ErrorEnum.INVALID_PORT.message


def test_empty_errors() -> None:
    assert to_error_enum([]) == ErrorEnum.INVALID_PARAMETER
