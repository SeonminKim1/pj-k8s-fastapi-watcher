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


# 상태 코드 하나의 에러 응답 문서: 모양(ErrorResponse)과 대표 example 하나.
def _error_doc(description: str, example: ErrorResponse) -> dict[str, Any]:
    return {
        "model": ErrorResponse,
        "description": description,
        "content": {"application/json": {"example": example.model_dump()}},
    }


_BAD_REQUEST = ErrorEnum.INVALID_PARAMETER

# 라우터 공통 에러 응답(APIRouter(responses=...)). 엔드포인트별 code 목록은 각 기능의 spec.md "에러 케이스"가 기준이다.
COMMON_ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    400: _error_doc(
        "잘못된 요청·규칙 위반. code로 구분한다(목록은 엔드포인트 설명의 spec 참고)",
        ErrorResponse(code=_BAD_REQUEST.code, message=_BAD_REQUEST.message),
    ),
    500: _error_doc("서버 내부 오류(db_error, unknown_error)", DB_ERROR),
}
