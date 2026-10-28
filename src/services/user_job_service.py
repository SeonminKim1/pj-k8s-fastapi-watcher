import re
from datetime import UTC, datetime
from typing import Any

from src.core.exception.my_exception import ErrorEnum, MyApiError
from src.models.user_job import (
    ALLOWED_RESOURCE_KINDS,
    ALLOWED_STATUS_TRANSITIONS,
    JobResource,
    JobStatus,
    UserJob,
)
from src.repository.user_job_repository import DuplicateJobNameError, UserJobRepository

# 유저 ID: 소문자·숫자·'-', 영숫자로 시작·끝, 1~58자(네임스페이스 user-{id}가 63자를 넘지 않도록)
_USER_ID_RE = re.compile(r"^[a-z0-9]([-a-z0-9]{0,56}[a-z0-9])?$")
# DNS-1123 label: job 이름 (1~63자)
_DNS_LABEL_RE = re.compile(r"^[a-z0-9]([-a-z0-9]{0,61}[a-z0-9])?$")
# DNS-1123 subdomain: 리소스 이름 (점으로 구분된 label, 전체 253자 이하)
_DNS_SUBDOMAIN_RE = re.compile(
    r"^[a-z0-9]([-a-z0-9]*[a-z0-9])?(\.[a-z0-9]([-a-z0-9]*[a-z0-9])?)*$"
)

# 동시 갱신으로 조건부 갱신이 어긋났을 때 다시 읽어 판단하는 최대 횟수
_STATUS_UPDATE_RETRIES = 3


def _is_user_id(value: Any) -> bool:
    return isinstance(value, str) and bool(_USER_ID_RE.fullmatch(value))


def _is_dns_label(value: Any) -> bool:
    return isinstance(value, str) and bool(_DNS_LABEL_RE.fullmatch(value))


def _is_dns_subdomain(value: Any) -> bool:
    return (
        isinstance(value, str)
        and len(value) <= 253
        and bool(_DNS_SUBDOMAIN_RE.fullmatch(value))
    )


# 매니페스트 목록을 검증해 JobResource로 바꾼다. namespace는 job 네임스페이스로 채운다.
def _build_resources(
    manifests: list[dict[str, Any]], namespace: str
) -> list[JobResource]:
    if not manifests:
        raise MyApiError(ErrorEnum.INVALID_JOB_RESOURCE)
    resources: list[JobResource] = []
    seen: set[tuple[str, str]] = set()
    for manifest in manifests:
        if not isinstance(manifest, dict) or not isinstance(
            manifest.get("metadata"), dict
        ):
            raise MyApiError(ErrorEnum.INVALID_JOB_RESOURCE)
        api_version = manifest.get("apiVersion")
        kind = manifest.get("kind")
        metadata = manifest["metadata"]
        name = metadata.get("name")
        # 문자열인지 먼저 본다. dict 같은 값은 해시가 안 돼 set 조회에서 TypeError(500)가 난다.
        if not isinstance(api_version, str) or not isinstance(kind, str):
            raise MyApiError(ErrorEnum.INVALID_JOB_RESOURCE)
        if (api_version, kind) not in ALLOWED_RESOURCE_KINDS or not _is_dns_subdomain(
            name
        ):
            raise MyApiError(ErrorEnum.INVALID_JOB_RESOURCE)
        if metadata.get("namespace") not in (None, namespace):
            raise MyApiError(ErrorEnum.INVALID_JOB_RESOURCE)
        if (kind, name) in seen:
            raise MyApiError(ErrorEnum.INVALID_JOB_RESOURCE)
        seen.add((kind, name))
        stored = {**manifest, "metadata": {**metadata, "namespace": namespace}}
        resources.append(
            JobResource(api_version=api_version, kind=kind, name=name, manifest=stored)
        )
    return resources


class UserJobService:
    """user-job 비즈니스 로직. MongoDB 접근은 주입받은 repository로만 한다."""

    def __init__(self, repository: UserJobRepository) -> None:
        self.repository = repository

    # 입력을 검증하고 pending 상태의 job을 저장한다. 클러스터 반영은 operator가 한다.
    async def create_job(
        self, owner_id: str, name: str, manifests: list[dict[str, Any]]
    ) -> UserJob:
        if not _is_user_id(owner_id) or not _is_dns_label(name):
            raise MyApiError(ErrorEnum.INVALID_PARAMETER)
        namespace = f"user-{owner_id}"
        resources = _build_resources(manifests, namespace)
        now = datetime.now(UTC)
        job_doc = {
            "owner_id": owner_id,
            "namespace": namespace,
            "name": name,
            "resources": [r.model_dump() for r in resources],
            "status": JobStatus.PENDING.value,
            "is_deleted": False,
            "created_at": now,
            "updated_at": now,
            "deleted_at": None,
        }
        try:
            return await self.repository.insert(job_doc)
        except DuplicateJobNameError as e:
            raise MyApiError(ErrorEnum.JOB_NAME_DUPLICATED) from e

    # 삭제되지 않은 자기 job을 최신순으로 반환한다.
    async def list_jobs(self, owner_id: str) -> list[UserJob]:
        return await self.repository.find_active_by_owner(owner_id)

    # 자기 job 하나를 반환한다. 남의 job·없음·삭제됨·잘못된 ID는 모두 JOB_NOT_FOUND.
    async def get_job(self, owner_id: str, job_id: str) -> UserJob:
        job = await self.repository.find_active_by_id(job_id)
        if job is None or job.owner_id != owner_id:
            raise MyApiError(ErrorEnum.JOB_NOT_FOUND)
        return job

    # operator 전용 상태 갱신. 같은 상태면 그대로 반환하고, 허용된 전이만 조건부로 원자적으로 바꾼다.
    async def update_job_status(self, job_id: str, status: JobStatus) -> UserJob:
        for _ in range(_STATUS_UPDATE_RETRIES):
            job = await self.repository.find_active_by_id(job_id)
            if job is None:
                raise MyApiError(ErrorEnum.JOB_NOT_FOUND)
            if job.status == status:
                return job
            if status not in ALLOWED_STATUS_TRANSITIONS[job.status]:
                raise MyApiError(ErrorEnum.INVALID_STATUS_TRANSITION)
            updated = await self.repository.update_status_if(
                job_id, job.status, status, datetime.now(UTC)
            )
            if updated is not None:
                return updated
            # 읽은 뒤 다른 갱신이 끼어들었다. 다시 읽어 판단한다.
        raise MyApiError(ErrorEnum.INVALID_STATUS_TRANSITION)

    # 자기 job을 soft delete한다. 클러스터 리소스 정리는 operator가 한다.
    async def delete_job(self, owner_id: str, job_id: str) -> None:
        deleted = await self.repository.soft_delete(owner_id, job_id, datetime.now(UTC))
        if not deleted:
            raise MyApiError(ErrorEnum.JOB_NOT_FOUND)
