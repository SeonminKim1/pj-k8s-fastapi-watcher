import re
from collections.abc import Callable
from typing import Annotated, Any

from pydantic import AfterValidator, Field

# 형식 규칙을 한 곳에 모은다. schema·model은 Annotated 타입을, service는 is_* 함수를 쓴다.

# 유저 ID: 소문자·숫자·'-', 영숫자로 시작·끝, 1~58자(네임스페이스 user-{id}가 63자를 넘지 않도록)
_USER_ID_RE = re.compile(r"[a-z0-9]([-a-z0-9]{0,56}[a-z0-9])?")
# DNS-1035 label: job 이름 (영문 소문자로 시작, 1~63자). Service 이름으로 그대로 쓰인다.
_DNS_1035_LABEL_RE = re.compile(r"[a-z]([-a-z0-9]{0,61}[a-z0-9])?")
# 환경 변수 이름: C 식별자 형식, 1~63자
_ENV_NAME_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]{0,62}")

# 이미지 참조: [레지스트리[:포트]/]경로[:태그][@sha256:digest]
# - 레지스트리: 호스트명(점으로 구분) + 선택 포트. 경로 앞부분에 '/'가 있어야 레지스트리로 본다.
# - 경로 구성요소: 소문자·숫자, 구분자는 '.', '_', '__', '-'(연속 가능)
_IMAGE_DOMAIN = r"[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?)*(?::[0-9]+)?"
_IMAGE_COMPONENT = r"[a-z0-9]+(?:(?:[._]|__|-+)[a-z0-9]+)*"
_IMAGE_RE = re.compile(
    rf"(?:{_IMAGE_DOMAIN}/)?{_IMAGE_COMPONENT}(?:/{_IMAGE_COMPONENT})*"
    r"(?::(?P<tag>[A-Za-z0-9_][A-Za-z0-9_.-]{0,127}))?"
    r"(?:@(?P<digest>sha256:[a-f0-9]{64}))?"
)
_IMAGE_MAX_LENGTH = 512


# 유저 ID 형식인지 본다. 문자열이 아니면 False.
def is_user_id(value: Any) -> bool:
    return isinstance(value, str) and bool(_USER_ID_RE.fullmatch(value))


# DNS-1035 label(job 이름)인지 본다. 문자열이 아니면 False.
def is_dns_1035_label(value: Any) -> bool:
    return isinstance(value, str) and bool(_DNS_1035_LABEL_RE.fullmatch(value))


# 환경 변수 이름 형식인지 본다.
def is_env_name(value: Any) -> bool:
    return isinstance(value, str) and bool(_ENV_NAME_RE.fullmatch(value))


# 이미지 참조인지 본다. 태그나 digest가 꼭 있어야 하고 태그 latest는 안 된다
# (imagePullPolicy: IfNotPresent라 latest면 노드마다 다른 이미지가 돌 수 있다).
def is_pinned_image(value: Any) -> bool:
    if not isinstance(value, str) or len(value) > _IMAGE_MAX_LENGTH:
        return False
    m = _IMAGE_RE.fullmatch(value)
    if m is None:
        return False
    tag, digest = m.group("tag"), m.group("digest")
    if tag is None and digest is None:
        return False
    return tag != "latest"


# is_* 함수를 pydantic 검증기로 감싼다. 틀리면 ValueError(→ pydantic ValidationError).
def _validator(check: Callable[[Any], bool], message: str) -> AfterValidator:
    def validate(value: str) -> str:
        if not check(value):
            raise ValueError(message)
        return value

    return AfterValidator(validate)


UserId = Annotated[
    str,
    _validator(is_user_id, "유저 ID 형식이 아닙니다."),
    Field(description="유저 ID. 소문자·숫자·'-', 영숫자로 시작·끝, 1~58자"),
]
DnsLabel1035 = Annotated[
    str,
    _validator(is_dns_1035_label, "DNS-1035 label 형식이 아닙니다."),
    Field(
        description="DNS-1035 label. 영문 소문자로 시작, 소문자·숫자·'-', 영숫자로 끝, 1~63자"
    ),
]
ImageRef = Annotated[
    str,
    _validator(is_pinned_image, "태그나 digest가 있는 이미지 참조가 아닙니다."),
    Field(
        description="컨테이너 이미지 참조 [레지스트리[:포트]/]경로(:태그|@sha256:digest), 1~512자. 태그나 digest 필수, latest 불가"
    ),
]
EnvName = Annotated[
    str,
    _validator(is_env_name, "환경 변수 이름 형식이 아닙니다."),
    Field(description="환경 변수 이름. [A-Za-z_][A-Za-z0-9_]*, 1~63자"),
]
