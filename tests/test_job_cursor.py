import base64
from datetime import UTC, datetime, timedelta, timezone

import pytest

from src.core.exception.my_exception import ErrorEnum, MyApiError
from src.models.user_job import JobPosition
from src.services.job_cursor import decode_cursor, encode_cursor

JOB_ID = "6720a1b2c3d4e5f6a7b8c9d0"


# 문자열을 padding 없는 base64url로 만든다(조작된 cursor 흉내).
def b64(raw: str) -> str:
    return base64.urlsafe_b64encode(raw.encode()).decode().rstrip("=")


# 인코딩한 위치가 그대로 돌아온다. 마이크로초·타임존(UTC 외 포함)도 유지된다.
@pytest.mark.parametrize(
    "created_at",
    [
        datetime(2026, 10, 29, 9, 0, tzinfo=UTC),
        datetime(2026, 10, 29, 9, 0, 0, 123456, tzinfo=UTC),
        datetime(2026, 10, 29, 18, 0, tzinfo=timezone(timedelta(hours=9))),
    ],
)
def test_round_trip(created_at: datetime) -> None:
    position = JobPosition(created_at=created_at, id=JOB_ID)
    cursor = encode_cursor(position)
    assert decode_cursor(cursor) == position
    # URL 쿼리에 그대로 넣을 수 있다(padding·+·/ 없음).
    assert not set(cursor) & {"=", "+", "/"}


@pytest.mark.parametrize(
    "cursor",
    [
        "",  # 빈 값(?cursor=)
        "x" * 257,  # 길이 초과
        "abc$",  # base64url 문자가 아님
        "a",  # base64 길이로 불가능
        base64.urlsafe_b64encode(b"\xff\xfe").decode(),  # UTF-8 아님
        b64(f"2026-10-29T09:00:00+00:00{JOB_ID}"),  # 구분자 없음
        b64(f"2026-10-29T09:00:00+00:00|{JOB_ID}|x"),  # 구분자가 둘
        b64(f"yesterday|{JOB_ID}"),  # 날짜 형식 아님
        b64(f"2026-10-29T09:00:00|{JOB_ID}"),  # 타임존 없음
        b64("2026-10-29T09:00:00+00:00|not-an-object-id"),  # id 형식 아님
        b64("2026-10-29T09:00:00+00:00|6720A1B2C3D4E5F6A7B8C9D0"),  # 대문자 hex
    ],
)
def test_invalid_cursor(cursor: str) -> None:
    with pytest.raises(MyApiError) as exc:
        decode_cursor(cursor)
    assert exc.value.error_enum == ErrorEnum.INVALID_CURSOR
