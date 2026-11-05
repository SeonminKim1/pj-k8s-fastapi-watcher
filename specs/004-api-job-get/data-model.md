# 데이터 모델: job 단건 조회 API

변경 없음 — `src/models/user_job_models.py`의 `UserJob`(`specs/001-domain-user-job/data-model.md`)을 읽기만 한다. 응답은 `src/schemas/job_response.py`의 `JobResponse`(`specs/002-api-job-create/contracts/post-jobs.md` "응답")를 쓴다.

## 조회 조건
- `find_active_by_id(job_id)`: 잘못된 ObjectId·없음·삭제됨이면 `None`. service가 `owner_id`가 다르면 `None`과 같게 `JOB_NOT_FOUND`.
- 인덱스: `_id` 기본 인덱스만 쓴다(변경 없음).
