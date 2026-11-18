from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.explanations.context import current_content_hash
from app.explanations.models import AIExplanation
from app.knowledge.models import KnowledgeItem
from app.reviews.models import ReviewItem
from app.sync.device import SyncDevice, SyncPairingCode, hash_token, issue_pairing_code


def _new_code(client: TestClient) -> str:
    response = client.post("/api/v1/sync/admin/pairing-codes", json={"expires_in_minutes": 10})
    assert response.status_code == 201, response.text
    return response.json()["data"]["pairing_code"]


def _pair(client: TestClient, key: str | None = None, name: str = "N3 Sensei test") -> str:
    code = key or _new_code(client)
    response = client.post(
        "/api/v1/sync/pair",
        headers={"X-Pairing-Key": code},
        json={"device_name": name},
    )
    assert response.status_code == 201, response.text
    return response.json()["data"]["access_token"]


def test_pairing_code_is_single_use_and_expiring(client: TestClient, db_session) -> None:
    assert (
        client.post(
            "/api/v1/sync/pair", headers={"X-Pairing-Key": "wrong"}, json={"device_name": "phone"}
        ).status_code
        == 401
    )
    code = _new_code(client)
    code_row = db_session.scalar(
        select(SyncPairingCode).where(SyncPairingCode.token_hash == hash_token(code))
    )
    assert code_row is not None
    assert code_row.token_hash != code
    assert code_row.used_at is None
    assert code_row.expires_at > datetime.now(UTC)
    response = client.post(
        "/api/v1/sync/pair",
        headers={"X-Pairing-Key": code},
        json={"device_name": "phone"},
    )
    assert response.status_code == 201
    db_session.refresh(code_row)
    assert code_row.used_at is not None
    reused = client.post(
        "/api/v1/sync/pair", headers={"X-Pairing-Key": code}, json={"device_name": "phone again"}
    )
    assert reused.status_code == 401
    assert db_session.query(SyncDevice).count() == 1

    expired_code = _new_code(client)
    expired_row = db_session.scalar(
        select(SyncPairingCode).where(SyncPairingCode.token_hash == hash_token(expired_code))
    )
    assert expired_row is not None
    expired_row.created_at = datetime.now(UTC) - timedelta(days=2)
    expired_row.expires_at = datetime.now(UTC) - timedelta(days=1)
    db_session.commit()
    expired = client.post(
        "/api/v1/sync/pair",
        headers={"X-Pairing-Key": expired_code},
        json={"device_name": "expired"},
    )
    assert expired.status_code == 401


def test_pairing_attempts_are_rate_limited(client: TestClient) -> None:
    for attempt in range(5):
        response = client.post(
            "/api/v1/sync/pair",
            headers={"X-Pairing-Key": f"invalid-code-{attempt}"},
            json={"device_name": "guess"},
        )
        assert response.status_code == (429 if attempt == 4 else 401)

    code = _new_code(client)
    blocked = client.post(
        "/api/v1/sync/pair", headers={"X-Pairing-Key": code}, json={"device_name": "phone"}
    )
    assert blocked.status_code == 429


def test_concurrent_pairing_code_rotation_leaves_one_live_code(db_session) -> None:  # type: ignore[no-untyped-def]
    engine = db_session.get_bind()

    def create_code() -> str:
        with Session(engine) as session:
            code, _ = issue_pairing_code(session)
            return code

    with ThreadPoolExecutor(max_workers=4) as executor:
        codes = list(executor.map(lambda _: create_code(), range(4)))

    active = list(
        db_session.scalars(
            select(SyncPairingCode).where(
                SyncPairingCode.used_at.is_(None), SyncPairingCode.revoked_at.is_(None)
            )
        )
    )
    assert len(active) == 1
    assert active[0].token_hash in {hash_token(code) for code in codes}


def test_admin_management_requires_secret_off_loopback_and_web_api_is_local_only(
    client: TestClient,
) -> None:
    secret = "admin-key-" + "a" * 40
    production = get_settings().model_copy(
        update={"app_env": "production", "sync_admin_key": SecretStr(secret)}
    )
    client.app.dependency_overrides[get_settings] = lambda: production
    with TestClient(
        client.app,
        base_url="https://sync.example.test",
        client=("198.51.100.20", 4567),
    ) as remote:
        assert remote.get("/api/v1/exams").status_code == 403
        assert remote.get("/api/v1/sync/admin/devices").status_code == 401
        assert (
            remote.get(
                "/api/v1/sync/admin/devices", headers={"X-Sync-Admin-Key": "wrong"}
            ).status_code
            == 401
        )
        headers = {"X-Sync-Admin-Key": secret}
        assert remote.get("/api/v1/sync/admin/devices", headers=headers).status_code == 200
        code = remote.post("/api/v1/sync/admin/pairing-codes", json={}, headers=headers).json()[
            "data"
        ]["pairing_code"]
        paired = remote.post(
            "/api/v1/sync/pair",
            headers={"X-Pairing-Key": code},
            json={"device_name": "Android phone"},
        )
        assert paired.status_code == 201


