from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pymongo.errors import PyMongoError

from src.core.exception.my_exception import MyApiError

app = FastAPI()


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
