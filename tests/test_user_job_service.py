from collections.abc import Collection
from datetime import datetime
from typing import Any

import pytest

from src.core.exception.my_exception import ErrorEnum, MyApiError
from src.models.enums import JobStatus
from src.models.user_job_models import (
    JOB_LIST_DEFAULT_LIMIT,
    JOB_LIST_MAX_LIMIT,
    MAX_JOBS_PER_USER,
    JobPage,
    JobPosition,
    UserJob,
    WebTemplate,
)
from src.repository.user_job_repository import (
    DuplicateJobNameError,
    JobQuotaExceededError,
)
from src.services.user_job_service import UserJobService


class FakeUserJobRepository:
    """메모리 dict로 UserJobRepository를 흉내 낸다. 유니크 이름·조건부 갱신 규칙을 실제와 같게 둔다."""

    def __init__(self) -> None:
        self.docs: dict[str, dict[str, Any]] = {}
        self._seq = 0
        # 조건부 갱신 직전에 다른 갱신이 끼어드는 상황을 만들 때 쓴다.
        self.interfere_once: JobStatus | None = None
        self.update_calls = 0
        self.max_slots_seen: int | None = None
        self.page_limit_seen: int | None = None

    # 실제 repository처럼 빈 슬롯이 없으면 한도 초과, 그다음 이름 중복을 판단한다.
    async def insert_with_slot(
        self, job_doc: dict[str, Any], max_slots: int
    ) -> UserJob:
        self.max_slots_seen = max_slots
        active = [
            d
            for d in self.docs.values()
            if d["owner_id"] == job_doc["owner_id"] and not d["is_deleted"]
        ]
        used = {d["quota_slot"] for d in active}
        slot = next((i for i in range(max_slots) if i not in used), None)
        if slot is None:
            raise JobQuotaExceededError
        if any(d["name"] == job_doc["name"] for d in active):
            raise DuplicateJobNameError
        self._seq += 1
        job_id = f"{self._seq:024x}"
        self.docs[job_id] = {**job_doc, "quota_slot": slot}
        return UserJob(id=job_id, **self.docs[job_id])

    # 실제 repository처럼 (created_at, id) 내림차순으로 정렬하고, after 위치보다 뒤인 것만 limit개 돌려준다.
    # 가짜 id는 같은 길이의 hex라 문자열 비교가 ObjectId 비교와 같다.
    async def find_active_page(
        self,
        owner_id: str,
        status: JobStatus | None,
        after: JobPosition | None,
        limit: int,
    ) -> list[UserJob]:
        self.page_limit_seen = limit
        jobs = sorted(
            (
                UserJob(id=i, **d)
                for i, d in self.docs.items()
                if d["owner_id"] == owner_id
                and not d["is_deleted"]
                and (status is None or d["status"] == status.value)
            ),
            key=lambda j: (j.created_at, j.id),
            reverse=True,
        )
        if after is not None:
            jobs = [
                j for j in jobs if (j.created_at, j.id) < (after.created_at, after.id)
            ]
        return jobs[:limit]

    async def find_active_by_id(self, job_id: str) -> UserJob | None:
        d = self.docs.get(job_id)
        return UserJob(id=job_id, **d) if d and not d["is_deleted"] else None

    async def update_status_from(
        self,
        job_id: str,
        from_statuses: Collection[JobStatus],
        to_status: JobStatus,
        now: datetime,
    ) -> UserJob | None:
        self.update_calls += 1
        if self.interfere_once is not None:
            self.docs[job_id]["status"] = self.interfere_once.value
            self.interfere_once = None
        d = self.docs.get(job_id)
        if (
            not d
            or d["is_deleted"]
            or d["status"] not in {s.value for s in from_statuses}
        ):
            return None
        d["status"], d["updated_at"] = to_status.value, now
        return UserJob(id=job_id, **d)

    async def soft_delete(self, owner_id: str, job_id: str, now: datetime) -> bool:
        d = self.docs.get(job_id)
        if not d or d["owner_id"] != owner_id or d["is_deleted"]:
            return False
        d.update(is_deleted=True, deleted_at=now, updated_at=now)
        return True


