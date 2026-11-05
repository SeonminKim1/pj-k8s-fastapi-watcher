# 기능 명세: user-job 도메인 모델

- **브랜치**: `001-domain-user-job`
- **작성일**: 2026-10-27
- **상태**: 확정
- **입력**: "user-job 도메인 모델, 저장소, 의존성 주입 구조"

## 개요 (Overview)
- **배경/목적**: 서비스의 모든 기능(job 생성·조회·삭제 API, operator)이 같은 user-job 모델을 기준으로 동작한다. API나 operator를 만들기 전에 모델과 저장 방식, 의존성 주입 구조를 먼저 정해 이후 기능들이 같은 기준을 쓰게 한다.
- **대상 사용자**: 이후 기능을 구현하는 개발자(내부 service·repository 계층). 최종 사용자에게 직접 노출되지 않는다.
- **완료 기준**: service를 통해 유저별로 job을 저장하고, 자기 job 목록·단건을 조회하고, 상태를 갱신하고, 삭제할 수 있으며, 이를 확인하는 service 테스트가 가짜 repository 주입으로 통과한다. `K8sService`는 `src/core/dependencies.py`에서만 만들어진다.
- **범위 제외**:
  - HTTP API(생성·조회·삭제 엔드포인트) → `002-api-job-create`, `003-api-job-list`, 이후 `api-job-*`
  - `K8sService`의 리소스 생성·삭제·watch 메서드와 operator 자체 → 이후 `component-job-operator`
- **관련 요구사항**: `CLAUDE.md`의 "유저 식별", "유저별 네임스페이스", "유저별 job 개수 제한", "에러 상태 코드", "핵심 도메인 — user-job", "job 입력은 템플릿 방식", "operator 패턴", 스택 파일의 "의존성 주입"

## 유저 시나리오와 테스트 (User Scenarios & Testing) *(필수)*

### 유저 스토리 1 - 유저별 job 저장과 조회 (우선순위: P1)
기능 개발자가 service로 유저의 job을 템플릿 입력으로 저장하고, 그 유저의 job 목록·단건을 다시 읽는다.

- **이 우선순위인 이유**: 모든 API와 operator가 이 저장·조회를 기준으로 동작한다.
- **독립 테스트**: 가짜 repository를 주입한 service 테스트로 저장 → 목록·단건 조회가 확인된다.
- **인수 시나리오**:
  1. **Given** 유저 `alice`의 job이 없음, **When** 이름 `my-web`, `web` 템플릿으로 `create_job`, **Then** `pending` 상태, 네임스페이스 `user-alice`, Deployment·Service 리소스를 가진 job이 저장되어 반환된다.
  2. **Given** `alice`와 `bob`의 job이 있음, **When** `alice`로 목록·단건 조회, **Then** `alice`의 삭제되지 않은 job만 나온다.
  3. **Given** `alice`의 삭제되지 않은 job이 10개, **When** 11번째 `create_job`, **Then** `JOB_QUOTA_EXCEEDED`.

### 유저 스토리 2 - operator의 상태 갱신 (우선순위: P2)
operator가 클러스터를 관찰한 결과로 job 상태를 바꾼다.

- **이 우선순위인 이유**: 유저는 job `status`로 진행 상황을 본다(`CLAUDE.md` "operator 패턴"). operator 구현 전에 전이 규칙이 정해져 있어야 한다.
- **독립 테스트**: service 테스트로 허용 전이·거부 전이·같은 상태 갱신이 확인된다.
- **인수 시나리오**:
  1. **Given** `pending` job, **When** `running`으로 갱신, **Then** 상태와 `updated_at`이 바뀐다.
  2. **Given** `running` job, **When** `pending`으로 갱신, **Then** `INVALID_STATUS_TRANSITION`.
  3. **Given** `running` job, **When** 다시 `running`으로 갱신, **Then** 아무것도 바꾸지 않고 그대로 반환(멱등).

### 유저 스토리 3 - job 삭제 (우선순위: P3)
유저의 job을 삭제 표시(soft delete)하고 개수 한도에서 뺀다.

- **이 우선순위인 이유**: 한도가 있으므로 삭제가 있어야 다시 만들 수 있다. 클러스터 정리는 operator 몫이라 문서 표시만 하면 된다.
- **독립 테스트**: service 테스트로 삭제 후 조회 불가·한도 슬롯 반환이 확인된다.
- **인수 시나리오**:
  1. **Given** `alice`의 job, **When** `delete_job`, **Then** 이후 조회는 `JOB_NOT_FOUND`이고 개수에서 빠진다.
  2. **Given** `bob`의 job, **When** `alice`로 `delete_job`, **Then** `JOB_NOT_FOUND`(남의 job 존재를 드러내지 않음).

