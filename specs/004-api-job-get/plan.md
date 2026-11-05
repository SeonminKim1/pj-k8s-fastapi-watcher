# 구현 계획: job 단건 조회 API

- **브랜치**: `004-api-job-get` | **작성일**: 2026-11-06 | **spec**: [spec.md](spec.md)

## 요약 (Summary)
`GET /jobs/{job_id}`를 추가한다. 도메인 service `get_job`과 생성 응답 schema `JobResponse`를 그대로 쓰고, 이 엔드포인트에만 404 응답 문서를 붙인다. 형식이 틀린 ID는 schema에서 막지 않고 없음으로 응답한다(결정 근거는 [research.md](research.md)).

## 기술 맥락 (Technical Context)
- **언어/버전**: Python (uv)
- **주요 의존성**: FastAPI, Pydantic (새 의존성 없음)
- **저장소**: MongoDB `user_jobs` (읽기만, `_id` 조회)
- **테스트**: `uv run pytest`. router 테스트(가짜 service), service `get_job` 테스트는 기존 것 사용
- **실행 환경**: 로컬 MongoDB + kubeconfig
- **유형**: HTTP API
- **성능·제약**: 없음(단건 `_id` 조회)

## Constitution Check
| 원칙·요구사항 | 이 기능에서 지키는 방법 | 결과 |
|---|---|---|
| II. 레이어 | router는 헤더 파싱 → `service.get_job()` 하나 → `JobResponse.from_job()` | 통과 |
| III. 테스트 | 소유권·없음·삭제됨·잘못된 ID는 기존 service 테스트(`test_get_job_not_found`)가 다룬다. router 테스트로 200·404·400·문서 확인 | 통과 |
| IV. 에러 표현 | 새 `ErrorEnum` 없음. `JOB_NOT_FOUND` 404, `INVALID_USER_ID` 400. 에러 표는 [contracts/get-job.md](contracts/get-job.md) | 통과 |
| V. 단순함 | 응답 schema·service 재사용, 새 모델 없음 | 통과 |
| 스택: API 문서(에러 응답) | 400·500은 라우터 공통 `COMMON_ERROR_RESPONSES`, 이 엔드포인트만 돌려주는 404는 엔드포인트의 `responses`에 `NOT_FOUND_RESPONSES`. 200·404 example은 schema 모듈 상수 | 통과 |
| 스택: 레이어(라우터 반환) | `models/` 객체가 아니라 `JobResponse` 반환 | 통과 |
| `CLAUDE.md`: 에러 상태 코드 | 남의 리소스는 404로 없음과 같게 | 통과 |
| `CLAUDE.md`: operator 패턴 | MongoDB만 읽음 | 통과 |

## 프로젝트 구조 (Project Structure)

### 변경 파일 (Source Code)
- `src/schemas/error_response.py`: `NOT_FOUND_RESPONSES`(404: `ErrorResponse` + `job_not_found` example) 추가. `COMMON_ERROR_RESPONSES` 주석의 code 목록 기준을 "각 기능의 contracts 에러 표"로
- `src/models/`: 없음
- `src/repository/`: 없음
- `src/services/`: 없음(`UserJobService.get_job` 사용)
- `src/routers/job_router.py`: `GET /jobs/{job_id}`(`response_model=JobResponse`, `description`에 contracts 경로, `responses`에 200 example `JOB_RESPONSE_EXAMPLE`과 `NOT_FOUND_RESPONSES`)
- `src/core/`, `src/main.py`: 없음
- `tests/test_job_router.py`: 가짜 service에 `get_job`. 200 응답 형태·전달 인자, `JOB_NOT_FOUND` 404 본문, 헤더 없음·형식 오류 400(service 미호출), OpenAPI(200·400·404·500, 404 example, 다른 엔드포인트에 404 없음, 200 example이 `JobResponse`로 검증)
- 문서: `README.md` API 표에 `GET /jobs/{job_id}`, 에러 상세 링크에 contracts 추가

### DB 변경
- 없음

### 외부 의존성
- 없음

## 리스크 / 확인 필요
- 없음. 읽기 전용이고 기존 service·schema를 그대로 쓴다.
