from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pymongo.errors import PyMongoError

from src.core.db.mongodb import close_client
from src.core.dependencies import (
    close_k8s_service,
    get_k8s_service,
    get_user_job_repository,
)
from src.core.exception.my_exception import MyApiError


# 앱 시작 시 클러스터 설정을 읽고 컬렉션 인덱스를 만든다(이미 있으면 그대로).
# 클러스터 설정(in-cluster·kubeconfig)이나 MongoDB가 없으면 앱이 뜨지 않는다.
# 시작 도중 실패해도 이미 만든 연결(MongoDB, K8s ApiClient)은 finally에서 닫는다.
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    try:
        get_k8s_service()
        await get_user_job_repository().ensure_indexes()
        yield
    finally:
        await close_client()
        close_k8s_service()


app = FastAPI(lifespan=lifespan)


# MyApiError는 error_enum에 담긴 상태 코드로 구조화된 JSON 응답을 돌려준다.
@app.exception_handler(MyApiError)
async def my_api_error_handler(request: Request, exc: MyApiError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.error_enum.status_code,
        content={"code": exc.error_enum.code, "message": exc.error_enum.message},
    )


# MongoDB 에러는 500 db_error로 응답한다.
@app.exception_handler(PyMongoError)
async def db_error_handler(request: Request, exc: PyMongoError) -> JSONResponse:
    return JSONResponse(
        status_code=500,
        content={"code": "db_error", "message": "데이터베이스 오류가 발생했습니다."},
    )


# 그 외 모든 예외는 500 unknown_error로 통일한다.
@app.exception_handler(Exception)
async def unknown_error_handler(request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(
        status_code=500,
        content={"code": "unknown_error", "message": "알 수 없는 오류가 발생했습니다."},
    )
