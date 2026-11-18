from fastapi.testclient import TestClient


def test_health_ok(client: TestClient) -> None:
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json()["data"] == {
        "status": "ok",
        "database": "ok",
        "environment": response.json()["data"]["environment"],
        "version": "0.1.0",
    }


def test_openapi_is_published(client: TestClient) -> None:
    spec = client.get("/api/v1/openapi.json").json()
    for path in ("/api/v1/exams", "/api/v1/exams/{exam_id}/questions", "/api/v1/attempts"):
        assert path in spec["paths"]


def test_unknown_route_uses_error_envelope(client: TestClient) -> None:
    response = client.get("/api/v1/does-not-exist")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def test_cors_allows_only_configured_origins(client: TestClient) -> None:
    allowed = client.options(
        "/api/v1/exams",
        headers={"Origin": "http://localhost:3000", "Access-Control-Request-Method": "GET"},
    )
    assert allowed.headers.get("access-control-allow-origin") == "http://localhost:3000"
    denied = client.options(
        "/api/v1/exams",
        headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "GET"},
    )
    assert "access-control-allow-origin" not in denied.headers
