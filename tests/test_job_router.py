from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Any

import pytest
from fastapi.testclient import TestClient

from src.core.dependencies import get_user_job_service
from src.core.exception.my_exception import ErrorEnum, MyApiError
from src.main import app
from src.models.enums import JobStatus
from src.models.user_job_models import JobPage, UserJob, WebTemplate
from src.schemas.job_request import JOB_CREATE_EXAMPLES, JOB_LIST_CURSOR_EXAMPLE
from src.schemas.job_response import (
    JOB_LIST_RESPONSE_EXAMPLE,
    JOB_RESPONSE_EXAMPLE,
    JobListResponse,
    JobResponse,
)
from src.services.job_cursor import decode_cursor
from src.services.job_templates import build_resources

# lifespan을 타지 않도록 with 없이 쓴다(클러스터·MongoDB 불필요).
client = TestClient(app)

HEADERS = {"X-User-Id": "alice"}


class FakeUserJobService:
    """create_job·list_jobs 호출을 기록하고, error가 있으면 그 비즈니스 에러를 던진다."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, str, WebTemplate]] = []
        self.list_calls: list[tuple[str, int, str | None, JobStatus | None]] = []
        self.page = JobPage(items=[], next_cursor=None)
        self.error: ErrorEnum | None = None

    async def list_jobs(
        self, owner_id: str, limit: int, cursor: str | None, status: JobStatus | None
    ) -> JobPage:
        self.list_calls.append((owner_id, limit, cursor, status))
        if self.error is not None:
            raise MyApiError(self.error)
        return self.page

    async def create_job(
        self, owner_id: str, name: str, template: WebTemplate
    ) -> UserJob:
        self.calls.append((owner_id, name, template))
        if self.error is not None:
            raise MyApiError(self.error)
        return make_job(owner_id=owner_id, name=name, template=template)


# 응답 변환을 확인할 수 있게 실제 모양을 갖춘 UserJob을 만든다.
def make_job(
    owner_id: str = "alice",
    name: str = "my-web",
    template: WebTemplate | None = None,
    status: JobStatus = JobStatus.PENDING,
    job_id: str = "0" * 24,
) -> UserJob:
    template = template or WebTemplate(type="web", image="nginx:1.27", port=80)
    namespace = f"user-{owner_id}"
    now = datetime(2026, 10, 28, tzinfo=UTC)
    return UserJob(
        id=job_id,
        owner_id=owner_id,
        namespace=namespace,
        name=name,
        template=template,
        resources=build_resources(name=name, namespace=namespace, template=template),
        quota_slot=0,
        status=status,
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


# 400·500은 라우터 공통 선언: ErrorResponse 모양과 대표 example. code 목록은 spec을 가리킨다.
def test_openapi_error_responses() -> None:
    op = client.get("/openapi.json").json()["paths"]["/jobs"]["post"]
    for status in ("400", "500"):
        content = op["responses"][status]["content"]["application/json"]
        assert content["schema"] == {"$ref": "#/components/schemas/ErrorResponse"}
        assert set(content["example"]) == {"code", "message"}
    assert "specs/002-api-job-create/contracts/post-jobs.md" in op["description"]
    assert "example" in op["responses"]["201"]["content"]["application/json"]


# --- GET /jobs (specs/003-api-job-list/contracts/get-jobs.md) ---


# 정상: 200, 항목은 요약 필드(id·name·status·created_at)뿐, next_cursor 그대로
def test_list_jobs_200(service: FakeUserJobService) -> None:
    service.page = JobPage(
        items=[make_job(name="api", status=JobStatus.RUNNING, job_id="1" * 24)],
        next_cursor="next",
    )
    r = client.get("/jobs", headers=HEADERS)
    assert r.status_code == 200
    assert r.json() == {
        "items": [
            {
                "id": "1" * 24,
                "name": "api",
                "status": "running",
                "created_at": "2026-10-28T00:00:00Z",
            }
        ],
        "next_cursor": "next",
    }


def test_list_jobs_empty(service: FakeUserJobService) -> None:
    r = client.get("/jobs", headers=HEADERS)
    assert r.status_code == 200
    assert r.json() == {"items": [], "next_cursor": None}


# 쿼리가 없으면 기본값(limit 20, cursor·status 없음), 있으면 그대로 service로 간다. 정의되지 않은 쿼리는 무시.
@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ("", ("alice", 20, None, None)),
        (
            "?limit=5&cursor=abc&status=running",
            ("alice", 5, "abc", JobStatus.RUNNING),
        ),
        ("?limit=100&sort=name&stauts=failed", ("alice", 100, None, None)),
    ],
)
def test_list_jobs_passes_query(
    service: FakeUserJobService, query: str, expected: tuple[Any, ...]
) -> None:
    assert client.get(f"/jobs{query}", headers=HEADERS).status_code == 200
    assert service.list_calls == [expected]


# spec "요청 검증 에러" 표의 행마다. 검증에서 걸리면 service를 부르지 않는다.
@pytest.mark.parametrize(
    ("headers", "query", "expected"),
    [
        ({}, "", ErrorEnum.INVALID_USER_ID),
        ({"X-User-Id": "Alice"}, "", ErrorEnum.INVALID_USER_ID),
        (HEADERS, "?limit=0", ErrorEnum.INVALID_LIMIT),
        (HEADERS, "?limit=-1", ErrorEnum.INVALID_LIMIT),
        (HEADERS, "?limit=101", ErrorEnum.INVALID_LIMIT),
        (HEADERS, "?limit=abc", ErrorEnum.INVALID_LIMIT),
        (HEADERS, "?limit=1.5", ErrorEnum.INVALID_LIMIT),
        (HEADERS, "?limit=", ErrorEnum.INVALID_LIMIT),
        (HEADERS, "?status=deleted", ErrorEnum.INVALID_JOB_STATUS),
        (HEADERS, "?status=RUNNING", ErrorEnum.INVALID_JOB_STATUS),
        (HEADERS, "?status=", ErrorEnum.INVALID_JOB_STATUS),
        (HEADERS, "?status=running,failed", ErrorEnum.INVALID_JOB_STATUS),
        (HEADERS, "?status=running&status=failed", ErrorEnum.INVALID_JOB_STATUS),
        (HEADERS, "?status=running&status=running", ErrorEnum.INVALID_JOB_STATUS),
        (HEADERS, "?limit=5&limit=100", ErrorEnum.INVALID_LIMIT),
        (HEADERS, "?cursor=a&cursor=b", ErrorEnum.INVALID_CURSOR),
    ],
)
def test_list_jobs_validation_errors(
    service: FakeUserJobService,
    headers: dict[str, str],
    query: str,
    expected: ErrorEnum,
) -> None:
    assert_error(client.get(f"/jobs{query}", headers=headers), expected)
    assert service.list_calls == []


# 여러 개가 틀리면 헤더 > limit > status. status 중복 검사도 이 순서를 지킨다.
@pytest.mark.parametrize(
    ("headers", "query", "expected"),
    [
        ({}, "?status=running&status=failed", ErrorEnum.INVALID_USER_ID),
        ({}, "?limit=0&status=bad", ErrorEnum.INVALID_USER_ID),
        (HEADERS, "?limit=0&status=running&status=failed", ErrorEnum.INVALID_LIMIT),
        (HEADERS, "?limit=abc&status=bad", ErrorEnum.INVALID_LIMIT),
        # 중복끼리는 limit > status > cursor
        (
            HEADERS,
            "?cursor=a&cursor=b&status=running&status=failed",
            ErrorEnum.INVALID_JOB_STATUS,
        ),
        (HEADERS, "?cursor=a&cursor=b&limit=1&limit=2", ErrorEnum.INVALID_LIMIT),
    ],
)
def test_list_jobs_validation_priority(
    service: FakeUserJobService,
    headers: dict[str, str],
    query: str,
    expected: ErrorEnum,
) -> None:
    assert_error(client.get(f"/jobs{query}", headers=headers), expected)


# service의 비즈니스 에러(잘못된 cursor)는 ErrorEnum 상태 코드·code 그대로
def test_list_jobs_invalid_cursor(service: FakeUserJobService) -> None:
    service.error = ErrorEnum.INVALID_CURSOR
    r = client.get("/jobs?cursor=bad", headers=HEADERS)
    assert_error(r, ErrorEnum.INVALID_CURSOR)


# /docs 스키마: GET /jobs가 200·400·500만 문서화하고, 파라미터는 헤더 + 쿼리 3개다
def test_openapi_list_jobs() -> None:
    op = client.get("/openapi.json").json()["paths"]["/jobs"]["get"]
    assert set(op["responses"]) == {"200", "400", "500"}
    assert {(p["name"], p["in"]) for p in op["parameters"]} == {
        ("X-User-Id", "header"),
        ("limit", "query"),
        ("cursor", "query"),
        ("status", "query"),
    }
    assert "specs/003-api-job-list/contracts/get-jobs.md" in op["description"]
    assert "example" in op["responses"]["200"]["content"]["application/json"]


# /docs·/redoc의 example: 응답 example은 JobListResponse 모양, cursor example은 실제로 풀리는 값,
# 쿼리 example을 그대로 보내면 200이다.
def test_openapi_list_examples_are_valid(service: FakeUserJobService) -> None:
    JobListResponse.model_validate(JOB_LIST_RESPONSE_EXAMPLE)
    decode_cursor(JOB_LIST_CURSOR_EXAMPLE)
    r = client.get(
        "/jobs",
        headers=HEADERS,
        params={"limit": 20, "status": "running", "cursor": JOB_LIST_CURSOR_EXAMPLE},
    )
    assert r.status_code == 200
