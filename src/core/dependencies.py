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


# 앱 종료 시 만들어 둔 K8sService의 ApiClient(스레드 풀·커넥션 풀)를 닫고 캐시를 비운다.
# 만든 적이 없으면 아무것도 하지 않는다(설정을 새로 읽지 않음).
def close_k8s_service() -> None:
    if get_k8s_service.cache_info().currsize == 0:
        return
    get_k8s_service().api_client.close()
    get_k8s_service.cache_clear()


# 공유 MongoDB 클라이언트의 user_jobs 컬렉션으로 repository를 만든다(요청마다 만들어도 가볍다).
def get_user_job_repository() -> UserJobRepository:
    return UserJobRepository(get_database()["user_jobs"])


# repository를 주입한 UserJobService를 만든다. 라우터는 Depends(get_user_job_service)로 받는다.
def get_user_job_service() -> UserJobService:
    return UserJobService(get_user_job_repository())
