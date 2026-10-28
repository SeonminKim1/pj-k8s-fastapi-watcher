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

    def __init__(self, collection: AsyncCollection) -> None:
        self.collection = collection

    # 삭제되지 않은 job끼리 이름 유니크, 유저별 목록 조회용 인덱스를 만든다(이미 있으면 그대로).
    async def ensure_indexes(self) -> None:
        await self.collection.create_index(
            [("owner_id", 1), ("name", 1)],
            name="uniq_owner_name",
            unique=True,
            partialFilterExpression={"is_deleted": False},
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
            raise DuplicateJobNameError from e
        doc["_id"] = result.inserted_id
        return _to_model(doc)

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

    # 현재 상태가 from_status일 때만 to_status로 원자적으로 바꾼다. 조건이 어긋나면 None.
    async def update_status_if(
        self, job_id: str, from_status: JobStatus, to_status: JobStatus, now: datetime
    ) -> UserJob | None:
        oid = _to_object_id(job_id)
        if oid is None:
            return None
        doc = await self.collection.find_one_and_update(
            {"_id": oid, "is_deleted": False, "status": from_status.value},
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
