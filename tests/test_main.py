import pytest
from fastapi.testclient import TestClient
from kubernetes.config.config_exception import ConfigException

from src import main
from src.core import dependencies
from src.main import app

client = TestClient(app)


# 앱이 import·기동되고 OpenAPI 문서가 열리는지 확인한다.
def test_openapi_docs() -> None:
    response = client.get("/docs")
    assert response.status_code == 200


# 검증 에러는 400으로 바꿔 응답하므로 OpenAPI에 422와 그 스키마가 없어야 한다(/docs가 실제 응답과 같게).
def test_openapi_has_no_422() -> None:
    schema = client.get("/openapi.json").json()
    for path, path_item in schema["paths"].items():
        for method, operation in path_item.items():
            assert "422" not in operation["responses"], (method, path)
    schemas = schema["components"]["schemas"]
    assert "HTTPValidationError" not in schemas
    assert "ValidationError" not in schemas
    # 문서화된 400 응답은 실제 에러 모양({code, message})
    bad_request = schema["paths"]["/jobs"]["post"]["responses"]["400"]
    assert bad_request["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/ErrorResponse"
    }


# 클러스터 설정(in-cluster·kubeconfig)이 모두 없으면 앱 시작이 실패한다. MongoDB보다 먼저 확인하므로 DB 없이 검증된다.
def test_startup_fails_without_cluster_config(monkeypatch: pytest.MonkeyPatch) -> None:
    def no_config() -> None:
        raise ConfigException("no config")

    monkeypatch.setattr(dependencies.config, "load_incluster_config", no_config)
    monkeypatch.setattr(dependencies.config, "load_kube_config", no_config)
    dependencies.get_k8s_service.cache_clear()
    with pytest.raises(ConfigException), TestClient(app):
        pass
    dependencies.get_k8s_service.cache_clear()


# 시작 도중(인덱스 생성) 실패해도 MongoDB 연결과 K8s 클라이언트를 닫는다.
def test_startup_failure_closes_clients(monkeypatch: pytest.MonkeyPatch) -> None:
    closed: list[str] = []

    class FailingRepository:
        async def ensure_indexes(self) -> None:
            raise RuntimeError("mongo down")

    async def fake_close_client() -> None:
        closed.append("mongo")

    monkeypatch.setattr(main, "get_k8s_service", lambda: None)
    monkeypatch.setattr(main, "get_user_job_repository", FailingRepository)
    monkeypatch.setattr(main, "close_client", fake_close_client)
    monkeypatch.setattr(main, "close_k8s_service", lambda: closed.append("k8s"))
    with pytest.raises(RuntimeError), TestClient(app):
        pass
    assert closed == ["mongo", "k8s"]
