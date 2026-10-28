from datetime import datetime
from typing import Any

import pytest

from src.core.exception.my_exception import ErrorEnum, MyApiError
from src.models.user_job import JobStatus, UserJob
from src.repository.user_job_repository import DuplicateJobNameError
from src.services.user_job_service import UserJobService


class FakeUserJobRepository:
    """메모리 dict로 UserJobRepository를 흉내 낸다. 유니크 이름·조건부 갱신 규칙을 실제와 같게 둔다."""

    def __init__(self) -> None:
        self.docs: dict[str, dict[str, Any]] = {}
        self._seq = 0
        # 조건부 갱신 직전에 다른 갱신이 끼어드는 상황을 만들 때 쓴다.
        self.interfere_once: JobStatus | None = None

    async def insert(self, job_doc: dict[str, Any]) -> UserJob:
        for d in self.docs.values():
            if not d["is_deleted"] and (d["owner_id"], d["name"]) == (
                job_doc["owner_id"],
                job_doc["name"],
            ):
                raise DuplicateJobNameError
        self._seq += 1
        job_id = f"{self._seq:024x}"
        self.docs[job_id] = dict(job_doc)
        return UserJob(id=job_id, **job_doc)

    async def find_active_by_owner(self, owner_id: str) -> list[UserJob]:
        jobs = [
            UserJob(id=i, **d)
            for i, d in self.docs.items()
            if d["owner_id"] == owner_id and not d["is_deleted"]
        ]
        return sorted(jobs, key=lambda j: j.created_at, reverse=True)

    async def find_active_by_id(self, job_id: str) -> UserJob | None:
        d = self.docs.get(job_id)
        return UserJob(id=job_id, **d) if d and not d["is_deleted"] else None

    async def update_status_if(
        self, job_id: str, from_status: JobStatus, to_status: JobStatus, now: datetime
    ) -> UserJob | None:
        if self.interfere_once is not None:
            self.docs[job_id]["status"] = self.interfere_once.value
            self.interfere_once = None
        d = self.docs.get(job_id)
        if not d or d["is_deleted"] or d["status"] != from_status.value:
            return None
        d["status"], d["updated_at"] = to_status.value, now
        return UserJob(id=job_id, **d)

    async def soft_delete(self, owner_id: str, job_id: str, now: datetime) -> bool:
        d = self.docs.get(job_id)
        if not d or d["owner_id"] != owner_id or d["is_deleted"]:
            return False
        d.update(is_deleted=True, deleted_at=now, updated_at=now)
        return True


def manifest(
    kind: str = "Deployment",
    name: str = "web",
    api_version: str = "apps/v1",
    **meta: Any,
) -> dict:
    return {
        "apiVersion": api_version,
        "kind": kind,
        "metadata": {"name": name, **meta},
        "spec": {},
    }


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


# 정상 생성: pending, 유저 네임스페이스, 매니페스트에 namespace 채움, 조회용 필드 추출
async def test_create_job(service: UserJobService) -> None:
    job = await service.create_job(
        "alice", "my-app", [manifest(), manifest("Service", "web", "v1")]
    )
    assert job.status is JobStatus.PENDING
    assert job.namespace == "user-alice"
    assert job.is_deleted is False and job.deleted_at is None
    assert job.created_at == job.updated_at and job.created_at.tzinfo is not None
    assert [(r.kind, r.name) for r in job.resources] == [
        ("Deployment", "web"),
        ("Service", "web"),
    ]
    assert all(
        r.manifest["metadata"]["namespace"] == "user-alice" for r in job.resources
    )


# 매니페스트에 job 네임스페이스와 같은 namespace가 있으면 허용
async def test_create_job_same_namespace_ok(service: UserJobService) -> None:
    job = await service.create_job(
        "alice", "my-app", [manifest(namespace="user-alice")]
    )
    assert job.resources[0].manifest["metadata"]["namespace"] == "user-alice"


@pytest.mark.parametrize("owner_id", ["", "Alice", "-alice", "alice_1", "a" * 59, None])
async def test_create_job_invalid_owner(service: UserJobService, owner_id: Any) -> None:
    with pytest.raises(MyApiError) as e:
        await service.create_job(owner_id, "my-app", [manifest()])
    assert_error(e, ErrorEnum.INVALID_PARAMETER)


async def test_create_job_owner_id_max_length_ok(service: UserJobService) -> None:
    job = await service.create_job("a" * 58, "my-app", [manifest()])
    assert len(job.namespace) == 63


@pytest.mark.parametrize("name", ["", "My-App", "app-", "a" * 64, "my.app"])
async def test_create_job_invalid_name(service: UserJobService, name: str) -> None:
    with pytest.raises(MyApiError) as e:
        await service.create_job("alice", name, [manifest()])
    assert_error(e, ErrorEnum.INVALID_PARAMETER)


@pytest.mark.parametrize(
    "manifests",
    [
        [],  # 리소스 없음
        [manifest("Secret", "s", "v1")],  # 허용 목록 밖(Secret 제외)
        [manifest("Deployment", "web", "v1")],  # apiVersion 불일치
        [manifest(name="Web")],  # 이름 형식 오류
        [{"apiVersion": "apps/v1", "kind": "Deployment"}],  # metadata 없음
        [
            {"apiVersion": {}, "kind": "Deployment", "metadata": {"name": "web"}}
        ],  # 문자열 아닌 apiVersion
        ["not-a-dict"],  # 매니페스트가 dict 아님
        [manifest(namespace="other")],  # 다른 네임스페이스
        [manifest(), manifest()],  # (kind, name) 중복
    ],
)
async def test_create_job_invalid_resource(
    service: UserJobService, manifests: list
) -> None:
    with pytest.raises(MyApiError) as e:
        await service.create_job("alice", "my-app", manifests)
    assert_error(e, ErrorEnum.INVALID_JOB_RESOURCE)


