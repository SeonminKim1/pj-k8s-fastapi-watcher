import os

from pymongo import MongoClient
from pymongo.database import Database

# 접속 정보는 환경 변수에서 읽고, 없으면 로컬 기본값을 쓴다.
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
MONGO_DB_NAME = os.getenv("MONGO_DB_NAME", "k8s_client")

# MongoClient는 내부에 커넥션 풀을 가지므로 프로세스당 하나만 만들어 재사용한다.
_client: MongoClient | None = None


# 공유 MongoClient를 지연 생성해서 반환한다.
def get_client() -> MongoClient:
    global _client
    if _client is None:
        _client = MongoClient(MONGO_URI)
    return _client


# repository에서 사용할 기본 데이터베이스 핸들을 반환한다.
def get_database() -> Database:
    return get_client()[MONGO_DB_NAME]