# 필수 필드만 채운 web 템플릿. 나머지는 인자로 덮어쓴다.
def web(**fields: Any) -> WebTemplate:
    return WebTemplate(**{"type": "web", "image": "nginx:1.27", "port": 80, **fields})


@pytest.fixture
def repo() -> FakeUserJobRepository:
    return FakeUserJobRepository()


@pytest.fixture
def service(repo: FakeUserJobRepository) -> UserJobService:
    return UserJobService(repo)


def assert_error(
    exc_info: pytest.ExceptionInfo[MyApiError], expected: ErrorEnum
) -> None:
    assert exc_info.value.error_enum is expected


# --- create_job ---


# 정상 생성: pending, 유저 네임스페이스, 템플릿 저장(기본값 포함), 템플릿으로 만든 리소스
async def test_create_job(service: UserJobService) -> None:
    job = await service.create_job(
        owner_id="alice", name="my-app", template=web(replicas=2)
    )
    assert job.status is JobStatus.PENDING
    assert job.namespace == "user-alice"
    assert job.name == "my-app"
    assert job.is_deleted is False and job.deleted_at is None
    assert job.created_at == job.updated_at and job.created_at.tzinfo is not None
    assert job.template == web(replicas=2, env={}, size="small")
    assert [(r.kind, r.name) for r in job.resources] == [
        ("Deployment", "my-app"),
        ("Service", "my-app"),
    ]
    assert all(
        r.manifest["metadata"]["namespace"] == "user-alice" for r in job.resources
    )
    deployment = job.resources[0].manifest
    assert deployment["spec"]["replicas"] == 2


# 템플릿은 JSON으로 저장된다(enum이 아닌 문자열). MongoDB에 그대로 넣을 수 있는 형태.
async def test_create_job_stores_template_as_json(
    service: UserJobService, repo: FakeUserJobRepository
) -> None:
    job = await service.create_job(
        owner_id="alice", name="my-app", template=web(size="medium")
    )
    stored = repo.docs[job.id]["template"]
    assert stored == {
        "type": "web",
        "image": "nginx:1.27",
        "port": 80,
        "replicas": 1,
        "env": {},
        "size": "medium",
    }
    assert type(stored["size"]) is str


@pytest.mark.parametrize("owner_id", ["", "Alice", "-alice", "alice_1", "a" * 59, None])
async def test_create_job_invalid_owner(service: UserJobService, owner_id: Any) -> None:
    with pytest.raises(MyApiError) as e:
        await service.create_job(owner_id=owner_id, name="my-app", template=web())
    assert_error(e, ErrorEnum.INVALID_USER_ID)


async def test_create_job_owner_id_max_length_ok(service: UserJobService) -> None:
    job = await service.create_job(owner_id="a" * 58, name="my-app", template=web())
    assert len(job.namespace) == 63


# job 이름은 DNS-1035 label: 숫자 시작·대문자·끝 '-'·64자·점은 거부
@pytest.mark.parametrize("name", ["", "1app", "My-App", "app-", "a" * 64, "my.app"])
async def test_create_job_invalid_name(service: UserJobService, name: str) -> None:
    with pytest.raises(MyApiError) as e:
        await service.create_job(owner_id="alice", name=name, template=web())
    assert_error(e, ErrorEnum.INVALID_JOB_NAME)


async def test_create_job_name_max_length_ok(service: UserJobService) -> None:
    job = await service.create_job(owner_id="alice", name="a" * 63, template=web())
    assert job.resources[0].name == "a" * 63


