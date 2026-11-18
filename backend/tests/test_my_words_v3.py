"""Personal words stay separate from Android and licensed learning progress."""

from uuid import uuid4

from app.learning_content.my_words_models import MyWord, MyWordProgress, MyWordReviewEvent
from app.learning_content.service import apply_snapshot
from app.learning_content.source import scan_source
from app.learning_content.study_models import LearningStudyProgress
from tests.test_learning_content_sync import create_run, fixture_pack, git_source


def word_payload(request_id=None):  # type: ignore[no-untyped-def]
    return {
        "request_id": str(request_id or uuid4()),
        "original_text": "学校",
        "language": "ja",
        "meanings": {"vi": ["trường học"], "en": ["school"]},
        "japanese_reading": "がっこう",
        "english_ipa": None,
        "source_url": "https://example.org/article",
        "source_title": "Reading page",
        "context": "学校へ行く",
        "tags": ["N3"],
    }


def test_my_words_crud_dedupe_and_review_preserve_learning_progress(client, db_session) -> None:  # type: ignore[no-untyped-def]
    payload = word_payload()
    created = client.post("/api/v1/my-words/", json=payload)
    assert created.status_code == 201, created.text
    word_id = created.json()["data"]["word"]["id"]
    assert created.json()["data"]["created"] is True
    assert client.post("/api/v1/my-words/", json=payload).json()["data"]["created"] is False
    same_word_new_request = word_payload()
    assert (
        client.post("/api/v1/my-words/", json=same_word_new_request).json()["data"]["created"]
        is False
    )
    assert db_session.query(MyWord).count() == 1
    assert client.get("/api/v1/my-words/?q=trường").json()["data"]["total"] == 1
    request_id = str(uuid4())
    rating = {"request_id": request_id, "rating": "good", "time_zone": "Asia/Bangkok"}
    rated = client.post(f"/api/v1/my-words/{word_id}/review", json=rating)
    assert rated.status_code == 200, rated.text
    assert rated.json()["data"]["word"]["progress"]["review_count"] == 1
    assert (
        client.post(f"/api/v1/my-words/{word_id}/review", json=rating).json()["data"]["duplicate"]
        is True
    )
    assert db_session.query(MyWordReviewEvent).count() == 1
    assert db_session.query(MyWordProgress).count() == 1
    assert db_session.query(LearningStudyProgress).count() == 0
    edited = payload.copy()
    edited.pop("request_id")
    edited["meanings"] = {"vi": ["trường học", "học đường"]}
    assert client.put(f"/api/v1/my-words/{word_id}", json=edited).status_code == 200
    invalid_edit = {**edited, "meanings": {"vi": ["  "]}}
    assert client.put(f"/api/v1/my-words/{word_id}", json=invalid_edit).status_code == 422
    invalid_url = {**edited, "source_url": "file:///private/source"}
    assert client.put(f"/api/v1/my-words/{word_id}", json=invalid_url).status_code == 422
    assert client.delete(f"/api/v1/my-words/{word_id}").status_code == 200
    assert client.get("/api/v1/my-words/").json()["data"]["total"] == 0
    assert db_session.query(MyWord).count() == 1  # soft deletion preserves reviews


def test_scoped_extension_credential_only_saves_words_and_can_be_revoked(client) -> None:  # type: ignore[no-untyped-def]
    issued = client.post("/api/v1/my-words/credentials", json={"label": "Test browser"})
    assert issued.status_code == 200, issued.text
    credential = issued.json()["data"]
    payload = word_payload()
    endpoint = "/api/v1/my-words/extension"
    assert client.post(endpoint, json=payload).status_code == 401
    headers = {"Authorization": f"Bearer {credential['token']}"}
    saved = client.post(endpoint, json=payload, headers=headers)
    assert saved.status_code == 201, saved.text
    assert saved.json()["data"]["created"] is True
    assert client.post(endpoint, json=payload, headers=headers).json()["data"]["created"] is False
    assert client.post(f"/api/v1/my-words/credentials/{credential['id']}/revoke").status_code == 200
    assert client.post(endpoint, json=word_payload(), headers=headers).status_code == 401


def test_dictionary_returns_only_verified_local_source_meanings(
    client, db_session, test_settings, tmp_path
) -> None:  # type: ignore[no-untyped-def]
    root = tmp_path / "android-fixture"
    git_source(root, fixture_pack())
    run = create_run(db_session)
    apply_snapshot(db_session, run.id, scan_source(root), test_settings)
    db_session.commit()
    response = client.get("/api/v1/dictionary/lookup", params={"q": "勉強"})
    assert response.status_code == 200
    assert response.json()["data"]["detected_language"] == "ja"
    assert response.json()["data"]["kind"] == "exact_dictionary"
    assert response.json()["data"]["entries"][0]["meaning_vi"] == "học tập"
    # No invented translation for English words without a licensed dictionary provider.
    unknown = client.get("/api/v1/dictionary/lookup", params={"q": "computer"}).json()["data"]
    assert unknown["kind"] == "unavailable" and unknown["entries"] == []
