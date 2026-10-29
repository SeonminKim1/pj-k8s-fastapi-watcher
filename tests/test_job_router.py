from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Any

import pytest
from fastapi.testclient import TestClient

from src.core.dependencies import get_user_job_service
from src.core.exception.my_exception import ErrorEnum, MyApiError
from src.main import app
from src.models.enums import JobStatus
from src.models.user_job import UserJob, WebTemplate
from src.schemas.job import JOB_CREATE_EXAMPLES, JOB_RESPONSE_EXAMPLE, JobResponse
from src.services.job_templates import build_resources

# lifespan을 타지 않도록 with 없이 쓴다(클러스터·MongoDB 불필요).
client = TestClient(app)

HEADERS = {"X-User-Id": "alice"}


class FakeUserJobService:
    """create_job 호출을 기록하고, error가 있으면 그 비즈니스 에러를 던진다."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, str, WebTemplate]] = []
        self.error: ErrorEnum | None = None

    async def create_job(
        self, owner_id: str, name: str, template: WebTemplate
    ) -> UserJob:
        self.calls.append((owner_id, name, template))
        if self.error is not None:
            raise MyApiError(self.error)
        namespace = f"user-{owner_id}"
        now = datetime(2026, 10, 28, tzinfo=UTC)
        return UserJob(
            id="0" * 24,
            owner_id=owner_id,
            namespace=namespace,
            name=name,
            template=template,
            resources=build_resources(name, namespace, template),
            quota_slot=0,
            status=JobStatus.PENDING,
            is_deleted=False,
            created_at=now,
            updated_at=now,
            deleted_at=None,
        )


@pytest.fixture
def service() -> Iterator[FakeUserJobService]:
    fake = FakeUserJobService()
    app.dependency_overrides[get_user_job_service] = lambda: fake
    yield fake
    app.dependency_overrides.clear()


def web(**fields: Any) -> dict[str, Any]:
    return {"type": "web", "image": "nginx:1.27", "port": 80, **fields}


def body(**fields: Any) -> dict[str, Any]:
    return {"name": "my-web", "template": web(), **fields}


# 정상: 201, 응답 필드는 spec의 JobResponse뿐(owner_id·quota_slot·매니페스트 본문 없음)
def test_create_job_201(service: FakeUserJobService) -> None:
    r = client.post("/jobs", headers=HEADERS, json=body(template=web(replicas=2)))
    assert r.status_code == 201
    data = r.json()
    assert set(data) == {
        "id",
        "name",
        "namespace",
        "status",
        "template",
        "resources",
        "created_at",
        "updated_at",
    }
    assert data["name"] == "my-web"
    assert data["namespace"] == "user-alice"
    assert data["status"] == "pending"
    assert data["template"] == {
        "type": "web",
        "image": "nginx:1.27",
        "port": 80,
        "replicas": 2,
        "env": {},
        "size": "small",
    }
    assert data["resources"] == [
        {"kind": "Deployment", "name": "my-web"},
        {"kind": "Service", "name": "my-web"},
    ]
    assert data["created_at"] == "2026-10-28T00:00:00Z"


# 헤더의 유저 ID, body의 name·template이 그대로 service로 간다
def test_create_job_passes_input(service: FakeUserJobService) -> None:
    client.post("/jobs", headers=HEADERS, json=body())
    [(owner_id, name, template)] = service.calls
    assert (owner_id, name) == ("alice", "my-web")
    assert template == WebTemplate(type="web", image="nginx:1.27", port=80)


def assert_error(r: Any, expected: ErrorEnum) -> None:
    assert r.status_code == expected.status_code
    assert r.json() == {"code": expected.code, "message": expected.message}


# spec "요청 검증 에러" 표의 행마다. 검증에서 걸리면 service를 부르지 않는다.
@pytest.mark.parametrize(
    ("headers", "payload", "expected"),
    [
        ({}, body(), ErrorEnum.INVALID_USER_ID),
        ({"X-User-Id": "Alice"}, body(), ErrorEnum.INVALID_USER_ID),
        ({"X-User-Id": "a" * 59}, body(), ErrorEnum.INVALID_USER_ID),
        (HEADERS, [body()], ErrorEnum.INVALID_PARAMETER),  # 객체 아님
        (HEADERS, {"template": web()}, ErrorEnum.INVALID_PARAMETER),  # name 누락
        (HEADERS, {"name": "my-web"}, ErrorEnum.INVALID_PARAMETER),  # template 누락
        (HEADERS, body(owner_id="bob"), ErrorEnum.INVALID_PARAMETER),  # 정의 안 된 필드
        (
            HEADERS,
            body(template=web(securityContext={"privileged": True})),
            ErrorEnum.INVALID_PARAMETER,
        ),
        (HEADERS, body(name="1web"), ErrorEnum.INVALID_JOB_NAME),
        (HEADERS, body(name="a" * 64), ErrorEnum.INVALID_JOB_NAME),
        (
            HEADERS,
            body(template={"image": "nginx:1.27", "port": 80}),
            ErrorEnum.INVALID_JOB_TYPE,
        ),
        (HEADERS, body(template=web(type="db")), ErrorEnum.INVALID_JOB_TYPE),
        (HEADERS, body(template=web(image="nginx")), ErrorEnum.INVALID_IMAGE),
        (
            HEADERS,
            body(template={"type": "web", "port": 80}),
            ErrorEnum.INVALID_IMAGE,
        ),  # image 누락
        (
            HEADERS,
            body(template={"type": "web", "image": "nginx:1.27"}),
            ErrorEnum.INVALID_PORT,
        ),  # port 누락
        (HEADERS, body(template=web(image="nginx:latest")), ErrorEnum.INVALID_IMAGE),
        (HEADERS, body(template=web(port=65536)), ErrorEnum.INVALID_PORT),
        (HEADERS, body(template=web(port="80")), ErrorEnum.INVALID_PORT),
        (HEADERS, body(template=web(replicas=3)), ErrorEnum.INVALID_REPLICAS),
        (HEADERS, body(template=web(env={"A-B": "v"})), ErrorEnum.INVALID_ENV),
        (
            HEADERS,
            body(template=web(env={f"K{i}": "v" for i in range(21)})),
            ErrorEnum.INVALID_ENV,
        ),
        (HEADERS, body(template=web(size="large")), ErrorEnum.INVALID_SIZE),
    ],
)
def test_validation_errors(
    service: FakeUserJobService,
    headers: dict[str, str],
    payload: Any,
    expected: ErrorEnum,
) -> None:
    r = client.post("/jobs", headers=headers, json=payload)
    assert_error(r, expected)
    assert service.calls == []


# body가 JSON이 아니면 요청 형식 에러
def test_invalid_json(service: FakeUserJobService) -> None:
    r = client.post(
        "/jobs",
        headers={**HEADERS, "Content-Type": "application/json"},
        content="{not json",
    )
    assert_error(r, ErrorEnum.INVALID_PARAMETER)


# JSON 파싱이 실패하면 FastAPI가 헤더 검증을 건너뛰지만, 헤더가 없거나 틀리면 여전히 invalid_user_id가 먼저(리뷰 1)
@pytest.mark.parametrize("headers", [{}, {"X-User-Id": "Bad_User"}])
def test_invalid_json_without_valid_header(
    service: FakeUserJobService, headers: dict[str, str]
) -> None:
    r = client.post(
        "/jobs",
        headers={**headers, "Content-Type": "application/json"},
        content="notjson",
    )
    assert_error(r, ErrorEnum.INVALID_USER_ID)


# 여러 개가 틀리면 우선순위가 가장 높은 하나만: 헤더 > 형식 > name > template 필드 순
@pytest.mark.parametrize(
    ("headers", "payload", "expected"),
    [
        ({}, body(name="1web", unknown=1), ErrorEnum.INVALID_USER_ID),
        (HEADERS, body(name="1web", unknown=1), ErrorEnum.INVALID_PARAMETER),
        (HEADERS, body(name="1web", template=web(port=0)), ErrorEnum.INVALID_JOB_NAME),
        (
            HEADERS,
            body(template=web(image="x", port=0, size="xl")),
            ErrorEnum.INVALID_IMAGE,
        ),
    ],
)
def test_validation_error_priority(
    service: FakeUserJobService,
    headers: dict[str, str],
    payload: Any,
    expected: ErrorEnum,
) -> None:
    assert_error(client.post("/jobs", headers=headers, json=payload), expected)


# service의 비즈니스 에러는 ErrorEnum 상태 코드·code 그대로
@pytest.mark.parametrize(
    "error", [ErrorEnum.JOB_QUOTA_EXCEEDED, ErrorEnum.JOB_NAME_DUPLICATED]
)
def test_business_errors(service: FakeUserJobService, error: ErrorEnum) -> None:
    service.error = error
    assert_error(client.post("/jobs", headers=HEADERS, json=body()), error)


# /docs 스키마: POST /jobs가 201·400을 문서화하고, 헤더 이름이 X-User-Id다
def test_openapi_create_job() -> None:
    op = client.get("/openapi.json").json()["paths"]["/jobs"]["post"]
    assert {"201", "400"} <= set(op["responses"])
    assert [p["name"] for p in op["parameters"]] == ["X-User-Id"]


# /docs·/redoc의 example: 요청 example은 실제로 201이 나고, 201 example은 JobResponse 모양이다.
@pytest.mark.parametrize("name", list(JOB_CREATE_EXAMPLES))
def test_openapi_request_examples_are_valid(
    service: FakeUserJobService, name: str
) -> None:
    payload = JOB_CREATE_EXAMPLES[name]["value"]
    assert client.post("/jobs", headers=HEADERS, json=payload).status_code == 201


def test_openapi_response_example_is_valid(service: FakeUserJobService) -> None:
    example = JobResponse.model_validate(JOB_RESPONSE_EXAMPLE)
    # "minimal" 요청의 결과와 id·시각을 뺀 나머지가 같다
    r = client.post(
        "/jobs", headers=HEADERS, json=JOB_CREATE_EXAMPLES["minimal"]["value"]
    )
    ignore = {"id", "created_at", "updated_at"}
    assert example.model_dump(mode="json", exclude=ignore) == {
        k: v for k, v in r.json().items() if k not in ignore
    }


# 에러 example은 code마다 하나이고, 이 엔드포인트가 낼 수 있는 에러를 모두 담는다.
def test_openapi_error_examples() -> None:
    responses = client.get("/openapi.json").json()["paths"]["/jobs"]["post"][
        "responses"
    ]

    def examples(status: str) -> dict[str, Any]:
        return responses[status]["content"]["application/json"]["examples"]

    expected_400 = [
        ErrorEnum.INVALID_USER_ID,
        ErrorEnum.INVALID_PARAMETER,
        ErrorEnum.INVALID_JOB_NAME,
        ErrorEnum.INVALID_JOB_TYPE,
        ErrorEnum.INVALID_IMAGE,
        ErrorEnum.INVALID_PORT,
        ErrorEnum.INVALID_REPLICAS,
        ErrorEnum.INVALID_ENV,
        ErrorEnum.INVALID_SIZE,
        ErrorEnum.JOB_QUOTA_EXCEEDED,
        ErrorEnum.JOB_NAME_DUPLICATED,
    ]
    assert {k: v["value"] for k, v in examples("400").items()} == {
        e.code: {"code": e.code, "message": e.message} for e in expected_400
    }
    assert set(examples("500")) == {"db_error", "unknown_error"}
    assert "example" in responses["201"]["content"]["application/json"]
