from enum import Enum


class ErrorEnum(Enum):
    """비즈니스 에러 종류별로 (코드, HTTP 상태 코드, 메시지)를 한 번에 정의한다."""

    INVALID_PARAMETER = ("invalid_parameter", 400, "요청 값이 유효하지 않습니다.")

    def __init__(self, code: str, status_code: int, message: str) -> None:
        self.code = code
        self.status_code = status_code
        self.message = message


class MyApiError(Exception):
    """services에서 발생시키는 모든 비즈니스 에러는 이 예외로 감싸서 던진다."""

    def __init__(self, error_enum: ErrorEnum) -> None:
        self.error_enum = error_enum
        super().__init__(error_enum.message)
