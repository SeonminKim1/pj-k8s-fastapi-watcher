from functools import cache

from kubernetes import client, config
from kubernetes.config.config_exception import ConfigException

from src.core.db.mongodb import get_database
from src.repository.user_job_repository import UserJobRepository
from src.services.k8s_service import K8sService
from src.services.user_job_service import UserJobService

# 실제 객체를 조립하는 유일한 곳. API는 Depends(get_xxx)로, operator는 lifespan에서 받아 쓴다.
# 테스트는 app.dependency_overrides 또는 생성자 인자로 가짜 객체를 넣는다.


# 처음 호출할 때만 클러스터 설정을 읽는다(in-cluster → kubeconfig). import 시점에는 클러스터에 접근하지 않는다.
@cache
def get_k8s_service() -> K8sService:
    try:
        config.load_incluster_config()
    except ConfigException:
        config.load_kube_config()
    return K8sService(client.ApiClient())


def get_user_job_repository() -> UserJobRepository:
    return UserJobRepository(get_database()["user_jobs"])


def get_user_job_service() -> UserJobService:
    return UserJobService(get_user_job_repository())