### 엣지 케이스 (Edge Cases)
- 유저 ID·job 이름이 형식에 맞지 않을 때(schema를 거치지 않는 호출자 포함)?
- 같은 이름의 job을 동시에 두 번 저장할 때? 한도 근처에서 동시에 여러 개 저장할 때?
- 삭제된 job과 같은 이름으로 다시 만들 때?
- 다른 유저의 job, 없는 job, 삭제된 job, ObjectId 형식이 아닌 ID로 조회·삭제할 때?
- 이미 같은 상태로 갱신할 때(이벤트 재전송·resync)? 허용되지 않는 전이일 때?
- MongoDB 오류일 때? 클러스터 설정이 없을 때 앱을 시작하면?

## 요구사항 (Requirements) *(필수)*

### 기능 요구사항 (Functional Requirements)
- **FR-001**: job의 소유자는 `X-User-Id` 유저 ID이며, 유저 ID 형식이 아니면 `INVALID_USER_ID`로 거절해야 한다(모든 owner_id 인자).
- **FR-002**: job은 소유자 네임스페이스 `user-{owner_id}`에 속하며, 네임스페이스는 서버가 정한다.
- **FR-003**: job은 유저 템플릿 입력(지금은 `web`)과, 서버가 템플릿으로 생성한 구성 리소스(1개 이상, 매니페스트 원본 포함)를 저장해야 한다.
- **FR-004**: job 이름은 DNS-1035 label이어야 하고, 삭제되지 않은 자기 job끼리 중복될 수 없다(동시 요청 포함). 삭제된 job의 이름은 다시 쓸 수 있다.
- **FR-005**: 유저당 삭제되지 않은 job은 10개까지이며, 동시 요청에서도 넘지 않아야 한다.
- **FR-006**: 소유자만 자기 job을 조회·삭제할 수 있다. 남의 job·없음·삭제됨·잘못된 ID는 모두 `JOB_NOT_FOUND`로 같게 응답한다.
- **FR-007**: 목록은 삭제되지 않은 자기 job을 최신순으로, cursor 페이지네이션과 `status` 필터로 돌려준다(상세 `003-api-job-list`).
- **FR-008**: 상태는 `pending`/`running`/`failed`이고, 정해진 전이만 허용하며, 같은 상태 갱신은 멱등 성공이다. 갱신은 operator 전용이다.
- **FR-009**: 삭제는 soft delete(`is_deleted`, `deleted_at`)이며 개수 한도에서 빠진다. 클러스터 정리는 operator가 한다.
- **FR-010**: service·repository·`K8sService`는 생성자로 의존 객체를 받고, 실제 객체는 `src/core/dependencies.py`에서만 조립한다. import 시점에는 클러스터에 접근하지 않는다.
- **FR-011**: 앱 시작 시 클러스터 설정을 먼저 읽고(없으면 시작 실패) 인덱스를 만들며, 종료 시(시작 도중 실패 포함) MongoDB·K8s 연결을 닫는다.

### 핵심 엔티티 (Key Entities)
- **UserJob**: 한 유저의 쿠버네티스 리소스 묶음. 소유자, 네임스페이스, 이름, 템플릿 입력, 구성 리소스, 상태, 한도 슬롯, 삭제 여부, 시각.
- **JobTemplate**: 타입으로 구분하는 유저 입력. 지금은 `web`(이미지, 포트, 레플리카, 환경 변수, 크기 프리셋).
- **JobResource**: 서버가 생성한 리소스 하나(apiVersion, kind, 이름, 매니페스트 원본).

## 성공 기준 (Success Criteria) *(필수)*
- **SC-001**: 이후 기능(API, operator)이 모델·service를 바꾸지 않고 주입받아 쓸 수 있다.
- **SC-002**: 비즈니스 규칙(소유권, 한도, 이름 중복, 상태 전이, soft delete)마다 service 테스트가 실제 DB 없이 통과한다.
- **SC-003**: 동시 저장 15개에서 정확히 10개만 성공한다(로컬 MongoDB 확인).

## 가정 (Assumptions)
- 다른 유저의 job 접근은 존재를 드러내지 않도록 404로 같게 처리한다.
- 운영 데이터가 없어 기존 문서 마이그레이션은 하지 않는다. `template`이 없는 개발 DB 문서는 지운다.
- 템플릿 타입을 추가해도 operator, 개수 한도, 상태 전이는 타입과 무관하다.
