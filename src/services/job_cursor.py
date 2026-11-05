import base64
import binascii
import re
from datetime import UTC, datetime

from src.core.exception.my_exception import ErrorEnum, MyApiError
from src.models.user_job_models import JobPosition

# job 목록 cursor ↔ 정렬 위치(created_at, id) 변환(docs/api-job-list/plan.md "cursor 인코딩").
# 형식: base64url("<created_at isoformat>|<id>"), padding 없음. 클라이언트에게는 불투명 문자열이다.
# 서명하지 않는다: 위치만 담고 소유자 조건은 항상 X-User-Id로 붙으므로, 조작해도 자기 job의 다른 위치를 볼 뿐이다.

# 이보다 긴 cursor는 디코딩하지 않고 거절한다. 실제 cursor는 70자 안팎이다.
_MAX_CURSOR_LENGTH = 256
# base64url 문자만(padding 없음). b64decode(altchars="-_")는 표준 문자 "+"·"/"도 받아 주므로 디코딩 전에 거른다.
_BASE64URL = re.compile(r"[A-Za-z0-9_-]+")
_SEPARATOR = "|"
# ObjectId 문자열(str(ObjectId)은 소문자 hex 24자리)
_OBJECT_ID = re.compile(r"[0-9a-f]{24}")


# 정렬 위치를 cursor 문자열로 만든다. isoformat은 마이크로초·타임존까지 그대로 왕복된다.
def encode_cursor(position: JobPosition) -> str:
    raw = f"{position.created_at.isoformat()}{_SEPARATOR}{position.id}"
    return base64.urlsafe_b64encode(raw.encode()).decode().rstrip("=")


# cursor 문자열을 정렬 위치로 푼다. 어느 단계에서든 형식이 틀리면 INVALID_CURSOR.
def decode_cursor(cursor: str) -> JobPosition:
    if len(cursor) > _MAX_CURSOR_LENGTH or not _BASE64URL.fullmatch(cursor):
        raise MyApiError(ErrorEnum.INVALID_CURSOR)
    try:
        # encode_cursor가 뗀 padding을 되붙인다. 길이가 base64로 불가능하면 binascii.Error.
        padded = cursor + "=" * (-len(cursor) % 4)
        raw = base64.urlsafe_b64decode(padded).decode()
        created_at_text, job_id = raw.split(_SEPARATOR)
        # UTC로 맞춘다. 타임존 없는 시각은 MongoDB의 UTC 시각과 비교할 수 없어 거절하고,
        # UTC로 바꾸면 datetime 범위(1~9999년)를 벗어나는 시각(예: 0001-01-01T00:00+14:00)은
        # OverflowError로 거절한다. 그대로 두면 MongoDB 쿼리 인코딩에서 터져 500이 된다.
        created_at = datetime.fromisoformat(created_at_text)
        if created_at.tzinfo is None:
            raise ValueError("timezone required")
        created_at = created_at.astimezone(UTC)
    except (binascii.Error, UnicodeDecodeError, ValueError, OverflowError) as e:
        raise MyApiError(ErrorEnum.INVALID_CURSOR) from e
    if not _OBJECT_ID.fullmatch(job_id):
        raise MyApiError(ErrorEnum.INVALID_CURSOR)
    return JobPosition(created_at=created_at, id=job_id)
