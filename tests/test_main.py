import pytest
from fastapi.testclient import TestClient
from kubernetes.config.config_exception import ConfigException

from src.core import dependencies
from src.main import app

client = TestClient(app)


# 앱이 import·기동되고 OpenAPI 문서가 열리는지 확인한다.
def test_openapi_docs() -> None:
    response = client.get("/docs")
    assert response.status_code == 200


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
