from collections.abc import Collection
from datetime import datetime
from typing import Any

from bson import ObjectId
from bson.errors import InvalidId
from pymongo import DESCENDING, ReturnDocument
from pymongo.asynchronous.collection import AsyncCollection
from pymongo.errors import DuplicateKeyError

from src.models.user_job import JobStatus, UserJob


class DuplicateJobNameError(Exception):
    """삭제되지 않은 job 중 (owner_id, name)이 겹쳐 유니크 인덱스에 걸렸을 때 발생한다."""


class JobQuotaExceededError(Exception):
    """유저의 삭제되지 않은 job이 슬롯 수만큼 있어 더 저장할 수 없을 때 발생한다."""


# 이름 유니크 인덱스(uniq_owner_name)의 키. 중복 에러가 이 인덱스에서 났는지 구분할 때 쓴다.
_OWNER_NAME_KEY = {"owner_id": 1, "name": 1}
# 개수 한도 슬롯 유니크 인덱스(uniq_owner_slot)의 키. 동시 요청과 슬롯이 겹쳤는지 구분할 때 쓴다.
_OWNER_SLOT_KEY = {"owner_id": 1, "quota_slot": 1}


# 문자열 ID를 ObjectId로 바꾼다. 형식이 틀리면 None(= 없는 job으로 취급).
def _to_object_id(job_id: str) -> ObjectId | None:
    try:
        return ObjectId(job_id)
    except (InvalidId, TypeError):
        return None


# MongoDB 문서를 UserJob으로 바꾼다(_id → id).
def _to_model(doc: dict[str, Any]) -> UserJob:
    return UserJob(id=str(doc.pop("_id")), **doc)


class UserJobRepository:
    """user_jobs 컬렉션 접근만 담당한다. 비즈니스 판단은 service가 한다."""

    # user_jobs 컬렉션을 주입받는다(조립은 core/dependencies.py).
    def __init__(self, collection: AsyncCollection) -> None:
        self.collection = collection

    # 삭제되지 않은 job끼리 이름 유니크·슬롯 유니크, 유저별 목록 조회용 인덱스를 만든다(이미 있으면 그대로).
    async def ensure_indexes(self) -> None:
        await self.collection.create_index(
            [("owner_id", 1), ("name", 1)],
            name="uniq_owner_name",
            unique=True,
            partialFilterExpression={"is_deleted": False},
        )
        # quota_slot이 없는 문서는 빼서, 없는 값(null)끼리 중복으로 걸리지 않게 한다.
        await self.collection.create_index(
            [("owner_id", 1), ("quota_slot", 1)],
            name="uniq_owner_slot",
            unique=True,
            partialFilterExpression={
                "is_deleted": False,
                "quota_slot": {"$exists": True},
            },
        )
        await self.collection.create_index(
            [("owner_id", 1), ("created_at", DESCENDING)],
            name="owner_created_at",
        )

    # 새 job 문서를 저장한다. 이름이 겹치면 DuplicateJobNameError.
    async def insert(self, job_doc: dict[str, Any]) -> UserJob:
        doc = dict(job_doc)
        try:
            result = await self.collection.insert_one(doc)
        except DuplicateKeyError as e:
            # 이름 인덱스 위반만 이름 중복으로 바꾼다. 다른 유니크 위반은 그대로 올려 500(db_error)으로 처리된다.
            if (e.details or {}).get("keyPattern") == _OWNER_NAME_KEY:
                raise DuplicateJobNameError from e
            raise
        doc["_id"] = result.inserted_id
        return _to_model(doc)

    # 삭제되지 않은 job이 차지한 슬롯 번호들.
    async def _used_slots(self, owner_id: str) -> set[int]:
        cursor = self.collection.find(
            {
                "owner_id": owner_id,
                "is_deleted": False,
                "quota_slot": {"$exists": True},
            },
            {"quota_slot": 1, "_id": 0},
        )
        return {doc["quota_slot"] async for doc in cursor}

    # 빈 슬롯(0 ~ max_slots-1)을 골라 새 job 문서를 저장한다. 슬롯 유니크 인덱스가 개수 한도를 지킨다.
    # - 빈 슬롯이 없으면 JobQuotaExceededError
    # - 동시 요청과 슬롯이 겹치면 다시 골라 재시도. 겹칠 때마다 다른 요청이 슬롯을 하나 차지한 것이므로
    #   max_slots번 겹치면 슬롯이 다 찬 것으로 보고 JobQuotaExceededError
    # - 이름이 겹치면 DuplicateJobNameError, 그 외 유니크 위반은 그대로 올려 500(db_error)
    async def insert_with_slot(
        self, job_doc: dict[str, Any], max_slots: int
    ) -> UserJob:
        owner_id = job_doc["owner_id"]
        for _ in range(max_slots):
            used = await self._used_slots(owner_id)
            slot = next((s for s in range(max_slots) if s not in used), None)
            if slot is None:
                raise JobQuotaExceededError
            doc = {**job_doc, "quota_slot": slot}
            try:
                result = await self.collection.insert_one(doc)
            except DuplicateKeyError as e:
                key_pattern = (e.details or {}).get("keyPattern")
                if key_pattern == _OWNER_NAME_KEY:
                    raise DuplicateJobNameError from e
                if key_pattern == _OWNER_SLOT_KEY:
                    continue
                raise
            doc["_id"] = result.inserted_id
            return _to_model(doc)
        raise JobQuotaExceededError

    # 유저의 삭제되지 않은 job을 최신순으로 반환한다.
    async def find_active_by_owner(self, owner_id: str) -> list[UserJob]:
        cursor = self.collection.find({"owner_id": owner_id, "is_deleted": False}).sort(
            "created_at", DESCENDING
        )
        return [_to_model(doc) async for doc in cursor]

    # 삭제되지 않은 job 하나를 찾는다. 잘못된 ID·없음·삭제됨이면 None.
    async def find_active_by_id(self, job_id: str) -> UserJob | None:
        oid = _to_object_id(job_id)
        if oid is None:
            return None
        doc = await self.collection.find_one({"_id": oid, "is_deleted": False})
        return _to_model(doc) if doc else None

    # 현재 상태가 from_statuses 중 하나일 때만 to_status로 원자적으로 바꾼다. 조건이 어긋나면 None.
    async def update_status_from(
        self,
        job_id: str,
        from_statuses: Collection[JobStatus],
        to_status: JobStatus,
        now: datetime,
    ) -> UserJob | None:
        oid = _to_object_id(job_id)
        if oid is None:
            return None
        doc = await self.collection.find_one_and_update(
            {
                "_id": oid,
                "is_deleted": False,
                "status": {"$in": [s.value for s in from_statuses]},
            },
            {"$set": {"status": to_status.value, "updated_at": now}},
            return_document=ReturnDocument.AFTER,
        )
        return _to_model(doc) if doc else None

    # 자기 job이고 삭제되지 않았을 때만 soft delete한다. 실제로 바뀌었으면 True.
    async def soft_delete(self, owner_id: str, job_id: str, now: datetime) -> bool:
        oid = _to_object_id(job_id)
        if oid is None:
            return False
        result = await self.collection.update_one(
            {"_id": oid, "owner_id": owner_id, "is_deleted": False},
            {"$set": {"is_deleted": True, "deleted_at": now, "updated_at": now}},
        )
        return result.modified_count == 1
