import base64
from datetime import UTC, datetime, timedelta, timezone

import pytest

from src.core.exception.my_exception import ErrorEnum, MyApiError
from src.models.user_job_models import JobPosition
from src.services.job_cursor import decode_cursor, encode_cursor

JOB_ID = "6720a1b2c3d4e5f6a7b8c9d0"


# 문자열을 padding 없는 base64url로 만든다(조작된 cursor 흉내).
def b64(raw: str) -> str:
    return base64.urlsafe_b64encode(raw.encode()).decode().rstrip("=")


# 인코딩한 위치가 같은 시각으로 돌아온다(UTC로 맞춰짐). 마이크로초도 유지된다.
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
    decoded = decode_cursor(cursor)
    assert decoded == position
    assert decoded.created_at.utcoffset() == timedelta(0)
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
        # UTC로 바꾸면 datetime 범위 밖(MongoDB 쿼리에서 OverflowError → 500이 되던 값, 리뷰 1)
        b64(f"0001-01-01T00:00:00+14:00|{JOB_ID}"),
        b64(f"9999-12-31T23:59:59-14:00|{JOB_ID}"),
        "+/+/",  # 표준 base64 문자(b64decode altchars가 받아 주던 값, 리뷰 3)
        b64(f"2026-10-29T09:00:00+00:00|{JOB_ID}") + "=",  # padding
    ],
)
def test_invalid_cursor(cursor: str) -> None:
    with pytest.raises(MyApiError) as exc:
        decode_cursor(cursor)
    assert exc.value.error_enum == ErrorEnum.INVALID_CURSOR