def test_remote_sync_endpoint_rejects_http(client: TestClient) -> None:
    production = get_settings().model_copy(update={"app_env": "production"})
    client.app.dependency_overrides[get_settings] = lambda: production
    with TestClient(
        client.app, base_url="http://sync.example.test", client=("198.51.100.21", 4567)
    ) as remote:
        assert remote.get("/api/v1/sync/changes").status_code == 400


def test_sync_admin_is_disabled_for_remote_access_without_configured_secret(
    client: TestClient,
) -> None:
    production = get_settings().model_copy(update={"app_env": "production", "sync_admin_key": None})
    client.app.dependency_overrides[get_settings] = lambda: production
    with TestClient(
        client.app,
        base_url="https://sync.example.test",
        client=("198.51.100.22", 4567),
    ) as remote:
        assert remote.post("/api/v1/sync/admin/pairing-codes", json={}).status_code == 503


def test_sync_activity_is_separate_and_admin_can_revoke_device(
    client: TestClient, db_session
) -> None:
    token = _pair(client, name="N3 Sensei phone")
    headers = {"Authorization": f"Bearer {token}"}
    assert client.get("/api/v1/sync/changes", headers=headers).status_code == 200
    now = datetime.now(UTC)
    event = {
        "request_id": str(uuid4()),
        "item_type": "JLPT_REVIEW_ITEM",
        "item_id": "remote-review-1",
        "rating": "GOOD",
        "reviewed_at": now.isoformat(),
        "interval_before_minutes": 0,
        "interval_after_minutes": 1440,
        "due_at_after": (now + timedelta(days=1)).isoformat(),
    }
    assert (
        client.post("/api/v1/sync/push", headers=headers, json={"events": [event]}).status_code
        == 200
    )

    device = db_session.scalar(select(SyncDevice).where(SyncDevice.token_hash == hash_token(token)))
    assert device is not None
    assert device.last_seen_at is not None
    assert device.last_pull_at is not None
    assert device.last_push_at is not None
    inventory = client.get("/api/v1/sync/admin/devices").json()["data"]
    assert inventory[0]["device_name"] == "N3 Sensei phone"
    assert inventory[0]["last_pull_at"] is not None
    assert inventory[0]["last_push_at"] is not None

    response = client.delete(f"/api/v1/sync/admin/devices/{device.id}")
    assert response.status_code == 200
    assert client.get("/api/v1/sync/changes", headers=headers).status_code == 401


def test_sync_data_endpoints_reject_missing_device_credential(client: TestClient) -> None:
    assert client.get("/api/v1/sync/changes").status_code == 401
    assert client.post("/api/v1/sync/push", json={"events": []}).status_code == 401
    assert client.post("/api/v1/sync/disconnect").status_code == 401


def test_empty_review_push_is_not_reported_as_data_pushed(client: TestClient, db_session) -> None:
    token = _pair(client)
    device = db_session.scalar(select(SyncDevice).where(SyncDevice.token_hash == hash_token(token)))
    assert device is not None
    headers = {"Authorization": f"Bearer {token}"}
    assert client.post("/api/v1/sync/push", headers=headers, json={"events": []}).status_code == 200
    db_session.refresh(device)
    assert device.last_seen_at is not None
    assert device.last_push_at is None