# owner_id를 받는 조회·삭제도 유저 ID 형식이 틀리면 INVALID_USER_ID(400). list는 limit·cursor보다 먼저 검사한다.
@pytest.mark.parametrize("method", ["list", "get", "delete"])
@pytest.mark.parametrize("owner_id", ["", "Bad_User!"])
async def test_invalid_owner_id_on_read_delete(
    service: UserJobService, method: str, owner_id: str
) -> None:
    job = await service.create_job(owner_id="alice", name="my-app", template=web())
    calls = {
        "list": lambda: service.list_jobs(owner_id, limit=0, cursor="bad"),
        "get": lambda: service.get_job(owner_id, job.id),
        "delete": lambda: service.delete_job(owner_id, job.id),
    }
    with pytest.raises(MyApiError) as e:
        await calls[method]()
    assert_error(e, ErrorEnum.INVALID_USER_ID)


async def test_create_job_duplicated_name(service: UserJobService) -> None:
    await service.create_job(owner_id="alice", name="my-app", template=web())
    with pytest.raises(MyApiError) as e:
        await service.create_job(owner_id="alice", name="my-app", template=web())
    assert_error(e, ErrorEnum.JOB_NAME_DUPLICATED)


# 다른 유저는 같은 이름 가능, 삭제된 job의 이름은 재사용 가능
async def test_create_job_name_reuse(service: UserJobService) -> None:
    job = await service.create_job(owner_id="alice", name="my-app", template=web())
    await service.create_job(owner_id="bob", name="my-app", template=web())
    await service.delete_job("alice", job.id)
    again = await service.create_job(owner_id="alice", name="my-app", template=web())
    assert again.id != job.id


# --- 개수 한도 ---


# service가 한도 값(MAX_JOBS_PER_USER)을 repository에 넘긴다
async def test_quota_limit_passed_to_repository(
    service: UserJobService, repo: FakeUserJobRepository
) -> None:
    await service.create_job(owner_id="alice", name="my-app", template=web())
    assert repo.max_slots_seen == MAX_JOBS_PER_USER == 10


# 10개까지 성공, 11번째는 JOB_QUOTA_EXCEEDED
async def test_quota_exceeded(service: UserJobService) -> None:
    for i in range(MAX_JOBS_PER_USER):
        await service.create_job(owner_id="alice", name=f"job{i}", template=web())
    with pytest.raises(MyApiError) as e:
        await service.create_job(owner_id="alice", name="one-more", template=web())
    assert_error(e, ErrorEnum.JOB_QUOTA_EXCEEDED)


# 한도가 꽉 찬 유저가 중복 이름을 보내면 한도 초과가 먼저(spec 검사 순서)
async def test_quota_checked_before_duplicated_name(service: UserJobService) -> None:
    for i in range(MAX_JOBS_PER_USER):
        await service.create_job(owner_id="alice", name=f"job{i}", template=web())
    with pytest.raises(MyApiError) as e:
        await service.create_job(owner_id="alice", name="job0", template=web())
    assert_error(e, ErrorEnum.JOB_QUOTA_EXCEEDED)


# 삭제하면 개수에서 빠져 다시 만들 수 있다
async def test_quota_freed_by_delete(service: UserJobService) -> None:
    jobs = [
        await service.create_job(owner_id="alice", name=f"job{i}", template=web())
        for i in range(MAX_JOBS_PER_USER)
    ]
    await service.delete_job("alice", jobs[3].id)
    job = await service.create_job(owner_id="alice", name="one-more", template=web())
    assert job.quota_slot == jobs[3].quota_slot


# 한도는 유저별이다
async def test_quota_per_user(service: UserJobService) -> None:
    for i in range(MAX_JOBS_PER_USER):
        await service.create_job(owner_id="alice", name=f"job{i}", template=web())
    assert await service.create_job(owner_id="bob", name="job0", template=web())


# --- list_jobs / get_job ---


async def test_list_jobs_own_active_latest_first(service: UserJobService) -> None:
    first = await service.create_job(owner_id="alice", name="first", template=web())
    second = await service.create_job(owner_id="alice", name="second", template=web())
    deleted = await service.create_job(owner_id="alice", name="deleted", template=web())
    await service.create_job(owner_id="bob", name="other", template=web())
    await service.delete_job("alice", deleted.id)
    page = await service.list_jobs("alice")
    assert [j.id for j in page.items] == [second.id, first.id]
    assert page.next_cursor is None


