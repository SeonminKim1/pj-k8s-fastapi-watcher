# FastAPI SDD 프로젝트 템플릿

도메인과 무관한 FastAPI 백엔드 공통 규칙과 SDD(Spec-Driven Development) 작업 규칙이다.
아래 **SDD 세트** 네 파일만 옮기면 새 프로젝트를 시작할 수 있다.

| 파일 | 역할 |
|---|---|
| `docs/fastapi-sdd-template.md` | 코드 규칙, SDD 작업 규칙, 부트스트랩 절차 (이 파일) |
| `sdd-process.md` | 단계별 진행 기준, 문서 템플릿, 문서 관리 규칙 |
| `.claude/skills/feat/SKILL.md` | `/feat` 스킬: 기능 추가/수정 진행 (같은 폴더의 `github.md`: GitHub Project 연동 명령) |
| `.claude/settings.json` | Claude Code 권한 설정(`uv` 명령 허용, 위험 명령 차단) |

새 프로젝트로 옮기기(경로를 유지한 채 복사):
```bash
tar -cf - docs/fastapi-sdd-template.md sdd-process.md .claude/skills/feat .claude/settings.json | tar -xf - -C <새 프로젝트 경로>
```
세트의 파일을 고칠 때는 네 파일이 서로 참조하는 경로·용어가 어긋나지 않게 함께 확인한다.

> **Claude에게**: `src/`가 없는 프로젝트라면 아래 "부트스트랩" 섹션을 먼저 수행한다. `/init`으로 호출된 경우도 포함한다.

## 문서별 역할
| 파일 | 읽는 대상 | 담는 내용 | 담지 않는 내용 |
|---|---|---|---|
| `README.md` | 사람(처음 보는 개발자) | 서비스 소개, 실행 방법, 환경 변수, API 목록, 다른 문서 링크 | 코딩 규칙, 요구사항 상세 |
| `CLAUDE.md` | Claude(매 세션 자동 로드) | 프로젝트 개요, 프로젝트 고유 구성, 서비스 전체 요구사항, 이 템플릿 import | 실행 방법, 공통 규칙 본문(→ 이 파일) |
| `docs/fastapi-sdd-template.md` | Claude | 프로젝트와 무관한 공통 코드 규칙, SDD 작업 규칙 | 특정 프로젝트 내용 |
| `sdd-process.md` | 사람 + Claude | 단계별 진행 기준과 문서 템플릿 | 코드 규칙 |
| `docs/<feature-name>/*.md` | 사람 + Claude | 기능 하나의 PRD~구현 기록 | 서비스 전체 요구사항(→ `CLAUDE.md`) |
| `.claude/skills/feat/SKILL.md` | Claude | `/feat` 실행 절차 | 단계별 문서 템플릿(→ `sdd-process.md`) |
| `.claude/skills/feat/github.md` | Claude | GitHub Project 연동 `gh` 명령(이슈·상태·PR) | 연동 시점·규칙(→ `sdd-process.md`) |
| `.claude/settings.json` | Claude Code | 팀 공통 권한 설정 | 개인 설정(→ `.claude/settings.local.json`) |

- 같은 내용을 두 군데에 쓰지 않는다. 필요하면 링크(README) 또는 `@import`(CLAUDE.md)로 연결한다.
- `CLAUDE.md`는 매 세션 컨텍스트에 들어가므로 짧게 유지한다. 길어지는 설명은 `docs/`로 빼고 경로만 남긴다.
- 실행 방법·환경 변수·API가 바뀌면 `README.md`를, 서비스 전체 요구사항이 바뀌면 `CLAUDE.md`를 갱신한다.

## 부트스트랩 (Claude 실행용)
**실행 조건**: `src/`가 아직 없는 프로젝트에서 `/init`을 실행했거나, 사용자가 "템플릿대로 세팅해줘"라고 요청했을 때.
이 경우 `CLAUDE.md`만 만들고 끝내지 말고 아래 단계를 순서대로 모두 수행한다.

