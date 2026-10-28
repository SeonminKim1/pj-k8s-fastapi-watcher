from pydantic import BaseModel, Field


class ErrorResponse(BaseModel):
    """모든 에러 응답의 형태. /docs에 400·404·500 응답 모양을 보여 주는 데 쓴다."""

    code: str = Field(
        description="에러 종류(ErrorEnum의 code). 클라이언트는 이 값으로 분기한다"
    )
    message: str = Field(description="사람이 읽는 설명")
