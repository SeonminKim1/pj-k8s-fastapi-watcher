from fastapi.testclient import TestClient

from src.main import app

client = TestClient(app)


# 앱이 import·기동되고 OpenAPI 문서가 열리는지 확인한다.
def test_openapi_docs() -> None:
    response = client.get("/docs")
    assert response.status_code == 200
