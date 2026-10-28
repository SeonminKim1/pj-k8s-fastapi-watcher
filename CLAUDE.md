# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 프로젝트 개요
쿠버네티스 인프라를 관리하는 서비스. REST API로 클러스터 리소스(Namespace, Deployment 등)를 조회·생성·삭제하고, 백그라운드 watch 컴포넌트로 리소스 변경을 감지해 상태를 동기화한다. 스택: FastAPI + MongoDB + Kubernetes API(공식 `kubernetes` Python 클라이언트).

공통 규칙: @docs/fastapi-sdd-template.md

## 프로젝트 고유 구성
- `src/core/db/mongodb.py`: 공유 `MongoClient`(`get_client()`/`get_database()`). 환경 변수 `MONGO_URI`(기본 `mongodb://localhost:27017`), `MONGO_DB_NAME`(기본 `k8s_client`). repository에서만 사용한다.
- `src/services/k8s_service.py`: `K8sService` 래퍼. in-cluster 설정을 먼저 시도하고 실패하면 kubeconfig를 읽는다. 클러스터 접근은 반드시 이 클래스를 거친다(테스트에서는 가짜 객체로 대체).
- `src/main.py`: `PyMongoError`는 500 `db_error`로 처리한다.

## 프로젝트 상세 설명 (요구사항)
- HTTP API 기능은 `docs/api-*`, watch 같은 백그라운드 기능은 `docs/component-*` 폴더로 문서화한다.