1. **세트 확인**: SDD 세트 네 파일이 정해진 경로에 있는지 확인한다. 위치가 다르면 옮기고, 빠진 파일이 있으면 사용자에게 알린다.
2. **질문 한 번에 하기**(AskUserQuestion): 서비스 한 줄 설명 / DB(MongoDB, PostgreSQL, 없음) / 연동할 외부 시스템(없음 가능).
3. **uv 프로젝트 생성**
   - `uv init --bare --python 3.11` (이미 `pyproject.toml`이 있으면 생략)
   - `uv add fastapi uvicorn` / `uv add --dev ruff pytest pytest-asyncio httpx2` (최신 Starlette의 TestClient는 `httpx2`를 쓴다)
   - `pyproject.toml`에 아래 설정 추가
     ```toml
     [tool.uv]
     package = false

     [tool.pytest.ini_options]
     pythonpath = ["."]
     testpaths = ["tests"]
     asyncio_mode = "auto"
     ```
   - DB 드라이버: MongoDB → `uv add pymongo`, PostgreSQL → `uv add sqlalchemy asyncpg`
4. **디렉터리 생성**: 아래 "레이어드 아키텍처" 표의 디렉터리를 만들고 각각 `__init__.py`를 둔다(`src/`, `src/core/db/`, `src/core/exception/` 포함). 테스트용 `tests/` 디렉터리도 만든다(`__init__.py` 없음).
5. **기본 코드 작성**
   - `src/core/exception/my_exception.py`, `src/main.py`: 아래 "Error Handling"의 기본 코드
   - `src/core/db/<db>.py`: 선택한 DB의 연결 모듈. 접속 정보는 환경 변수에서 읽고 기본값은 localhost. DB가 없으면 생략.
   - 외부 시스템이 있으면 `src/services/<name>_service.py`에 빈 래퍼 클래스 하나
   - `tests/test_main.py`: 아래 "테스트"의 스모크 테스트
6. **`.gitignore`**: `__pycache__/`, `*.py[oc]`, `.venv`, `.env`, `.ruff_cache/`, `.pytest_cache/`
7. **`CLAUDE.md`** (아래 형태로, 2번 답변으로 채운다)
   ```markdown
   ## 프로젝트 개요
   <이 서비스가 무엇을 하는지 1~2줄>. 스택: FastAPI + <DB> + <외부 시스템>.

   공통 규칙: @docs/fastapi-sdd-template.md

   ## 프로젝트 고유 구성
   - <DB 연결 모듈, 외부 클라이언트 래퍼 클래스 등 이 프로젝트에만 있는 것>

   ## 프로젝트 상세 설명 (요구사항)
   - <서비스 전체에 걸친 요구사항. 기능 단위 요구사항은 docs/<feature-name>/prd.md에 쓴다>
   ```
8. **`README.md`** (아래 형태로)
   ```markdown
   # <프로젝트 이름>
   <서비스 한 줄 설명>

   ## 요구 사항
   - Python 3.11+, uv, <DB>, <외부 시스템>

   ## 실행
   uv sync
   uv run uvicorn src.main:app --reload
   → http://localhost:8000/docs

   ## 환경 변수
   | 이름 | 기본값 | 설명 |

   ## API
   | Method | Path | 설명 |
   (기능을 구현할 때마다 추가)

   ## 개발
   uv run ruff check . / uv run ruff format .
   uv run pytest
   - 코드 규칙: docs/fastapi-sdd-template.md
   - 개발 프로세스: sdd-process.md
   ```
9. **확인**: `uv run ruff check .`, `uv run ruff format .`, `uv run pytest`가 모두 통과해야 한다.
10. **보고**: 만든 파일 목록과, 다음 할 일("`/feat <기능 설명>`으로 첫 기능 시작")을 알려준다.

