from typing import Any

import pytest

from src.models.user_job import JobResource, WebTemplate
from src.services.job_templates import KINDS_BY_TYPE, SIZE_PRESETS, build_resources

LABELS = {"app.kubernetes.io/name": "my-web"}


def web(**fields: Any) -> WebTemplate:
    return WebTemplate(**{"type": "web", "image": "nginx:1.27", "port": 8080, **fields})


# kind로 생성된 리소스를 찾는다.
def by_kind(resources: list[JobResource], kind: str) -> JobResource:
    return next(r for r in resources if r.kind == kind)


def build(**fields: Any) -> list[JobResource]:
    return build_resources("my-web", "user-alice", web(**fields))


def container(resources: list[JobResource]) -> dict[str, Any]:
    pod = by_kind(resources, "Deployment").manifest["spec"]["template"]["spec"]
    assert len(pod["containers"]) == 1
    return pod["containers"][0]


# web은 Deployment·Service 하나씩, 이름은 job 이름, 모두 job 네임스페이스. kind 목록과 일치한다.
def test_web_resources() -> None:
    resources = build()
    assert {(r.api_version, r.kind) for r in resources} == KINDS_BY_TYPE["web"]
    assert len(resources) == 2
    for r in resources:
        assert r.name == "my-web"
        assert r.manifest["apiVersion"] == r.api_version
        assert r.manifest["kind"] == r.kind
        assert r.manifest["metadata"] == {
            "name": "my-web",
            "namespace": "user-alice",
            "labels": LABELS,
        }


def test_deployment_spec() -> None:
    spec = by_kind(build(replicas=2), "Deployment").manifest["spec"]
    assert spec["replicas"] == 2
    assert spec["selector"] == {"matchLabels": LABELS}
    assert spec["template"]["metadata"] == {"labels": LABELS}
    pod = spec["template"]["spec"]
    assert pod["automountServiceAccountToken"] is False
    assert pod["securityContext"] == {"seccompProfile": {"type": "RuntimeDefault"}}


def test_container_fixed_values() -> None:
    c = container(build())
    assert c["name"] == "app"
    assert c["image"] == "nginx:1.27"
    assert c["imagePullPolicy"] == "IfNotPresent"
    assert c["ports"] == [{"containerPort": 8080, "protocol": "TCP"}]
    assert c["securityContext"] == {
        "privileged": False,
        "allowPrivilegeEscalation": False,
        "capabilities": {"drop": ["ALL"]},
    }
    assert c["readinessProbe"] == {"tcpSocket": {"port": 8080}}
    assert "livenessProbe" not in c
    # root 실행은 허용(runAsNonRoot를 강제하지 않음)
    assert "runAsNonRoot" not in c["securityContext"]


@pytest.mark.parametrize("size", ["small", "medium"])
def test_resources_from_size(size: str) -> None:
    c = container(build(size=size))
    preset = SIZE_PRESETS[size]
    assert c["resources"] == {"requests": preset, "limits": preset}


def test_default_size_is_small() -> None:
    assert container(build())["resources"]["limits"] == {
        "cpu": "100m",
        "memory": "128Mi",
    }


# env는 이름순 [{name, value}]. 입력 순서가 달라도 같은 매니페스트가 나온다.
def test_env_sorted() -> None:
    a = container(build(env={"B": "2", "A": "1"}))["env"]
    b = container(build(env={"A": "1", "B": "2"}))["env"]
    assert a == b == [{"name": "A", "value": "1"}, {"name": "B", "value": "2"}]


def test_env_empty() -> None:
    assert container(build())["env"] == []


def test_service_spec() -> None:
    spec = by_kind(build(), "Service").manifest["spec"]
    assert spec == {
        "type": "ClusterIP",
        "selector": LABELS,
        "ports": [{"port": 8080, "targetPort": 8080, "protocol": "TCP"}],
    }


# 라벨 dict를 리소스끼리 공유하지 않는다(operator가 한쪽에 라벨을 붙여도 다른 쪽이 바뀌지 않게).
def test_labels_not_shared() -> None:
    resources = build()
    dep, svc = by_kind(resources, "Deployment"), by_kind(resources, "Service")
    dep.manifest["metadata"]["labels"]["user-job-id"] = "x"
    assert "user-job-id" not in svc.manifest["metadata"]["labels"]
    assert "user-job-id" not in dep.manifest["spec"]["selector"]["matchLabels"]


def test_same_input_same_output() -> None:
    assert build(env={"A": "1"}, replicas=2) == build(env={"A": "1"}, replicas=2)
