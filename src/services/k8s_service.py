from kubernetes import client, config
from kubernetes.config.config_exception import ConfigException


class K8sService:
    """Kubernetes API 클라이언트 래퍼. 다른 service는 이 클래스를 통해서만 클러스터에 접근한다."""

    def __init__(self) -> None:
        # 클러스터 안에서는 ServiceAccount 설정을, 밖에서는 kubeconfig를 사용한다.
        try:
            config.load_incluster_config()
        except ConfigException:
            config.load_kube_config()
        self.core_v1 = client.CoreV1Api()
        self.apps_v1 = client.AppsV1Api()