## Python 규칙
- 패키지 관리·가상환경·스크립트 실행은 `uv`만 쓴다(`pip`/`venv` 금지).
- lint·포맷은 `ruff`만 쓴다(`black`/`flake8`/`isort` 금지).
- 타입 힌트 필수. 모든 public 함수는 return type을 명시한다.
- 함수/변수는 snake_case.
- 검증 함수 이름: 틀리면 예외를 던지는 함수는 `validate_<대상>`(예: `validate_user_id`), 참/거짓만 돌려주는 함수는 `is_<대상>`(예: `is_user_id`).
- 모든 함수와 복잡한 로직에는 짧지만 빠른 이해에 도움이 되는 주석을 단다.
- `models/`·`schemas/`의 Pydantic 필드에는 `Field(description=...)`로 설명을 단다(의미, 형식·제약, 누가 값을 정하는지). `schemas/`의 설명은 `/docs`에 그대로 노출된다.

## 테스트
- `pytest`로 작성하고 `uv run pytest`로 실행한다. 테스트 파일은 `tests/test_<대상>.py`.
- **service 테스트가 핵심이다.** 비즈니스 규칙(쿼터, 소유권, 상태 전이 등)마다 정상/에러 케이스를 하나 이상 둔다. repository·외부 클라이언트는 `monkeypatch`나 가짜 객체로 대체하고 실제 DB/외부 시스템에 붙지 않는다.
- router 테스트는 `fastapi.testclient.TestClient`로 상태 코드와 응답 형태만 확인한다.
- async 함수는 `async def test_...`로 그대로 쓴다(`asyncio_mode = "auto"`).

스모크 테스트(부트스트랩 시 생성):
```python
# tests/test_main.py
from fastapi.testclient import TestClient

from src.main import app

client = TestClient(app)


# 앱이 import·기동되고 OpenAPI 문서가 열리는지 확인한다.
def test_openapi_docs() -> None:
    response = client.get("/docs")
    assert response.status_code == 200
```

## 레이어드 아키텍처
요청 흐름은 반드시 **Router → Service → Repository** 순서를 따른다. "간단한" 엔드포인트라도 레이어를 건너뛰지 않는다.

| 위치 | 역할 | 금지 |
|---|---|---|
| `src/routers/` | HTTP 계층만: 요청 파싱 → `services/` 함수 하나 호출 → 결과 반환 | 비즈니스 로직, `repository/`·외부 클라이언트 직접 호출, raw dict·`models/` 객체 반환 |
| `src/schemas/` | 라우터의 요청/응답 Pydantic 모델. 리소스당 모듈 하나(`routers/<name>_router.py` ↔ `schemas/<name>.py`) | 라우터가 참조하는 모델은 이것뿐 |
| `src/services/` | 비즈니스 로직(검증/변환). 영속화는 `repository/`로, 외부 클라이언트는 직접 호출. 도메인 객체 또는 완성된 응답 객체 반환 | `routers/` import |
| `src/repository/` | DB 접근(쿼리/CRUD)만 | `routers/`·`services/` 호출 |
| `src/models/` | 내부/도메인 모델, DB document 모델(`schemas/`와 구분) | |
| `src/core/` | 공통 인프라: DB 연결(`core/db`), 예외(`core/exception`) 등 | |
| `src/main.py` | 앱 엔트리포인트(`app = FastAPI()`), 라우터·예외 핸들러 등록 | |

- 외부 시스템 클라이언트는 `services/<name>_service.py`의 클래스 하나로 감싸고, 다른 service는 그 클래스를 통해서만 호출한다.
- 라우터가 없는 백그라운드 컴포넌트(watch, 스케줄러 등)도 DB는 `repository/`, 외부 시스템은 래퍼 클래스를 통해서만 접근한다.

## API 문서 (OpenAPI)
`/docs`(Swagger UI)와 `/redoc`(ReDoc)에서 요청·응답이 실제 값으로 보이게 한다. 스키마만 두면 ReDoc이 `"string"`, `0` 같은 의미 없는 샘플을 만든다.
- **요청 body**: `Body(openapi_examples={...})`로 대표 입력을 이름 붙여 둔다(예: 필수 필드만, 모든 필드).
- **헤더·쿼리 파라미터**: `Header(...)`·`Query(...)`에도 `openapi_examples`를 둔다.
- **정상 응답**: `responses={<상태 코드>: {"content": {"application/json": {"example": ...}}}}`.
- **에러 응답**: 엔드포인트마다 나열하지 않는다. `schemas/error.py`에 400·500(필요하면 404) 응답 문서(`ErrorResponse` 모양 + 대표 example 하나)를 두고 `APIRouter(responses=...)`로 라우터마다 한 번만 붙인다.
  - 엔드포인트별 에러 code 목록의 기준은 `docs/<feature-name>/spec.md`의 에러 표다. `/docs`에는 엔드포인트 `description`에 그 경로만 적는다(같은 목록을 코드·테스트에 다시 쓰지 않는다).
  - 전역 핸들러의 500 본문은 핸들러와 문서가 같은 상수를 쓴다.
