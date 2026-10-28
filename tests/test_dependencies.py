import importlib

import pytest
from kubernetes.config.config_exception import ConfigException

import src.core.dependencies as deps
from src.repository.user_job_repository import UserJobRepository
from src.services.k8s_service import K8sService
from src.services.user_job_service import UserJobService


@pytest.fixture(autouse=True)
def clear_cache() -> None:
    deps.get_k8s_service.cache_clear()


# 클러스터 설정 로딩 함수를 가짜로 바꾸고 호출 순서를 기록한다.
@pytest.fixture
def config_calls(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    calls: list[str] = []

    def incluster() -> None:
        calls.append("incluster")
        raise ConfigException("not in cluster")

    monkeypatch.setattr(deps.config, "load_incluster_config", incluster)
    monkeypatch.setattr(
        deps.config, "load_kube_config", lambda: calls.append("kubeconfig")
    )
    return calls


# import만으로는 클러스터 설정을 읽지 않는다.
def test_import_does_not_load_config(config_calls: list[str]) -> None:
    importlib.reload(deps)
    assert config_calls == []


# 처음 호출 때 in-cluster → kubeconfig 순으로 한 번만 읽고, 이후 같은 객체를 반환한다.
def test_get_k8s_service_loads_once(config_calls: list[str]) -> None:
    first = deps.get_k8s_service()
    second = deps.get_k8s_service()
    assert isinstance(first, K8sService)
    assert first is second
    assert config_calls == ["incluster", "kubeconfig"]


# service는 user_jobs 컬렉션을 쓰는 repository를 주입받는다(실제 DB 접속은 하지 않음).
def test_get_user_job_service_wiring() -> None:
    service = deps.get_user_job_service()
    assert isinstance(service, UserJobService)
    assert isinstance(service.repository, UserJobRepository)
    assert service.repository.collection.name == "user_jobs"


# close_k8s_service()는 만들어 둔 ApiClient를 닫고 캐시를 비운다. 다음 호출은 새로 만든다.
def test_close_k8s_service(
    config_calls: list[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    service = deps.get_k8s_service()
    closed: list[bool] = []
    monkeypatch.setattr(service.api_client, "close", lambda: closed.append(True))
    deps.close_k8s_service()
    assert closed == [True]
    assert deps.get_k8s_service.cache_info().currsize == 0
    assert deps.get_k8s_service() is not service


# 만든 적이 없으면 설정을 읽지 않고 아무것도 하지 않는다.
def test_close_k8s_service_without_service(config_calls: list[str]) -> None:
    deps.close_k8s_service()
    assert config_calls == []
