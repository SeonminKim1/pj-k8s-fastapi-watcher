import pytest

from src.core.db import mongodb


class FakeClient:
    def __init__(self) -> None:
        self.closed = False

    async def close(self) -> None:
        self.closed = True


# close_client()는 공유 클라이언트를 닫고 비워서, 다음 get_client()가 새로 만들게 한다.
async def test_close_client(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakeClient()
    monkeypatch.setattr(mongodb, "_client", fake)
    await mongodb.close_client()
    assert fake.closed is True
    assert mongodb._client is None


# 만들어진 클라이언트가 없으면 아무것도 하지 않는다.
async def test_close_client_without_client(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(mongodb, "_client", None)
    await mongodb.close_client()
    assert mongodb._client is None
