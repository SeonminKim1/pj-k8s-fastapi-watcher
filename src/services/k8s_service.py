from kubernetes import client


class K8sService:
    """Kubernetes API 클라이언트 래퍼. 다른 클래스는 이 객체를 생성자로 주입받아 클러스터에 접근한다."""

    # 설정 로딩은 하지 않고, 주입받은 ApiClient로 API 객체만 만든다(설정 로딩은 core/dependencies.py).
    def __init__(self, api_client: client.ApiClient) -> None:
        self.api_client = api_client
        self.core_v1 = client.CoreV1Api(api_client)
        self.apps_v1 = client.AppsV1Api(api_client)
        self.batch_v1 = client.BatchV1Api(api_client)
