# 리서치: user-job 도메인 모델

## MongoDB 접근 방식
- **결정**: 비동기 `AsyncMongoClient(tz_aware=True)`. repository·service 메서드는 모두 `async def`, 라우터도 `async def`.
- **근거**: FastAPI 이벤트 루프를 막지 않는다. `pymongo` 4.19에 내장돼 새 패키지가 필요 없다. operator에서 동기 `kubernetes` 클라이언트를 부를 때는 `asyncio.to_thread`로 감싼다(operator 기능에서 다룸).
- **검토한 대안**: 동기 `MongoClient` — 기존 코드였지만 async 라우터와 섞이면 루프를 막는다.

## 시각
- **결정**: UTC aware `datetime`. 읽을 때도 `tz_aware=True`로 UTC aware.
- **근거**: cursor·정렬·응답 직렬화에서 타임존이 흔들리지 않는다.

## 이름 중복을 service에 전달하는 방법
- **결정**: repository가 `DuplicateKeyError`를 잡아 `keyPattern`이 이름 인덱스(`uniq_owner_name`)일 때만 `DuplicateJobNameError`로 바꾸고, service가 `JOB_NAME_DUPLICATED`로 바꾼다. 다른 유니크 위반은 그대로 올려 500.
- **근거**: service가 pymongo 예외에 의존하지 않는다. 다른 인덱스 위반을 이름 중복으로 잘못 알리지 않는다(코드 리뷰 반영).

## 잘못된 ObjectId
- **결정**: repository가 `None`으로 처리하고 service는 "없음"과 같게 `JOB_NOT_FOUND`.
- **근거**: 남의 job·없음·삭제됨·잘못된 ID를 구분하지 않아 존재를 드러내지 않는다.

## 상태 갱신의 원자성
- **결정**: 목표 상태로 갈 수 있는 이전 상태 목록으로 `status: {$in: [...]}` 조건부 갱신 1회. 실패하면 다시 읽어 없음·같은 상태(멱등)·허용 안 됨을 판단한다. 재시도하지 않는다.
- **근거**: 읽기 → 판단 → 조건부 갱신 × 재시도 방식은 재시도 상수가 필요하고, 재시도 소진 시 허용된 전이를 `INVALID_STATUS_TRANSITION`으로 잘못 알렸다(코드 리뷰 4·5·6).
- **검토한 대안**: 최대 3회 재시도(초기 구현) — 위 이유로 바꿈.

## 클러스터 설정 로딩 시점
- **결정**: `get_k8s_service()`를 `functools.cache`로 한 번만 만들고, lifespan에서 MongoDB보다 먼저 호출해 설정이 없으면 앱 시작을 실패시킨다. import 시점에는 읽지 않는다.
- **근거**: 테스트가 import만으로 클러스터에 붙지 않는다. 설정 없이 떠서 operator가 늦게 실패하는 것보다 시작 때 실패가 낫다(작업 확인 중 요청).
