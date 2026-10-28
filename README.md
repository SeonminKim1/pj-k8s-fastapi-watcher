# pj-k8s-fastapi-watcher
쿠버네티스 리소스를 REST API로 관리하고, watch로 리소스 변경을 동기화하는 FastAPI 서비스.

## 요구 사항
- Python 3.11+, uv, MongoDB, 접근 가능한 Kubernetes 클러스터(kubeconfig 또는 in-cluster ServiceAccount)

## 실행
```bash
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
(기능을 구현할 때마다 추가)

## 개발
```bash
uv run ruff check . && uv run ruff format .
uv run pytest                                   # 전체 테스트
uv run pytest tests/test_main.py::test_openapi_docs   # 단일 테스트
```
- 코드 규칙: [docs/fastapi-sdd-template.md](docs/fastapi-sdd-template.md)
- 개발 프로세스: [sdd-process.md](sdd-process.md)

