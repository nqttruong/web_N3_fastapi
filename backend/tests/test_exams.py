import uuid

from fastapi.testclient import TestClient


def test_create_and_get_exam_preserves_japanese(client: TestClient) -> None:
    payload = {
        "title": "  N3 語彙 模擬テスト「第１回」  ",
        "category": "vocabulary",
        "description": "漢字読み・表記・文脈規定 — tự biên soạn",
        "source_url": "https://example.com/jlpt/n3/vocab-1",
    }
    created = client.post("/api/v1/exams", json=payload)
    assert created.status_code == 201
    exam = created.json()["data"]
    assert exam["title"] == "N3 語彙 模擬テスト「第１回」"  # trimmed, full-width kept as-is
    assert exam["level"] == "N3"
    assert exam["status"] == "draft"
    assert exam["question_count"] == 0

    fetched = client.get(f"/api/v1/exams/{exam['id']}").json()["data"]
    assert fetched["description"] == payload["description"]
    assert fetched["created_at"].endswith("Z") or "+00:00" in fetched["created_at"]


def test_create_exam_validation(client: TestClient) -> None:
    bad = [
        {"category": "grammar"},  # missing title
        {"title": "x", "category": "listening"},  # unknown category
        {"title": "x", "category": "grammar", "level": "N6"},
        {"title": "x", "category": "grammar", "source_url": "ftp://example.com"},
        {"title": "x", "category": "grammar", "unknown_field": 1},  # extra=forbid
    ]
    for payload in bad:
        response = client.post("/api/v1/exams", json=payload)
        assert response.status_code == 422, payload
        assert response.json()["error"]["code"] == "validation_error"


def test_duplicate_source_url_conflicts(client: TestClient, make_exam) -> None:  # type: ignore[no-untyped-def]
    make_exam(source_url="https://example.com/a")
    response = client.post(
        "/api/v1/exams",
        json={"title": "other", "category": "kanji", "source_url": "https://example.com/a"},
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "conflict"


def test_unknown_source_id_rejected(client: TestClient) -> None:
    response = client.post(
        "/api/v1/exams", json={"title": "x", "category": "kanji", "source_id": str(uuid.uuid4())}
    )
    assert response.status_code == 422


def test_get_missing_exam_404(client: TestClient) -> None:
    response = client.get(f"/api/v1/exams/{uuid.uuid4()}")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"
    assert client.get("/api/v1/exams/not-a-uuid").status_code == 422


def test_patch_exam(client: TestClient, make_exam) -> None:  # type: ignore[no-untyped-def]
    exam = make_exam(description="cũ")
    response = client.patch(
        f"/api/v1/exams/{exam['id']}", json={"status": "ready", "description": None}
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["status"] == "ready"
    assert data["description"] is None
    assert data["title"] == exam["title"]

    assert client.patch(f"/api/v1/exams/{exam['id']}", json={"title": None}).status_code == 422
    assert client.patch(f"/api/v1/exams/{exam['id']}", json={}).status_code == 422
    assert (
        client.patch(f"/api/v1/exams/{uuid.uuid4()}", json={"status": "ready"}).status_code == 404
    )


def test_list_exams_pagination_search_filter(client: TestClient, make_exam) -> None:  # type: ignore[no-untyped-def]
    for i in range(5):
        make_exam(title=f"文法 {i}", category="grammar")
    make_exam(title="読解 長文", category="reading")
    make_exam(title="100% 漢字", category="kanji")

    page1 = client.get("/api/v1/exams", params={"page": 1, "page_size": 3}).json()
    assert page1["meta"] == {"page": 1, "page_size": 3, "total": 7, "total_pages": 3}
    assert len(page1["data"]) == 3
    assert page1["data"][0]["attempt_count"] == 0
    assert page1["data"][0]["latest_attempt_started_at"] is None
    assert page1["data"][0]["approved_explanation_count"] == 0
    page3 = client.get("/api/v1/exams", params={"page": 3, "page_size": 3}).json()
    assert len(page3["data"]) == 1
    ids = {
        e["id"]
        for p in (1, 2, 3)
        for e in client.get("/api/v1/exams", params={"page": p, "page_size": 3}).json()["data"]
    }
    assert len(ids) == 7  # stable ordering, no duplicates across pages

    grammar = client.get("/api/v1/exams", params={"category": "grammar"}).json()
    assert grammar["meta"]["total"] == 5
    search = client.get("/api/v1/exams", params={"q": "読解"}).json()
    assert [e["title"] for e in search["data"]] == ["読解 長文"]
    # LIKE wildcards are escaped
    assert client.get("/api/v1/exams", params={"q": "%"}).json()["meta"]["total"] == 1

    assert client.get("/api/v1/exams", params={"page": 0}).status_code == 422
    assert client.get("/api/v1/exams", params={"page_size": 101}).status_code == 422
    assert client.get("/api/v1/exams", params={"category": "nope"}).status_code == 422


def test_exam_sources(client: TestClient) -> None:
    created = client.post(
        "/api/v1/exam-sources", json={"name": "Tự biên soạn", "base_url": "https://example.com"}
    )
    assert created.status_code == 201
    dup = client.post(
        "/api/v1/exam-sources", json={"name": "Tự biên soạn", "base_url": "https://x.example"}
    )
    assert dup.status_code == 409
    source_id = created.json()["data"]["id"]
    exam = client.post(
        "/api/v1/exams", json={"title": "x", "category": "kanji", "source_id": source_id}
    ).json()["data"]
    assert exam["source_name"] == "Tự biên soạn"
