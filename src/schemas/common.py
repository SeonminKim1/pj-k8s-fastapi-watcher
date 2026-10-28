from typing import Annotated

from fastapi import Header

from src.models.k8s_names import UserId

# 게이트웨이가 넣어 주는 유저 ID 헤더. 형식이 틀리거나 없으면 400 invalid_user_id.
# 라우터는 schemas/만 참조하므로 헤더 타입도 여기에 둔다. 다른 라우터도 같은 타입을 쓴다.
UserIdHeader = Annotated[UserId, Header(alias="X-User-Id")]