async def test_list_jobs_empty(service: UserJobService) -> None:
    assert await service.list_jobs("alice") == JobPage(items=[], next_cursor=None)


# 다음 페이지가 있는지 보려고 repository에 limit + 1을 넘긴다. 기본 limit은 20.
async def test_list_jobs_reads_one_more(
    service: UserJobService, repo: FakeUserJobRepository
) -> None:
    await service.list_jobs("alice")
    assert repo.page_limit_seen == JOB_LIST_DEFAULT_LIMIT + 1 == 21
    await service.list_jobs("alice", limit=3)
    assert repo.page_limit_seen == 4


# next_cursor가 None이 될 때까지 이어 받아 페이지별 job 이름을 모은다.
async def collect_pages(
    service: UserJobService, limit: int, status: JobStatus | None = None
) -> list[list[str]]:
    pages, cursor = [], None
    while True:
        page = await service.list_jobs(
            owner_id="alice", limit=limit, cursor=cursor, status=status
        )
        pages.append([j.name for j in page.items])
        if page.next_cursor is None:
            return pages
        cursor = page.next_cursor


# 끝 페이지까지 이어 받으면 빠짐·겹침 없이 최신순 전체와 같고, 마지막 페이지만 next_cursor가 None
async def test_list_jobs_pages(service: UserJobService) -> None:
    for i in range(5):
        await service.create_job(owner_id="alice", name=f"job{i}", template=web())
    assert await collect_pages(service, 2) == [
        ["job4", "job3"],
        ["job2", "job1"],
        ["job0"],
    ]


# 남은 개수가 정확히 limit이면 그 페이지에서 끝난다(빈 페이지로 가는 cursor를 주지 않는다)
async def test_list_jobs_exact_multiple_of_limit(service: UserJobService) -> None:
    for i in range(4):
        await service.create_job(owner_id="alice", name=f"job{i}", template=web())
    assert await collect_pages(service, 2) == [["job3", "job2"], ["job1", "job0"]]
    assert await collect_pages(service, 4) == [["job3", "job2", "job1", "job0"]]


# created_at이 같으면 id 내림차순. 같은 시각 그룹이 페이지 경계에 걸려도 빠짐·겹침 없음
async def test_list_jobs_same_created_at(
    service: UserJobService, repo: FakeUserJobRepository
) -> None:
    jobs = [
        await service.create_job(owner_id="alice", name=f"job{i}", template=web())
        for i in range(3)
    ]
    for job in jobs:
        repo.docs[job.id]["created_at"] = jobs[0].created_at
    assert await collect_pages(service, 2) == [["job2", "job1"], ["job0"]]


async def test_list_jobs_status_filter(service: UserJobService) -> None:
    jobs = [
        await service.create_job(owner_id="alice", name=f"job{i}", template=web())
        for i in range(4)
    ]
    await service.update_job_status(jobs[1].id, JobStatus.RUNNING)
    await service.update_job_status(jobs[3].id, JobStatus.RUNNING)
    assert await collect_pages(service=service, limit=1, status=JobStatus.RUNNING) == [
        ["job3"],
        ["job1"],
    ]
    assert await collect_pages(service=service, limit=10, status=JobStatus.FAILED) == [
        []
    ]


# cursor가 가리키던 job이 그사이 삭제돼도 그 위치 뒤가 이어진다
async def test_list_jobs_cursor_job_deleted(service: UserJobService) -> None:
    for i in range(3):
        await service.create_job(owner_id="alice", name=f"job{i}", template=web())
    first = await service.list_jobs("alice", limit=1)
    await service.delete_job("alice", first.items[0].id)
    rest = await service.list_jobs("alice", limit=10, cursor=first.next_cursor)
    assert [j.name for j in rest.items] == ["job1", "job0"]