# 같은 이름이라도 kind가 다르면 허용
async def test_create_job_same_name_different_kind_ok(service: UserJobService) -> None:
    job = await service.create_job(
        "alice", "my-app", [manifest(), manifest("Service", "web", "v1")]
    )
    assert len(job.resources) == 2


async def test_create_job_duplicated_name(service: UserJobService) -> None:
    await service.create_job("alice", "my-app", [manifest()])
    with pytest.raises(MyApiError) as e:
        await service.create_job("alice", "my-app", [manifest()])
    assert_error(e, ErrorEnum.JOB_NAME_DUPLICATED)


# 다른 유저는 같은 이름 가능, 삭제된 job의 이름은 재사용 가능
async def test_create_job_name_reuse(service: UserJobService) -> None:
    job = await service.create_job("alice", "my-app", [manifest()])
    await service.create_job("bob", "my-app", [manifest()])
    await service.delete_job("alice", job.id)
    again = await service.create_job("alice", "my-app", [manifest()])
    assert again.id != job.id


# --- list_jobs / get_job ---


async def test_list_jobs_own_active_latest_first(service: UserJobService) -> None:
    first = await service.create_job("alice", "first", [manifest()])
    second = await service.create_job("alice", "second", [manifest()])
    deleted = await service.create_job("alice", "deleted", [manifest()])
    await service.create_job("bob", "other", [manifest()])
    await service.delete_job("alice", deleted.id)
    assert [j.id for j in await service.list_jobs("alice")] == [second.id, first.id]


async def test_list_jobs_empty(service: UserJobService) -> None:
    assert await service.list_jobs("alice") == []


async def test_get_job(service: UserJobService) -> None:
    job = await service.create_job("alice", "my-app", [manifest()])
    assert (await service.get_job("alice", job.id)).id == job.id


# 남의 job·없음·삭제됨·잘못된 ID는 모두 JOB_NOT_FOUND
@pytest.mark.parametrize("case", ["other_owner", "missing", "deleted", "invalid_id"])
async def test_get_job_not_found(service: UserJobService, case: str) -> None:
    job = await service.create_job("alice", "my-app", [manifest()])
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
    job = await service.create_job("alice", "my-app", [manifest()])
    for status in path:
        job = await service.update_job_status(job.id, status)
    assert job.status is path[-1]
    assert job.updated_at >= job.created_at


# 같은 상태로의 갱신은 변경 없이 성공(멱등)
async def test_update_status_same_is_noop(service: UserJobService) -> None:
    job = await service.create_job("alice", "my-app", [manifest()])
    same = await service.update_job_status(job.id, JobStatus.PENDING)
    assert same.status is JobStatus.PENDING and same.updated_at == job.updated_at


@pytest.mark.parametrize("current", [JobStatus.RUNNING, JobStatus.FAILED])
async def test_update_status_back_to_pending_rejected(
    service: UserJobService, current: JobStatus
) -> None:
    job = await service.create_job("alice", "my-app", [manifest()])
    await service.update_job_status(job.id, current)
    with pytest.raises(MyApiError) as e:
        await service.update_job_status(job.id, JobStatus.PENDING)
    assert_error(e, ErrorEnum.INVALID_STATUS_TRANSITION)


@pytest.mark.parametrize("case", ["missing", "deleted", "invalid_id"])
async def test_update_status_not_found(service: UserJobService, case: str) -> None:
    job = await service.create_job("alice", "my-app", [manifest()])
    job_id = {"missing": "f" * 24, "invalid_id": "not-an-id"}.get(case, job.id)
    if case == "deleted":
        await service.delete_job("alice", job.id)
    with pytest.raises(MyApiError) as e:
        await service.update_job_status(job_id, JobStatus.RUNNING)
    assert_error(e, ErrorEnum.JOB_NOT_FOUND)


# 읽은 뒤 다른 갱신이 끼어들면 다시 읽어 판단한다: 끼어든 값이 목표와 같으면 그대로 성공
async def test_update_status_concurrent_same_target(
    service: UserJobService, repo: FakeUserJobRepository
) -> None:
    job = await service.create_job("alice", "my-app", [manifest()])
    repo.interfere_once = JobStatus.RUNNING
    assert (
        await service.update_job_status(job.id, JobStatus.RUNNING)
    ).status is JobStatus.RUNNING


# 끼어든 값에서 목표로 가는 전이가 허용되면 이어서 갱신
async def test_update_status_concurrent_then_transition(
    service: UserJobService, repo: FakeUserJobRepository
) -> None:
    job = await service.create_job("alice", "my-app", [manifest()])
    repo.interfere_once = JobStatus.FAILED
    assert (
        await service.update_job_status(job.id, JobStatus.RUNNING)
    ).status is JobStatus.RUNNING


# --- delete_job ---


async def test_delete_job(service: UserJobService, repo: FakeUserJobRepository) -> None:
    job = await service.create_job("alice", "my-app", [manifest()])
    await service.delete_job("alice", job.id)
    doc = repo.docs[job.id]
    assert doc["is_deleted"] is True and doc["deleted_at"] is not None
    assert doc["updated_at"] == doc["deleted_at"]


@pytest.mark.parametrize(
    "case", ["other_owner", "missing", "already_deleted", "invalid_id"]
)
async def test_delete_job_not_found(service: UserJobService, case: str) -> None:
    job = await service.create_job("alice", "my-app", [manifest()])
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
