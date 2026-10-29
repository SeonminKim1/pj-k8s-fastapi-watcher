from typing import Any

import pytest
from pydantic import BaseModel, TypeAdapter, ValidationError

from src.models.enums import JobSize
from src.models.k8s_names import (
    DnsLabel1035,
    UserId,
    is_dns_1035_label,
    is_pinned_image,
    is_user_id,
)
from src.models.user_job import JobTemplate, WebTemplate

template_adapter = TypeAdapter(JobTemplate)


# 필수 필드만 채운 web 템플릿 입력. 나머지는 인자로 덮어쓴다.
def web(**fields: Any) -> dict[str, Any]:
    return {"type": "web", "image": "nginx:1.27", "port": 80, **fields}


# 검증 실패한 첫 에러의 loc. 어느 필드에서 걸렸는지 확인할 때 쓴다.
def first_error_loc(data: dict[str, Any]) -> tuple[Any, ...]:
    with pytest.raises(ValidationError) as exc:
        template_adapter.validate_python(data)
    return exc.value.errors()[0]["loc"]


# 필수 필드만 보내면 기본값(replicas 1, env 빈 dict, size small)이 채워진다.
def test_web_template_defaults() -> None:
    t = template_adapter.validate_python(web())
    assert isinstance(t, WebTemplate)
    assert (t.replicas, t.env, t.size) == (1, {}, JobSize.SMALL)


def test_web_template_all_fields() -> None:
    t = template_adapter.validate_python(
        web(replicas=2, env={"MODE": "prod", "_X1": ""}, size="medium")
    )
    assert (t.replicas, t.env, t.size) == (
        2,
        {"MODE": "prod", "_X1": ""},
        JobSize.MEDIUM,
    )


@pytest.mark.parametrize(
    "image",
    [
        "nginx:1.27",
        "library/nginx:1.27-alpine",
        "ghcr.io/org/app:v1.0.0",
        "localhost:5000/app:dev_1",
        "registry.example.com:443/a/b/c:1",
        "nginx@sha256:" + "a" * 64,
        "nginx:1.27@sha256:" + "0" * 64,
        "nginx:latest@sha256:"
        + "0" * 64,  # digest가 이미지를 고정하므로 latest도 허용(리뷰 7)
        "my__app-x.y:1",
    ],
)
def test_image_ok(image: str) -> None:
    assert is_pinned_image(image)


@pytest.mark.parametrize(
    "image",
    [
        "nginx",  # 태그·digest 없음
        "nginx:latest",
        "ghcr.io/org/app",  # 레지스트리만 있고 태그 없음
        "localhost:5000/app",  # 포트를 태그로 착각하지 않는다
        "Nginx:1",  # 경로는 소문자만
        "nginx:1 ",  # 공백
        "nginx: 1",
        "nginx:-1",  # 태그는 '-'로 시작 불가
        "nginx@sha256:abc",  # digest 길이
        "",
        "a/" * 255 + "b:1",  # 512자 초과
        123,
    ],
)
def test_image_rejected(image: Any) -> None:
    assert not is_pinned_image(image)


# 경계값: 1, 65535는 통과, 0·65536·문자열·bool은 거절(strict라 "80"·true를 숫자로 바꾸지 않는다).
@pytest.mark.parametrize("port", [1, 65535])
def test_port_ok(port: int) -> None:
    assert template_adapter.validate_python(web(port=port)).port == port


@pytest.mark.parametrize("port", [0, 65536, -1, "80", True, 80.0])
def test_port_rejected(port: Any) -> None:
    assert first_error_loc(web(port=port)) == ("web", "port")


@pytest.mark.parametrize("replicas", [0, 3, "1", True])
def test_replicas_rejected(replicas: Any) -> None:
    assert first_error_loc(web(replicas=replicas)) == ("web", "replicas")


def test_env_max_20_ok() -> None:
    env = {f"K{i}": "v" for i in range(20)}
    assert len(template_adapter.validate_python(web(env=env)).env) == 20


@pytest.mark.parametrize(
    "env",
    [
        {f"K{i}": "v" for i in range(21)},  # 21개
        {"1ABC": "v"},  # 숫자로 시작
        {"A-B": "v"},
        {"A" * 64: "v"},  # 64자
        {"A": "x" * 1025},  # 값 1025자
        {"A": 1},  # 값이 문자열 아님
        ["A=1"],  # 객체 아님
    ],
)
def test_env_rejected(env: Any) -> None:
    assert first_error_loc(web(env=env))[:2] == ("web", "env")


def test_env_value_max_length_ok() -> None:
    assert template_adapter.validate_python(web(env={"A": "x" * 1024}))


def test_size_rejected() -> None:
    assert first_error_loc(web(size="large")) == ("web", "size")


def test_unknown_field_rejected() -> None:
    with pytest.raises(ValidationError) as exc:
        template_adapter.validate_python(web(resources={"cpu": "8"}))
    assert exc.value.errors()[0]["type"] == "extra_forbidden"


# type이 없거나 지원하지 않는 값이면 template 위치에서 걸린다(필드 검증 전에).
@pytest.mark.parametrize(
    ("data", "error_type"),
    [
        ({"image": "nginx:1.27", "port": 80}, "union_tag_not_found"),
        (web(type="db"), "union_tag_invalid"),
    ],
)
def test_type_rejected(data: dict[str, Any], error_type: str) -> None:
    with pytest.raises(ValidationError) as exc:
        template_adapter.validate_python(data)
    err = exc.value.errors()[0]
    assert (err["type"], err["loc"]) == (error_type, ())


class _Names(BaseModel):
    user_id: UserId
    job_name: DnsLabel1035


@pytest.mark.parametrize("value", ["a", "a" * 58, "user-1", "0abc"])
def test_user_id_ok(value: str) -> None:
    assert is_user_id(value)


@pytest.mark.parametrize("value", ["", "a" * 59, "-a", "a-", "A", "a_b", 1])
def test_user_id_rejected(value: Any) -> None:
    assert not is_user_id(value)


@pytest.mark.parametrize("value", ["a", "a" * 63, "my-web", "w1"])
def test_job_name_ok(value: str) -> None:
    assert is_dns_1035_label(value)


@pytest.mark.parametrize("value", ["", "a" * 64, "1web", "-a", "a-", "Web", "a.b"])
def test_job_name_rejected(value: str) -> None:
    assert not is_dns_1035_label(value)


# Annotated 타입이 is_* 함수와 같은 규칙으로 pydantic 검증을 한다.
def test_annotated_types_use_same_rules() -> None:
    assert _Names(user_id="alice", job_name="my-web")
    with pytest.raises(ValidationError) as exc:
        _Names(user_id="Alice", job_name="1web")
    assert [e["loc"] for e in exc.value.errors()] == [("user_id",), ("job_name",)]
