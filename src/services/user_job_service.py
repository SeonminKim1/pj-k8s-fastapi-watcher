from datetime import UTC, datetime
from typing import Any

from src.core.exception.my_exception import ErrorEnum, MyApiError
from src.models.enums import JobStatus
from src.models.k8s_names import is_dns_1035_label, is_user_id
from src.models.user_job import (
    ALLOWED_STATUS_TRANSITIONS,
    JOB_LIST_DEFAULT_LIMIT,
    JOB_LIST_MAX_LIMIT,
    MAX_JOBS_PER_USER,
    JobPage,
    JobPosition,
    JobTemplate,
    UserJob,
)
from src.repository.user_job_repository import (
    DuplicateJobNameError,
    JobQuotaExceededError,
    UserJobRepository,
)
from src.services.job_cursor import decode_cursor, encode_cursor
from src.services.job_templates import build_resources


# 유저 ID 형식이 틀리면 INVALID_USER_ID(400). owner_id를 받는 모든 메서드의 첫 검사다.
def _validate_user_id(owner_id: Any) -> None:
    if not is_user_id(owner_id):
        raise MyApiError(ErrorEnum.INVALID_USER_ID)


# job 이름이 DNS-1035 label이 아니면 INVALID_JOB_NAME(400).
def _validate_job_name(name: Any) -> None:
    if not is_dns_1035_label(name):
        raise MyApiError(ErrorEnum.INVALID_JOB_NAME)


# 목록 limit이 1~JOB_LIST_MAX_LIMIT 정수가 아니면 INVALID_LIMIT(400). bool은 int의 하위 타입이라 따로 막는다.
def _validate_limit(limit: Any) -> None:
    if (
        not isinstance(limit, int)
        or isinstance(limit, bool)
        or not 1 <= limit <= JOB_LIST_MAX_LIMIT
    ):
        raise MyApiError(ErrorEnum.INVALID_LIMIT)


class UserJobService:
    """user-job 비즈니스 로직. MongoDB 접근은 주입받은 repository로만 한다."""

    # MongoDB 접근에 쓸 repository를 주입받는다(테스트는 가짜 repository).
    def __init__(self, repository: UserJobRepository) -> None:
        self.repository = repository

    # 템플릿으로 매니페스트를 만들어 pending 상태의 job을 저장한다. 클러스터 반영은 operator가 한다.
    # owner_id·name은 schema를 거치지 않는 호출자를 위해 다시 검사한다. template은 이미 검증된 모델이다.
    # 검사 순서: 형식 → 개수 한도(JOB_QUOTA_EXCEEDED) → 이름 중복(JOB_NAME_DUPLICATED). 한도·중복은 저장 시 인덱스로 판단한다.
    async def create_job(
        self, owner_id: str, name: str, template: JobTemplate
    ) -> UserJob:
        _validate_user_id(owner_id)
        _validate_job_name(name)
        namespace = f"user-{owner_id}"
        resources = build_resources(name=name, namespace=namespace, template=template)
        now = datetime.now(UTC)
        job_doc = {
            "owner_id": owner_id,
            "namespace": namespace,
            "name": name,
            "template": template.model_dump(mode="json"),
            "resources": [r.model_dump() for r in resources],
            "status": JobStatus.PENDING.value,
            "is_deleted": False,
            "created_at": now,
            "updated_at": now,
            "deleted_at": None,
        }
        try:
            return await self.repository.insert_with_slot(job_doc, MAX_JOBS_PER_USER)
        except JobQuotaExceededError as e:
            raise MyApiError(ErrorEnum.JOB_QUOTA_EXCEEDED) from e
        except DuplicateJobNameError as e:
            raise MyApiError(ErrorEnum.JOB_NAME_DUPLICATED) from e

    # 삭제되지 않은 자기 job을 최신순(created_at 내림차순, 같으면 id 내림차순)으로 최대 limit개 반환한다.
    # cursor는 직전 페이지 마지막 항목의 위치이고, status가 있으면 그 상태만 돌려준다(docs/api-job-list/spec.md).
    # limit + 1개를 읽어 다음 페이지에 항목이 실제로 있을 때만 next_cursor를 준다.
    # 검사 순서: owner_id(INVALID_USER_ID) → limit(INVALID_LIMIT) → cursor(INVALID_CURSOR).
    async def list_jobs(
        self,
        owner_id: str,
        limit: int = JOB_LIST_DEFAULT_LIMIT,
        cursor: str | None = None,
        status: JobStatus | None = None,
    ) -> JobPage:
        _validate_user_id(owner_id)
        _validate_limit(limit)
        after = decode_cursor(cursor) if cursor is not None else None
        jobs = await self.repository.find_active_page(
            owner_id=owner_id, status=status, after=after, limit=limit + 1
        )
        if len(jobs) <= limit:
            return JobPage(items=jobs, next_cursor=None)
        items = jobs[:limit]
        last = JobPosition(created_at=items[-1].created_at, id=items[-1].id)
        return JobPage(items=items, next_cursor=encode_cursor(last))

    # 자기 job 하나를 반환한다. 유저 ID 형식 오류는 INVALID_USER_ID, 남의 job·없음·삭제됨·잘못된 ID는 모두 JOB_NOT_FOUND.
    async def get_job(self, owner_id: str, job_id: str) -> UserJob:
        _validate_user_id(owner_id)
        job = await self.repository.find_active_by_id(job_id)
        if job is None or job.owner_id != owner_id:
            raise MyApiError(ErrorEnum.JOB_NOT_FOUND)
        return job

    # operator 전용 상태 갱신. 목표 상태로 갈 수 있는 이전 상태일 때만 한 번의 조건부 갱신으로 원자적으로 바꾼다.
    # 갱신되지 않았을 때만 다시 읽어 이유를 판단한다: 없음·삭제됨 → JOB_NOT_FOUND, 이미 같은 상태 → 그대로 반환(멱등),
    # 그 외 → INVALID_STATUS_TRANSITION.
    async def update_job_status(self, job_id: str, status: JobStatus) -> UserJob:
        sources = [
            s for s, targets in ALLOWED_STATUS_TRANSITIONS.items() if status in targets
        ]
        updated = await self.repository.update_status_from(
            job_id=job_id,
            from_statuses=sources,
            to_status=status,
            now=datetime.now(UTC),
        )
        if updated is not None:
            return updated
        job = await self.repository.find_active_by_id(job_id)
        if job is None:
            raise MyApiError(ErrorEnum.JOB_NOT_FOUND)
        if job.status == status:
            return job
        raise MyApiError(ErrorEnum.INVALID_STATUS_TRANSITION)

    # 자기 job을 soft delete한다. 클러스터 리소스 정리는 operator가 한다.
    async def delete_job(self, owner_id: str, job_id: str) -> None:
        _validate_user_id(owner_id)
        deleted = await self.repository.soft_delete(
            owner_id=owner_id, job_id=job_id, now=datetime.now(UTC)
        )
        if not deleted:
            raise MyApiError(ErrorEnum.JOB_NOT_FOUND)
