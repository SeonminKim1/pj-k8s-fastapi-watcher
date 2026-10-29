from typing import Any

from pydantic import BaseModel, Field

from src.core.exception.my_exception import ErrorEnum


class ErrorResponse(BaseModel):
    """모든 에러 응답의 형태. /docs에 400·404·500 응답 모양을 보여 주는 데 쓴다."""

    code: str = Field(
        description="에러 종류(ErrorEnum의 code). 클라이언트는 이 값으로 분기한다"
    )
    message: str = Field(description="사람이 읽는 설명")


# 전역 예외 핸들러(main.py)가 응답하는 500 에러. ErrorEnum이 아니므로 응답 본문을 여기에 두고
# 핸들러와 /docs example이 함께 쓴다.
DB_ERROR = ErrorResponse(code="db_error", message="데이터베이스 오류가 발생했습니다.")
UNKNOWN_ERROR = ErrorResponse(
    code="unknown_error", message="알 수 없는 오류가 발생했습니다."
)
SERVER_ERRORS: list[ErrorResponse] = [DB_ERROR, UNKNOWN_ERROR]


# 에러 응답 목록을 OpenAPI media type examples로 바꾼다(code마다 example 하나, 이름은 code).
def _examples(errors: list[ErrorResponse]) -> dict[str, dict[str, Any]]:
    return {e.code: {"summary": e.code, "value": e.model_dump()} for e in errors}


# 라우터 responses에 넣을 에러 응답 문서. 엔드포인트가 낼 수 있는 ErrorEnum을 상태 코드별로 묶어
# /docs·/redoc에 code별 example로 보여 준다. 500(SERVER_ERRORS)은 모든 엔드포인트에 붙인다.
def error_responses(*errors: ErrorEnum) -> dict[int | str, dict[str, Any]]:
    by_status: dict[int, list[ErrorResponse]] = {}
    for e in errors:
        by_status.setdefault(e.status_code, []).append(
            ErrorResponse(code=e.code, message=e.message)
        )
    by_status[500] = SERVER_ERRORS
    return {
        status: {
            "model": ErrorResponse,
            "content": {"application/json": {"examples": _examples(items)}},
        }
        for status, items in sorted(by_status.items())
    }
