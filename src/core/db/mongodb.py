import os

from pymongo import AsyncMongoClient
from pymongo.asynchronous.database import AsyncDatabase

# 접속 정보는 환경 변수에서 읽고, 없으면 로컬 기본값을 쓴다.
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
MONGO_DB_NAME = os.getenv("MONGO_DB_NAME", "k8s_client")

# AsyncMongoClient는 내부에 커넥션 풀을 가지므로 프로세스당 하나만 만들어 재사용한다.
_client: AsyncMongoClient | None = None


# 공유 AsyncMongoClient를 지연 생성해서 반환한다. 시각은 UTC aware datetime으로 읽는다.
def get_client() -> AsyncMongoClient:
    global _client
    if _client is None:
        _client = AsyncMongoClient(MONGO_URI, tz_aware=True)
    return _client


# 앱 종료 시 커넥션 풀을 닫는다. 다시 get_client()를 부르면 새로 만든다.
async def close_client() -> None:
    global _client
    if _client is not None:
        await _client.close()
        _client = None


# repository에서 사용할 기본 데이터베이스 핸들을 반환한다.
def get_database() -> AsyncDatabase:
    return get_client()[MONGO_DB_NAME]
