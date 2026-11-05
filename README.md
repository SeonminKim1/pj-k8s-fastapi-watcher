# pj-k8s-fastapi-watcher
쿠버네티스 리소스를 REST API로 관리하고, watch로 리소스 변경을 동기화하는 FastAPI 서비스.

## 요구 사항
- Python 3.11+, uv, MongoDB, 접근 가능한 Kubernetes 클러스터(kubeconfig 또는 in-cluster ServiceAccount)

## 실행
```bash
git submodule update --init   # .claude (ai-shared-dev-toolkit)
uv sync
uv run uvicorn src.main:app --reload
```
→ http://localhost:8000/docs

## 환경 변수
| 이름 | 기본값 | 설명 |
|---|---|---|
| `MONGO_URI` | `mongodb://localhost:27017` | MongoDB 접속 URI |
| `MONGO_DB_NAME` | `k8s_client` | 사용할 데이터베이스 이름 |
| `KUBECONFIG` | `~/.kube/config` | 클러스터 밖에서 실행할 때 사용할 kubeconfig 경로 |

## API
| Method | Path | 설명 |
|---|---|---|
| `POST` | `/jobs` | job 생성. `X-User-Id` 헤더 필수. 템플릿 입력(`web`)으로 서버가 Deployment·Service 매니페스트를 만들어 `pending`으로 저장(클러스터 반영은 operator). 유저당 10개 |
| `GET` | `/jobs` | 삭제되지 않은 자기 job 요약(`id`·`name`·`status`·`created_at`)을 최신순으로 조회. `X-User-Id` 헤더 필수. 쿼리 `limit`(1~100, 기본 20), `cursor`(직전 응답의 `next_cursor`), `status`(하나만). 응답 `{items, next_cursor}` |
| `GET` | `/jobs/{job_id}` | 삭제되지 않은 자기 job 하나의 상세(생성 응답과 같은 모양: 템플릿·리소스 요약 포함) 조회. `X-User-Id` 헤더 필수. 남의 job·없는 job·삭제된 job·형식이 틀린 ID는 모두 404 `job_not_found` |

- 에러 응답은 `{code, message}`이며 400·404·500만 쓴다. 요청 형식 오류는 필드별 `code`(`invalid_image`, `invalid_port` 등)로 구분한다. 상세: [specs/002-api-job-create/contracts/post-jobs.md](specs/002-api-job-create/contracts/post-jobs.md), [specs/003-api-job-list/contracts/get-jobs.md](specs/003-api-job-list/contracts/get-jobs.md), [specs/004-api-job-get/contracts/get-job.md](specs/004-api-job-get/contracts/get-job.md)

## 개발
```bash
uv run ruff check . && uv run ruff format .
uv run pytest                                   # 전체 테스트
uv run pytest tests/test_main.py::test_openapi_docs   # 단일 테스트
```
- 코드 규칙: [.claude/stacks/fastapi.md](.claude/stacks/fastapi.md)
- 개발 프로세스(SDD): [.claude/skills/sdd-speckit/process.md](.claude/skills/sdd-speckit/process.md) — 기능은 `/sdd-speckit-specify`부터 진행, 기능 문서는 [specs/](specs/)
- `.claude/`는 [ai-shared-dev-toolkit](https://github.com/SeonminKim1/ai-shared-dev-toolkit) 서브모듈이다. clone 후 `git submodule update --init`