# 다른 유저 job 위치의 cursor를 보내도 자기 job만 나온다
async def test_list_jobs_other_users_cursor(service: UserJobService) -> None:
    await service.create_job(owner_id="alice", name="mine", template=web())
    await service.create_job(owner_id="bob", name="b0", template=web())
    await service.create_job(owner_id="bob", name="b1", template=web())
    bob_cursor = (await service.list_jobs("bob", limit=1)).next_cursor
    page = await service.list_jobs("alice", cursor=bob_cursor)
    assert [j.name for j in page.items] == ["mine"]


@pytest.mark.parametrize("limit", [1, JOB_LIST_MAX_LIMIT])
async def test_list_jobs_limit_bounds_ok(service: UserJobService, limit: int) -> None:
    await service.list_jobs("alice", limit=limit)


@pytest.mark.parametrize("limit", [0, -1, JOB_LIST_MAX_LIMIT + 1, True, "20", None])
async def test_list_jobs_invalid_limit(service: UserJobService, limit: Any) -> None:
    with pytest.raises(MyApiError) as e:
        await service.list_jobs("alice", limit=limit)
    assert_error(e, ErrorEnum.INVALID_LIMIT)


async def test_list_jobs_invalid_cursor(service: UserJobService) -> None:
    with pytest.raises(MyApiError) as e:
        await service.list_jobs("alice", cursor="not-a-cursor")
    assert_error(e, ErrorEnum.INVALID_CURSOR)


# 검사 순서: limit이 cursor보다 먼저
async def test_list_jobs_limit_checked_before_cursor(service: UserJobService) -> None:
    with pytest.raises(MyApiError) as e:
        await service.list_jobs("alice", limit=0, cursor="not-a-cursor")
    assert_error(e, ErrorEnum.INVALID_LIMIT)


async def test_get_job(service: UserJobService) -> None:
    job = await service.create_job(owner_id="alice", name="my-app", template=web())
    assert (await service.get_job("alice", job.id)).id == job.id


# 남의 job·없음·삭제됨·잘못된 ID는 모두 JOB_NOT_FOUND
@pytest.mark.parametrize("case", ["other_owner", "missing", "deleted", "invalid_id"])
async def test_get_job_not_found(service: UserJobService, case: str) -> None:
    job = await service.create_job(owner_id="alice", name="my-app", template=web())
    owner, job_id = "alice", job.id
    if case == "other_owner":
        owner = "bob"
    elif case == "missing":
        job_id = "f" * 24
    elif case == "deleted":
        await service.delete_job("alice", job.id)
    else:
        job_id = "not-an-id"
    with pytest.raises(MyApiError) as e:
        await service.get_job(owner, job_id)
    assert_error(e, ErrorEnum.JOB_NOT_FOUND)


# --- update_job_status ---


@pytest.mark.parametrize(
    "path",
    [
        [JobStatus.RUNNING],
        [JobStatus.FAILED],
        [JobStatus.RUNNING, JobStatus.FAILED],
        [JobStatus.FAILED, JobStatus.RUNNING],
    ],
)
async def test_update_status_allowed(
    service: UserJobService, path: list[JobStatus]
) -> None:
    job = await service.create_job(owner_id="alice", name="my-app", template=web())
    for status in path:
        job = await service.update_job_status(job.id, status)
    assert job.status is path[-1]
    assert job.updated_at >= job.created_at


# 같은 상태로의 갱신은 변경 없이 성공(멱등)
async def test_update_status_same_is_noop(service: UserJobService) -> None:
    job = await service.create_job(owner_id="alice", name="my-app", template=web())
    same = await service.update_job_status(job.id, JobStatus.PENDING)
    assert same.status is JobStatus.PENDING and same.updated_at == job.updated_at


