from collections.abc import Callable
from typing import Any

from src.models.enums import JobSize, JobType
from src.models.user_job import JobResource, JobTemplate, WebTemplate

# 템플릿 입력 → 매니페스트 생성. 유저가 정하지 않는 값(라벨, 리소스, 보안 설정 등)은 여기서 고정한다.
# 타입을 추가하면 생성 함수 하나와 _BUILDERS·KINDS_BY_TYPE 한 줄씩을 더한다.

# 크기 프리셋(requests = limits)
SIZE_PRESETS: dict[JobSize, dict[str, str]] = {
    JobSize.SMALL: {"cpu": "100m", "memory": "128Mi"},
    JobSize.MEDIUM: {"cpu": "250m", "memory": "256Mi"},
}

# 타입별로 만드는 (apiVersion, kind). operator가 정리·검증할 때 기준이 된다.
KINDS_BY_TYPE: dict[JobType, frozenset[tuple[str, str]]] = {
    JobType.WEB: frozenset({("apps/v1", "Deployment"), ("v1", "Service")}),
}

# Deployment selector와 Service selector가 함께 쓰는 라벨 키. selector는 생성 후 바꿀 수 없다.
_NAME_LABEL = "app.kubernetes.io/name"


# 매니페스트에서 조회용 값(api_version·kind·name)을 꺼내 JobResource로 감싼다.
def _resource(manifest: dict[str, Any]) -> JobResource:
    return JobResource(
        api_version=manifest["apiVersion"],
        kind=manifest["kind"],
        name=manifest["metadata"]["name"],
        manifest=manifest,
    )


# web: Deployment 1개 + ClusterIP Service 1개. 이름은 job 이름, 보안 설정·리소스·probe는 고정.
def _build_web(name: str, namespace: str, template: WebTemplate) -> list[JobResource]:
    labels = {_NAME_LABEL: name}
    metadata = {"name": name, "namespace": namespace, "labels": labels}
    resources = dict(SIZE_PRESETS[template.size])
    container = {
        "name": "app",
        "image": template.image,
        "imagePullPolicy": "IfNotPresent",
        "ports": [{"containerPort": template.port, "protocol": "TCP"}],
        # 같은 입력이면 같은 매니페스트가 나오도록 이름순으로 정렬한다(apply diff 최소화).
        "env": [{"name": k, "value": v} for k, v in sorted(template.env.items())],
        "resources": {"requests": resources, "limits": dict(resources)},
        "securityContext": {
            "privileged": False,
            "allowPrivilegeEscalation": False,
            "capabilities": {"drop": ["ALL"]},
        },
        # 포트가 열려야 Ready. operator의 running이 "응답 가능"을 뜻하게 한다. liveness는 두지 않는다.
        "readinessProbe": {"tcpSocket": {"port": template.port}},
    }
    deployment = {
        "apiVersion": "apps/v1",
        "kind": "Deployment",
        "metadata": metadata,
        "spec": {
            "replicas": template.replicas,
            "selector": {"matchLabels": dict(labels)},
            "template": {
                "metadata": {"labels": dict(labels)},
                "spec": {
                    "automountServiceAccountToken": False,
                    "securityContext": {"seccompProfile": {"type": "RuntimeDefault"}},
                    "containers": [container],
                },
            },
        },
    }
    service = {
        "apiVersion": "v1",
        "kind": "Service",
        "metadata": {**metadata, "labels": dict(labels)},
        "spec": {
            "type": "ClusterIP",
            "selector": dict(labels),
            "ports": [
                {"port": template.port, "targetPort": template.port, "protocol": "TCP"}
            ],
        },
    }
    return [_resource(deployment), _resource(service)]


_BUILDERS: dict[JobType, Callable[[str, str, Any], list[JobResource]]] = {
    JobType.WEB: _build_web,
    # 추후 JobType.DB: _build_db 등
}


# 템플릿 타입에 맞는 생성 함수로 매니페스트를 만든다. name·namespace는 이미 검증된 값이다.
def build_resources(
    name: str, namespace: str, template: JobTemplate
) -> list[JobResource]:
    return _BUILDERS[template.type](name, namespace, template)