def test_change_feed_requires_device_and_returns_verified_key_only(
    client: TestClient, make_exam, make_question
) -> None:
    exam = make_exam()
    verified = make_question(exam["id"], 1)
    unverified = make_question(
        exam["id"], 2, question_text="未確認の問題", correct_answer=None, answer_status="missing"
    )
    assert client.get("/api/v1/sync/changes").status_code == 401
    token = _pair(client)
    response = client.get(
        "/api/v1/sync/changes?cursor=0&limit=2", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200, response.text
    page = response.json()["data"]
    assert page["has_more"] is True
    assert len(page["data"]) == 2
    cursor = page["next_cursor"]
    remaining = client.get(
        f"/api/v1/sync/changes?cursor={cursor}&limit=50",
        headers={"Authorization": f"Bearer {token}"},
    ).json()["data"]["data"]
    by_id = {
        change["entity_id"]: change["data"]
        for change in page["data"] + remaining
        if change["entity_type"] == "question"
    }
    assert verified["id"] in by_id, remaining
    assert by_id[verified["id"]]["answer_index"] == 0
    assert by_id[unverified["id"]]["answer_index"] is None


def test_android_review_push_is_idempotent_and_does_not_store_srs_projection(
    client: TestClient, db_session
) -> None:
    token = _pair(client)
    request_id = str(uuid4())
    now = datetime.now(UTC)
    event = {
        "request_id": request_id,
        "item_type": "VOCABULARY",
        "item_id": "n3-l01-v001",
        "rating": "GOOD",
        "reviewed_at": now.isoformat(),
        "interval_before_minutes": 0,
        "interval_after_minutes": 60,
        "due_at_after": (now + timedelta(hours=1)).isoformat(),
    }
    headers = {"Authorization": f"Bearer {token}"}
    first = client.post("/api/v1/sync/push", headers=headers, json={"events": [event]})
    second = client.post("/api/v1/sync/push", headers=headers, json={"events": [event]})
    assert first.status_code == second.status_code == 200
    assert first.json()["data"]["accepted"] == [request_id]
    assert second.json()["data"]["duplicates"] == [request_id]
    collision = client.post(
        "/api/v1/sync/push",
        headers=headers,
        json={"events": [{**event, "rating": "EASY"}]},
    )
    assert collision.status_code == 409
    from app.sync.models import AndroidReviewEvent

    assert len(list(db_session.scalars(select(AndroidReviewEvent)))) == 1


def test_feed_publishes_knowledge_and_review_items_with_snapshots(
    client: TestClient, db_session, make_exam, make_question
) -> None:
    exam = make_exam()
    question = make_question(exam["id"], 1)
    knowledge = KnowledgeItem(
        knowledge_type="grammar",
        jlpt_level="N3",
        title="〜ので",
        content="Vì",
        canonical_key="node:test:node",
        details={"note": "snapshot"},
        status="active",
    )
    db_session.add(knowledge)
    db_session.flush()
    review = ReviewItem(
        review_type="original_question",
        dedup_key=f"q:{question['id']}",
        source_question_id=question["id"],
        status="active",
        srs_state="new",
        step_index=None,
        interval_minutes=0,
        review_count=0,
        lapse_count=0,
        algorithm_version="ladder-v1",
        ladder="20m,1h,1d",
        version=1,
    )
    db_session.add(review)
    db_session.commit()

    token = _pair(client)
    response = client.get(
        "/api/v1/sync/changes?limit=500", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200, response.text
    rows = response.json()["data"]["data"]
    knowledge_row = next(
        row
        for row in rows
        if row["entity_type"] == "knowledge_item" and row["entity_id"] == str(knowledge.id)
    )
    review_row = next(
        row
        for row in rows
        if row["entity_type"] == "review_item" and row["entity_id"] == str(review.id)
    )
    assert knowledge_row["schema_version"] == "1.0"
    assert knowledge_row["data"]["details"] == {"note": "snapshot"}
    assert review_row["data"]["source_question_id"] == question["id"]


def test_revoked_device_cannot_continue_incremental_sync(client: TestClient) -> None:
    token = _pair(client)
    headers = {"Authorization": f"Bearer {token}"}
    assert client.post("/api/v1/sync/disconnect", headers=headers).status_code == 200
    response = client.get("/api/v1/sync/changes?cursor=0", headers=headers)
    assert response.status_code == 401


def test_approved_explanation_is_published_then_tombstoned_when_stale(
    client: TestClient, db_session, make_exam, make_question
) -> None:
    from app.exams.models import Question

    exam = make_exam()
    question_data = make_question(exam["id"], 1)
    question = db_session.get(Question, question_data["id"])
    assert question is not None
    digest = current_content_hash(db_session, question)
    explanation = AIExplanation(
        question_id=question.id,
        provider="manual",
        model="local",
        explanation_json={"summary": "approved"},
        verification_status="approved",
        origin="manual",
        prompt_version="manual-v1",
        schema_version="1.0",
        content_hash=digest,
        cache_key=f"test:{question.id}",
        reviewed_at=datetime.now(UTC),
    )
    db_session.add(explanation)
    db_session.commit()
    token = _pair(client)
    headers = {"Authorization": f"Bearer {token}"}
    first = client.get("/api/v1/sync/changes?limit=500", headers=headers).json()["data"]["data"]
    row = next(item for item in first if item["entity_type"] == "ai_explanation")
    assert row["operation"] == "insert" and row["data"]["verification_status"] == "approved"
    cursor = row["cursor"]
    question.question_text = question.question_text + " changed"
    db_session.commit()
    after = client.get(f"/api/v1/sync/changes?cursor={cursor}&limit=500", headers=headers).json()[
        "data"
    ]["data"]
    explanation_change = next(item for item in after if item["entity_type"] == "ai_explanation")
    assert explanation_change["operation"] == "delete"
    assert explanation_change["data"] is None
