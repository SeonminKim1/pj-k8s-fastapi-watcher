from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pymongo.errors import PyMongoError

from src.core.db.mongodb import close_client
from src.core.dependencies import (
    close_k8s_service,
    get_k8s_service,
    get_user_job_repository,
)
from src.core.exception.my_exception import ErrorEnum, MyApiError
from src.core.exception.validation_error import to_error_enum
from src.models.k8s_names import is_user_id
from src.routers import job_router
from src.schemas.error import DB_ERROR, UNKNOWN_ERROR


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
app.include_router(job_router.router)


# FastAPI는 OpenAPI에 422(HTTPValidationError)를 자동으로 넣지만, 이 서비스는 검증 에러를 400으로 바꿔 응답한다.
# /docs가 실제 응답과 같도록 기본 OpenAPI를 만든 뒤 422 응답과 그 스키마를 뺀다. 결과는 FastAPI처럼 캐시한다.
def _openapi_without_422() -> dict[str, Any]:
    if app.openapi_schema is not None:
        return app.openapi_schema
    schema = FastAPI.openapi(app)
    for path_item in schema.get("paths", {}).values():
        for operation in path_item.values():
            operation.get("responses", {}).pop("422", None)
    schemas = schema.get("components", {}).get("schemas", {})
    for name in ("HTTPValidationError", "ValidationError"):
        schemas.pop(name, None)
    app.openapi_schema = schema
    return schema


app.openapi = _openapi_without_422  # type: ignore[method-assign]


# MyApiError는 error_enum에 담긴 상태 코드로 구조화된 JSON 응답을 돌려준다.
@app.exception_handler(MyApiError)
async def my_api_error_handler(request: Request, exc: MyApiError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.error_enum.status_code,
        content={"code": exc.error_enum.code, "message": exc.error_enum.message},
    )


# 요청 검증 에러(FastAPI 기본 422)는 400으로 바꾸고, 첫 번째(우선순위가 가장 높은) 에러 하나를
# 필드별 ErrorEnum의 code·message로 알려준다(CLAUDE.md "에러 상태 코드": 400/404/500만 쓴다).
# body JSON 파싱이 실패하면 FastAPI는 헤더를 검증하지 않고 멈추므로, 그때는 X-User-Id를 직접 확인해
# 우선순위 1인 invalid_user_id를 먼저 알려준다.
@app.exception_handler(RequestValidationError)
async def validation_error_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    errors = exc.errors()
    json_invalid = any(e.get("type") == "json_invalid" for e in errors)
    if json_invalid and not is_user_id(request.headers.get("X-User-Id")):
        error = ErrorEnum.INVALID_USER_ID
    else:
        error = to_error_enum(errors)
    return JSONResponse(
        status_code=error.status_code,
        content={"code": error.code, "message": error.message},
    )


# MongoDB 에러는 500 db_error로 응답한다.
@app.exception_handler(PyMongoError)
async def db_error_handler(request: Request, exc: PyMongoError) -> JSONResponse:
    return JSONResponse(status_code=500, content=DB_ERROR.model_dump())


# 그 외 모든 예외는 500 unknown_error로 통일한다.
@app.exception_handler(Exception)
async def unknown_error_handler(request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(status_code=500, content=UNKNOWN_ERROR.model_dump())
