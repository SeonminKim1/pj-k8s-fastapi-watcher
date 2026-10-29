# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 프로젝트 개요
쿠버네티스 인프라를 관리하는 서비스. REST API로 클러스터 리소스(Namespace, Deployment 등)를 조회·생성·삭제하고, 백그라운드 watch 컴포넌트로 리소스 변경을 감지해 상태를 동기화한다. 스택: FastAPI + MongoDB + Kubernetes API(공식 `kubernetes` Python 클라이언트).

공통 규칙: @docs/fastapi-sdd-template.md

## 프로젝트 고유 구성
- `src/core/db/mongodb.py`: 공유 `AsyncMongoClient(tz_aware=True)`(`get_client()`/`get_database()`). 환경 변수 `MONGO_URI`(기본 `mongodb://localhost:27017`), `MONGO_DB_NAME`(기본 `k8s_client`). MongoDB 접근은 모두 비동기(`async def`)이며, `dependencies.py`가 repository를 만들 때만 사용한다.
- `src/core/dependencies.py`: service·repository·`K8sService` 조립. `main.py` lifespan에서 클러스터 설정 로딩(`get_k8s_service()`)과 repository `ensure_indexes()`를 하므로, 앱을 띄우려면 클러스터 설정(in-cluster 또는 kubeconfig)과 MongoDB가 모두 필요하다(없으면 시작 실패).
- `src/services/k8s_service.py`: `K8sService` 래퍼. 클러스터 접근은 반드시 이 클래스를 거친다. 다른 클래스는 직접 만들지 않고 생성자로 주입받는다(주입 방식은 아래 "의존성 주입").
- `src/main.py`: `PyMongoError`는 500 `db_error`로 처리한다. 요청 검증 에러(FastAPI 422)는 `src/core/exception/validation_error.py`의 `to_error_enum()`으로 필드별 `ErrorEnum` 하나를 골라 400으로 응답하고, OpenAPI(`/docs`)에서도 422를 뺀다. 새 필드를 추가하면 그 파일의 위치→에러 표에도 추가한다. 500 응답 본문(`db_error`·`unknown_error`)은 `schemas/error.py`의 상수를 쓴다. 엔드포인트의 에러 example은 `schemas/error.py`의 `error_responses(*ErrorEnum)`으로 만든다.
- `src/models/k8s_names.py`: 유저 ID·DNS-1035 이름·이미지 참조·env 이름 형식 규칙의 유일한 정의(`Annotated` 타입과 `is_*` 함수). schema·model·service가 함께 쓴다.
- `src/services/job_templates.py`: 템플릿 → 매니페스트 생성과 서버 고정 값(크기 프리셋, 보안 설정, 라벨 등). job 타입을 추가할 때는 `models/enums.py`의 `JobType`, `models/user_job.py`의 템플릿 모델, 이 파일의 생성 함수·`KINDS_BY_TYPE`을 함께 늘린다.
- `src/models/enums.py`: 도메인 enum(`JobStatus`, `JobType`, `JobSize`)을 모아 둔다. 새 enum도 여기에 둔다. 에러 종류 `ErrorEnum`만 `MyApiError`와 짝이라 `core/exception/my_exception.py`에 둔다.
- 이슈 트래커: GitHub Project (`/feat`가 `.claude/skills/feat/github.md`의 `gh` 명령으로 이슈·상태·PR 관리, 비어 있으면 연동 안 함)
  - owner: `SeonminKim1`
  - Project 번호: `3`, 제목: `pj-k8s-fastapi-watcher` (https://github.com/users/SeonminKim1/projects/3, 저장소 `SeonminKim1/pj-k8s-fastapi-watcher`에 연결됨)

## 프로젝트 상세 설명 (요구사항)
- HTTP API 기능은 `docs/api-*`, watch 같은 백그라운드 기능은 `docs/component-*`, API·컴포넌트 없이 도메인 모델만 정의하는 기능은 `docs/domain-*` 폴더로 문서화한다.
- **유저 식별**: 인증은 앞단(게이트웨이)이 처리하고, 이 서비스는 요청 헤더 `X-User-Id`의 값을 유저 ID로 신뢰한다. 유저 ID는 소문자·숫자·`-`만, 영숫자로 시작·끝, 1~58자여야 한다(아니면 400).
- **유저별 네임스페이스**: 유저의 리소스는 모두 전용 네임스페이스 `user-{유저 ID}`에 둔다. 다른 네임스페이스에는 만들지 않는다.
- **유저별 job 개수 제한**: 유저 한 명이 가질 수 있는 삭제되지 않은 job은 10개까지다. 넘으면 400.
- **에러 상태 코드**: 400(잘못된 요청·규칙 위반·중복·상태 충돌), 404(없음·남의 리소스), 500(DB 오류 등 서버 내부 오류)만 쓴다. 비즈니스 에러(`MyApiError`)는 400·404 중 하나이고 구분은 `ErrorEnum`의 `code`로 한다. 500은 전역 예외 핸들러만 응답한다.
- **핵심 도메인 — user-job**: 유저가 만든 쿠버네티스 리소스 묶음(예: Deployment + Service)을 하나의 job으로 관리한다. job은 MongoDB에 소유자·구성 리소스(매니페스트 원본 포함)·상태를 기록한다. 상세: `docs/domain-user-job/`
- **job 입력은 템플릿 방식**: 유저는 쿠버네티스 매니페스트를 직접 보내지 않는다. job 타입(지금은 `web`만)과 그 타입이 허용하는 필드만 보내고, 서버가 매니페스트를 생성한다. 라벨·네임스페이스·리소스 requests/limits(크기 프리셋)·보안 설정 등은 서버가 고정하며 유저가 바꿀 수 없다. 새 구성이 필요하면 타입이나 필드를 추가한다.
- **operator 패턴**:
  - MongoDB의 job 문서가 원하는 상태(desired), 클러스터가 실제 상태(actual)다.
  - API는 MongoDB에만 기록하고 바로 응답한다. 클러스터에 쓰지 않으며 생성 성공을 보장하지 않는다. 유저는 job `status`로 진행 상황을 본다.
  - 클러스터에 쓰는 것은 operator(백그라운드 컴포넌트)뿐이다. operator는 job과 클러스터를 비교해 리소스를 만들고(server-side apply)·다시 시도하고·삭제된 job의 리소스를 정리하고, 관찰한 결과로 `status`를 갱신한다.
  - operator가 만드는 리소스에는 `app.kubernetes.io/managed-by`와 `user-job-id` 라벨을 붙인다.
  - watch는 이벤트를 놓칠 수 있으므로 주기적으로 전체를 다시 점검(resync)한다. operator는 프로세스 하나에서만 실행한다.
- **의존성 주입**: service·repository·`K8sService`는 클래스로 만들고 의존 객체를 생성자로 받는다. 실제 객체는 `src/core/dependencies.py`에서만 조립한다(API는 FastAPI `Depends`, operator는 lifespan에서 받는다). 테스트는 가짜 객체를 주입한다. 단, DB·클러스터 같은 외부 의존이 없고 입력만으로 결과가 정해지는 순수 함수 모듈(예: `services/job_templates.py`)은 클래스·주입 없이 직접 import한다(가짜로 바꿀 이유가 없으므로).