@pytest.mark.parametrize("current", [JobStatus.RUNNING, JobStatus.FAILED])
async def test_update_status_back_to_pending_rejected(
    service: UserJobService, current: JobStatus
) -> None:
    job = await service.create_job(owner_id="alice", name="my-app", template=web())
    await service.update_job_status(job.id, current)
    with pytest.raises(MyApiError) as e:
        await service.update_job_status(job.id, JobStatus.PENDING)
    assert_error(e, ErrorEnum.INVALID_STATUS_TRANSITION)


@pytest.mark.parametrize("case", ["missing", "deleted", "invalid_id"])
async def test_update_status_not_found(service: UserJobService, case: str) -> None:
    job = await service.create_job(owner_id="alice", name="my-app", template=web())
    job_id = {"missing": "f" * 24, "invalid_id": "not-an-id"}.get(case, job.id)
    if case == "deleted":
        await service.delete_job("alice", job.id)
    with pytest.raises(MyApiError) as e:
        await service.update_job_status(job_id, JobStatus.RUNNING)
    assert_error(e, ErrorEnum.JOB_NOT_FOUND)


# 조건부 갱신 직전에 다른 갱신이 같은 목표 상태로 바꿔 놓으면: 갱신은 빗나가고, 다시 읽어 같은 상태이므로 그대로 성공
async def test_update_status_concurrent_same_target(
    service: UserJobService, repo: FakeUserJobRepository
) -> None:
    job = await service.create_job(owner_id="alice", name="my-app", template=web())
    repo.interfere_once = JobStatus.RUNNING
    result = await service.update_job_status(job.id, JobStatus.RUNNING)
    assert result.status is JobStatus.RUNNING
    assert repo.update_calls == 1


# 끼어든 상태(failed)도 목표(running)의 허용된 이전 상태라면 한 번의 조건부 갱신으로 바로 성공
async def test_update_status_concurrent_other_source(
    service: UserJobService, repo: FakeUserJobRepository
) -> None:
    job = await service.create_job(owner_id="alice", name="my-app", template=web())
    repo.interfere_once = JobStatus.FAILED
    result = await service.update_job_status(job.id, JobStatus.RUNNING)
    assert result.status is JobStatus.RUNNING
    assert repo.update_calls == 1


# 상태 갱신은 재시도 없이 조건부 갱신 한 번만 한다(허용 전이·금지 전이·같은 상태 모두)
@pytest.mark.parametrize(
    "target", [JobStatus.RUNNING, JobStatus.PENDING, JobStatus.FAILED]
)
async def test_update_status_single_write(
    service: UserJobService, repo: FakeUserJobRepository, target: JobStatus
) -> None:
    job = await service.create_job(owner_id="alice", name="my-app", template=web())
    await service.update_job_status(job.id, JobStatus.FAILED)
    repo.update_calls = 0
    try:
        await service.update_job_status(job.id, target)
    except MyApiError as e:
        assert e.error_enum is ErrorEnum.INVALID_STATUS_TRANSITION
    assert repo.update_calls == 1


# --- delete_job ---


async def test_delete_job(service: UserJobService, repo: FakeUserJobRepository) -> None:
    job = await service.create_job(owner_id="alice", name="my-app", template=web())
    await service.delete_job("alice", job.id)
    doc = repo.docs[job.id]
    assert doc["is_deleted"] is True and doc["deleted_at"] is not None
    assert doc["updated_at"] == doc["deleted_at"]


@pytest.mark.parametrize(
    "case", ["other_owner", "missing", "already_deleted", "invalid_id"]
)
async def test_delete_job_not_found(service: UserJobService, case: str) -> None:
    job = await service.create_job(owner_id="alice", name="my-app", template=web())
    owner, job_id = "alice", job.id
    if case == "other_owner":
        owner = "bob"
    elif case == "missing":
        job_id = "f" * 24
    elif case == "already_deleted":
        await service.delete_job("alice", job.id)
    else:
        job_id = "not-an-id"
    with pytest.raises(MyApiError) as e:
        await service.delete_job(owner, job_id)
    assert_error(e, ErrorEnum.JOB_NOT_FOUND)
