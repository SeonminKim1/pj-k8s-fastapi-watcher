    from enum import StrEnum

# 도메인 enum을 한 곳에 모은다. 에러 종류(ErrorEnum)는 MyApiError와 짝이라 core/exception에 둔다.


class JobStatus(StrEnum):
    """operator가 클러스터를 관찰해 갱신하는 job 상태. 삭제는 상태가 아니라 is_deleted로 표시한다."""

    PENDING = "pending"
    RUNNING = "running"
    FAILED = "failed"


class JobType(StrEnum):
    """job 템플릿 타입. 타입을 추가하면 템플릿 모델(models/user_job.py)과 생성 함수(services/job_templates.py)도 함께 늘린다."""

    WEB = "web"


class JobSize(StrEnum):
    """컨테이너 크기 프리셋. 실제 cpu·memory 값은 매니페스트를 만들 때 정한다."""

    SMALL = "small"
    MEDIUM = "medium"
