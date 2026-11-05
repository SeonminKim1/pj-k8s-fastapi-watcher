# 리서치: job 단건 조회 API

## job ID 형식 검사
- **결정**: path의 `job_id`는 `str`로 받고 schema에서 형식을 검사하지 않는다. 형식이 틀린 ID는 service `get_job`이 `JOB_NOT_FOUND`로 응답한다.
- **근거**: 도메인 규칙(`specs/001-domain-user-job/data-model.md` "get_job")이 잘못된 ID를 없음과 같게 본다. schema에서 막으면 400이 되어 FR-003(구분되지 않음)과 어긋나고, 새 `ErrorEnum`도 필요하다.
- **검토한 대안**: ObjectId 형식을 schema에서 검사해 400 `invalid_job_id` — 남의 job·없는 job과 응답이 달라지고 규칙이 두 곳에 생긴다.

## 응답 모양
- **결정**: 생성 응답 schema `JobResponse`를 그대로 쓰고, 200 example도 `JOB_RESPONSE_EXAMPLE`을 함께 쓴다.
- **근거**: spec 가정(상세 = 생성 응답). 같은 모델이라 클라이언트가 모델 하나를 쓰고, 항목을 늘릴 때 두 응답이 함께 바뀐다.
- **검토한 대안**: 상세 전용 `JobDetailResponse` — 지금은 항목이 같아 중복이다.

## 404 응답 문서
- **결정**: `src/schemas/error_response.py`에 `JOB_NOT_FOUND_RESPONSES`(404: `ErrorResponse` + `job_not_found` example)를 두고 `GET /jobs/{job_id}`에만 붙인다. 400·500은 라우터 공통(`COMMON_ERROR_RESPONSES`) 그대로.
- **근거**: 스택 파일 "API 문서"의 에러 응답 규칙: 라우터의 모든 엔드포인트가 돌려주는 것(400·500)은 `APIRouter(responses=...)`로 한 번, 일부 엔드포인트만 돌려주는 것(404)은 그 엔드포인트에 붙이고, `/docs`에는 실제로 돌려주는 상태 코드만 보인다. 404는 이 엔드포인트만 돌려준다.
- **검토한 대안**: 라우터 공통에 404 추가 — `POST /jobs`·`GET /jobs`에 나지 않는 404가 문서에 보인다.

## 헤더 에러 우선순위
- **결정**: 헤더는 기존 `UserIdHeader`로 받는다. `job_id`는 `str`이라 요청 검증 에러가 나지 않으므로 헤더 에러(`invalid_user_id`)가 항상 먼저 나간다.
- **근거**: FastAPI가 path·header 검증을 함께 모으고, 실패하면 핸들러 본문(service 호출)이 실행되지 않는다.