- example 값은 `schemas/<name>.py`에 상수로 두고 라우터가 연결만 한다.
- **테스트로 어긋남을 막는다**: 요청 example을 실제로 보내 정상 응답이 나는지, 응답 example이 응답 schema로 검증되는지 확인한다.

## Error Handling
- 모든 비즈니스 에러는 `MyApiError(ErrorEnum.XXX)`로 던진다. `ErrorEnum` 각 항목은 `(code, status_code, message)`를 가진다.
- 예외 핸들러는 `main.py`에 등록한다.
  - `MyApiError` → `{code, message}` JSON + enum에 지정된 상태 코드
  - DB 에러 → 500
  - 기타 `Exception` → 500 (`unknown_error`)

기본 코드:
```python
# src/core/exception/my_exception.py
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
```
```python
# src/main.py
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from src.core.exception.my_exception import MyApiError

app = FastAPI()


# MyApiError는 error_enum에 담긴 상태 코드로 구조화된 JSON 응답을 돌려준다.
@app.exception_handler(MyApiError)
async def my_api_error_handler(request: Request, exc: MyApiError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.error_enum.status_code,
        content={"code": exc.error_enum.code, "message": exc.error_enum.message},
    )


# 그 외 모든 예외는 500 unknown_error로 통일한다.
@app.exception_handler(Exception)
async def unknown_error_handler(request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(
        status_code=500,
        content={"code": "unknown_error", "message": "알 수 없는 오류가 발생했습니다."},
    )
```

## SDD 작업 규칙
작업 흐름은 **PRD → SPEC → PLAN → TASK → IMPLEMENT**다. 단계별 기준과 각 문서의 템플릿은 `sdd-process.md`에 있으며, 문서 작업을 할 때는 그 파일을 먼저 읽는다.

### 문서 위치
기능 하나당 폴더 하나를 쓴다.
```
docs/<feature-name>/
├── prd.md        # 왜/무엇을
├── spec.md       # 어떻게 (API 또는 컴포넌트 명세)
├── plan.md       # 레이어별 변경 파일, DB 변경
├── task.md       # 작업 체크리스트
└── implement.md  # 구현 기록, spec과 달라진 점, 확인 결과
```
- `<feature-name>`은 kebab-case. HTTP API는 `api-`, 백그라운드 컴포넌트는 `component-` 접두사를 붙인다. 예: `api-user-create`, `component-order-watch`

### Claude가 지킬 것
- **spec 없이 구현하지 않는다.** spec이 없거나 `sdd-process.md`의 spec 템플릿 항목이 비어 있으면 구현 전에 사용자에게 묻는다.
- **추측으로 채우지 않는다.** PRD에 없는 구현 디테일(Method/Path, 필드 타입, 상태 코드, 실행 방식 등)은 구체적으로 질문해서 채운다. 기존 `docs/*/spec.md`가 있으면 패턴(에러 코드, 응답 형태)을 맞춘다.
- **단계마다 멈춘다.** 한 단계의 문서를 만들면 사용자에게 보여주고 확인받은 뒤 다음 단계로 간다. 사용자가 "끝까지 진행"이라고 하면 연속으로 진행한다.
- **문서를 코드와 맞춘다.** 구현 중 spec과 달라진 점은 `implement.md`에 남기고 `spec.md`도 고친다.
- **서비스 전체 방향이 바뀌는 결정**은 기능 문서보다 먼저 사용자와 논의하고, 결론을 `CLAUDE.md`의 "프로젝트 상세 설명 (요구사항)"에 반영한다.
