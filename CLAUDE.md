# CLAUDE.md
이 프로젝트에만 해당하는 내용만 둔다. 어느 FastAPI 프로젝트에도 맞는 규칙(레이어, 의존성 주입, 에러 처리, 테스트 등)은 아래 스택 템플릿에 있다.

스택 규칙: @.claude/stacks/fastapi.md

## 프로젝트 개요
쿠버네티스 인프라를 관리하는 서비스. REST API로 클러스터 리소스(Namespace, Deployment 등)를 조회·생성·삭제하고, 백그라운드 watch 컴포넌트로 리소스 변경을 감지해 상태를 동기화한다. 스택: FastAPI + MongoDB + Kubernetes API(공식 `kubernetes` Python 클라이언트).

## 고유 모듈
- `src/core/db/mongodb.py`: 공유 `AsyncMongoClient(tz_aware=True)`(`get_client()`/`get_database()`). 환경 변수 `MONGO_URI`(기본 `mongodb://localhost:27017`), `MONGO_DB_NAME`(기본 `k8s_client`). 접근은 모두 비동기이며 `dependencies.py`만 사용한다.
- `src/core/dependencies.py`: `main.py` lifespan에서 클러스터 설정 로딩(`get_k8s_service()`)과 repository `ensure_indexes()`를 한다. 그래서 앱을 띄우려면 클러스터 설정(in-cluster 또는 kubeconfig)과 MongoDB가 모두 필요하다.
- `src/services/k8s_service.py`: `K8sService`. 클러스터 접근은 반드시 이 클래스를 거친다.
- `src/core/exception/validation_error.py`: 요청 검증 에러(FastAPI 422)를 필드별 `ErrorEnum` 하나로 바꿔 400으로 응답한다(`to_error_enum()`, OpenAPI에서도 422 제거). 새 입력 필드에는 타입에 `error_code(ErrorEnum.XXX)`를 붙이고, 필수 필드라 누락도 그 code로 알려야 하면 `_MISSING_ERRORS`에도 추가한다.
- `src/main.py`: `PyMongoError` → 500 `db_error`. 500 본문 상수와 공통 400·500 응답 문서(`COMMON_ERROR_RESPONSES`)는 `schemas/error_response.py`.
- `src/models/k8s_names.py`: 유저 ID·DNS-1035 이름·이미지 참조·env 이름 형식 규칙의 유일한 정의(`Annotated` 타입과 `is_*` 함수).
- `src/models/enums.py`: 도메인 enum(`JobStatus`, `JobType`, `JobSize`). 새 enum도 여기에 둔다(`ErrorEnum`만 `core/exception/my_exception.py`).
- `src/services/job_templates.py`: 템플릿 → 매니페스트 생성과 서버 고정 값(크기 프리셋, 보안 설정, 라벨 등). job 타입을 추가할 때는 `JobType`, `models/user_job_models.py`의 템플릿 모델, 이 파일의 생성 함수·`KINDS_BY_TYPE`을 함께 늘린다.
- SDD 방식: spec-kit 기반 `/sdd-speckit-*`(`.claude/skills/sdd-speckit/process.md`). 기능 문서는 `specs/NNN-<이름>/`
- 이슈 트래커: GitHub Project (`/sdd-speckit-*`가 `.claude/skills/sdd-feat/tracker-github.md`의 명령으로 연동, 비어 있으면 연동 안 함)
  - owner: `SeonminKim1`
  - Project 번호: `3`, 제목: `pj-k8s-fastapi-watcher` (https://github.com/users/SeonminKim1/projects/3, 저장소 `SeonminKim1/pj-k8s-fastapi-watcher`)

## 서비스 요구사항
- **유저 식별**: 인증은 앞단(게이트웨이)이 처리하고, 이 서비스는 요청 헤더 `X-User-Id`의 값을 유저 ID로 신뢰한다. 유저 ID는 소문자·숫자·`-`만, 영숫자로 시작·끝, 1~58자여야 한다(아니면 400).
- **유저별 네임스페이스**: 유저의 리소스는 모두 전용 네임스페이스 `user-{유저 ID}`에 둔다. 다른 네임스페이스에는 만들지 않는다.
- **유저별 job 개수 제한**: 유저 한 명이 가질 수 있는 삭제되지 않은 job은 10개까지다. 넘으면 400.
- **에러 상태 코드**: 400(잘못된 요청·규칙 위반·중복·상태 충돌), 404(없음·남의 리소스), 500(서버 내부 오류)만 쓴다. 비즈니스 에러는 400·404 중 하나이고 구분은 `ErrorEnum`의 `code`로 한다.
- **핵심 도메인 — user-job**: 유저가 만든 쿠버네티스 리소스 묶음(예: Deployment + Service)을 하나의 job으로 관리한다. job은 MongoDB에 소유자·구성 리소스(매니페스트 원본 포함)·상태를 기록한다. 상세: `specs/001-domain-user-job/`
- **job 입력은 템플릿 방식**: 유저는 쿠버네티스 매니페스트를 직접 보내지 않는다. job 타입(지금은 `web`만)과 그 타입이 허용하는 필드만 보내고, 서버가 매니페스트를 생성한다. 라벨·네임스페이스·리소스 requests/limits(크기 프리셋)·보안 설정 등은 서버가 고정하며 유저가 바꿀 수 없다. 새 구성이 필요하면 타입이나 필드를 추가한다.
- **operator 패턴**:
  - MongoDB의 job 문서가 원하는 상태(desired), 클러스터가 실제 상태(actual)다.
  - API는 MongoDB에만 기록하고 바로 응답한다. 클러스터에 쓰지 않으며 생성 성공을 보장하지 않는다. 유저는 job `status`로 진행 상황을 본다.
  - 클러스터에 쓰는 것은 operator(백그라운드 컴포넌트)뿐이다. operator는 job과 클러스터를 비교해 리소스를 만들고(server-side apply)·다시 시도하고·삭제된 job의 리소스를 정리하고, 관찰한 결과로 `status`를 갱신한다.
  - operator가 만드는 리소스에는 `app.kubernetes.io/managed-by`와 `user-job-id` 라벨을 붙인다.
  - watch는 이벤트를 놓칠 수 있으므로 주기적으로 전체를 다시 점검(resync)한다. operator는 프로세스 하나에서만 실행한다.
