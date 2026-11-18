"""Web QR protocol with a simulated future Android client; no Android files touched."""

import secrets
import uuid
from datetime import UTC, datetime, timedelta

from pydantic import SecretStr

from app.core.config import get_settings
from app.sync.device import SyncDevice, SyncPairingAttempt, hash_token
from app.sync.qr_models import SyncQRAudit, SyncQRSession


def create_session(client, test_settings):  # type: ignore[no-untyped-def]
    client.app.dependency_overrides[get_settings] = lambda: test_settings.model_copy(
        update={"sync_public_https_base_url": "https://jlpt.example.test"}
    )
    response = client.post("/api/v1/sync/admin/qr-sessions")
    assert response.status_code == 201, response.text
    return response.json()["data"]


def test_mock_android_qr_claim_confirm_pull_and_revoke(client, db_session, test_settings) -> None:  # type: ignore[no-untyped-def]
    created = create_session(client, test_settings)
    qr = created["qr_payload"]
    assert qr["version"] == 1 and qr["base_url"].startswith("https://")
    assert "access_token" not in str(qr)
    session_id = qr["session_id"]
    credential = secrets.token_urlsafe(48)
    claim_body = {
        "challenge": qr["challenge"],
        "device_name": "Mock Android",
        "device_credential": credential,
    }
    path = f"/api/v1/sync/qr-sessions/{session_id}"
    assert (
        client.post(path + "/claim", json={**claim_body, "challenge": "x" * 32}).status_code == 401
    )
    assert (
        client.post(path + "/claim", json={**claim_body, "device_name": "   "}).status_code == 422
    )
    assert (
        client.post(path + "/claim", json={**claim_body, "unexpected": "field"}).status_code == 422
    )
    claimed = client.post(path + "/claim", json=claim_body)
    assert claimed.status_code == 200, claimed.text
    claim = claimed.json()["data"]
    assert "device_credential" not in claim
    assert client.post(path + "/claim", json=claim_body).json()["data"] == claim
    assert client.get(path, headers={"X-Claim-Ticket": "invalid"}).status_code == 401
    assert (
        client.post(
            f"/api/v1/sync/admin/qr-sessions/{session_id}/confirm",
            json={"confirmation_code": claim["confirmation_code"]},
        ).status_code
        == 409
    )
    ready = client.post(path + "/ready", headers={"X-Claim-Ticket": claim["claim_ticket"]})
    assert ready.json()["data"]["status"] == "AWAITING_CONFIRMATION"
    assert (
        client.post(
            f"/api/v1/sync/admin/qr-sessions/{session_id}/confirm",
            json={
                "confirmation_code": "000000"
                if claim["confirmation_code"] != "000000"
                else "999999"
            },
        ).status_code
        == 401
    )
    confirmed = client.post(
        f"/api/v1/sync/admin/qr-sessions/{session_id}/confirm",
        json={"confirmation_code": claim["confirmation_code"]},
    )
    assert confirmed.status_code == 200, confirmed.text
    assert confirmed.json()["data"]["status"] == "PAIRED"
    assert (
        client.post(
            f"/api/v1/sync/admin/qr-sessions/{session_id}/confirm",
            json={"confirmation_code": claim["confirmation_code"]},
        ).status_code
        == 200
    )
    assert client.post(path + "/claim", json=claim_body).status_code == 409
    assert (
        client.get(path, headers={"X-Claim-Ticket": claim["claim_ticket"]}).json()["data"]["status"]
        == "PAIRED"
    )
    bearer = {"Authorization": f"Bearer {credential}"}
    assert client.get("/api/v1/sync/changes", headers=bearer).status_code == 200
    device_id = confirmed.json()["data"]["device_id"]
    device = db_session.get(SyncDevice, uuid.UUID(device_id))
    assert device is not None
    assert device.token_hash == hash_token(credential)
    assert device.token_hash != credential
    assert client.delete(f"/api/v1/sync/admin/devices/{device_id}").status_code == 200
    assert client.get("/api/v1/sync/changes", headers=bearer).status_code == 401
    db_session.refresh(device)
    assert device.revoked_at is not None
    assert db_session.query(SyncQRAudit).filter_by(session_id=uuid.UUID(session_id)).count() >= 5


def test_qr_expiry_cancel_and_configuration_guard(client, db_session, test_settings) -> None:  # type: ignore[no-untyped-def]
    assert client.post("/api/v1/sync/admin/qr-sessions").status_code == 503
    created = create_session(client, test_settings)
    path = f"/api/v1/sync/qr-sessions/{created['id']}"
    session = db_session.get(SyncQRSession, uuid.UUID(created["id"]))
    session.expires_at = datetime.now(UTC) - timedelta(seconds=1)
    db_session.commit()
    response = client.post(
        path + "/claim",
        json={
            "challenge": created["qr_payload"]["challenge"],
            "device_name": "Too late",
            "device_credential": secrets.token_urlsafe(48),
        },
    )
    assert response.status_code == 409
    db_session.refresh(session)
    assert session.status == "EXPIRED"
    another = create_session(client, test_settings)
    assert (
        client.post(f"/api/v1/sync/admin/qr-sessions/{another['id']}/cancel").json()["data"][
            "status"
        ]
        == "CANCELLED"
    )
    rejected = create_session(client, test_settings)
    claim = client.post(
        f"/api/v1/sync/qr-sessions/{rejected['id']}/claim",
        json={
            "challenge": rejected["qr_payload"]["challenge"],
            "device_name": "Unknown",
            "device_credential": secrets.token_urlsafe(48),
        },
    )
    assert claim.status_code == 200
    assert (
        client.post(f"/api/v1/sync/admin/qr-sessions/{rejected['id']}/reject").json()["data"][
            "status"
        ]
        == "REJECTED"
    )
    assert (
        client.post(
            f"/api/v1/sync/qr-sessions/{rejected['id']}/ready",
            headers={"X-Claim-Ticket": claim.json()["data"]["claim_ticket"]},
        ).status_code
        == 409
    )


def test_qr_rejects_loopback_base_url(client, test_settings) -> None:  # type: ignore[no-untyped-def]
    client.app.dependency_overrides[get_settings] = lambda: test_settings.model_copy(
        update={"sync_public_https_base_url": "https://127.0.0.1:8000"}
    )
    assert client.post("/api/v1/sync/admin/qr-sessions").status_code == 503


def test_qr_rejects_non_https_or_non_origin_urls(client, test_settings) -> None:  # type: ignore[no-untyped-def]
    for value in (
        "http://jlpt.example.test",
        "https://localhost",
        "https://jlpt.example.test/api/v1",
        "https://user:pass@jlpt.example.test",
        "https://jlpt.example.test?next=/",
    ):
        client.app.dependency_overrides[get_settings] = lambda value=value: (
            test_settings.model_copy(update={"sync_public_https_base_url": value})
        )
        assert client.post("/api/v1/sync/admin/qr-sessions").status_code == 503


def test_remote_qr_management_requires_admin_credential(client, test_settings) -> None:  # type: ignore[no-untyped-def]
    secret = "sync-admin-secret-that-is-at-least-32-chars"
    client.app.dependency_overrides[get_settings] = lambda: test_settings.model_copy(
        update={
            "sync_admin_key": SecretStr(secret),
            "sync_public_https_base_url": "https://jlpt.example.test",
        }
    )
    path = "/api/v1/sync/admin/qr-sessions"
    assert client.post(path).status_code == 401
    assert client.post(path, headers={"X-Sync-Admin-Key": "wrong"}).status_code == 401
    assert client.post(path, headers={"X-Sync-Admin-Key": secret}).status_code == 201


def test_qr_payload_is_short_lived_and_contains_no_device_credential(
    client, db_session, test_settings
) -> None:  # type: ignore[no-untyped-def]
    created = create_session(client, test_settings)
    payload = created["qr_payload"]
    assert set(payload) == {"version", "base_url", "session_id", "challenge", "expires_at"}
    assert payload["version"] == 1
    assert payload["base_url"] == "https://jlpt.example.test"
    assert datetime.fromisoformat(payload["expires_at"].replace("Z", "+00:00")) - datetime.now(
        UTC
    ) <= timedelta(minutes=5)
    session = db_session.get(SyncQRSession, uuid.UUID(created["id"]))
    assert session is not None
    assert session.challenge_hash == hash_token(payload["challenge"])
    assert payload["challenge"] not in session.challenge_hash
    assert session.credential_hash is None


def test_qr_claim_rate_limit_is_shared_and_does_not_burn_session(
    client, db_session, test_settings
) -> None:  # type: ignore[no-untyped-def]
    created = create_session(client, test_settings)
    qr = created["qr_payload"]
    results = []
    for _ in range(5):
        result = client.post(
            f"/api/v1/sync/qr-sessions/{qr['session_id']}/claim",
            json={
                "challenge": "wrong-challenge-value-000000000000",
                "device_name": "Mock Android",
                "device_credential": secrets.token_urlsafe(48),
            },
        )
        results.append(result.status_code)
        row = db_session.get(SyncQRSession, uuid.UUID(created["id"]))
        assert row is not None and row.status == "WAITING_FOR_DEVICE"
        assert row.failure_count == 0
    assert results == [401, 401, 401, 401, 429]
    assert result.headers["Retry-After"] == "900"

    blocked = client.post(
        f"/api/v1/sync/qr-sessions/{qr['session_id']}/claim",
        json={
            "challenge": qr["challenge"],
            "device_name": "Mock Android",
            "device_credential": secrets.token_urlsafe(48),
        },
    )
    assert blocked.status_code == 429
    assert 1 <= int(blocked.headers["Retry-After"]) <= 900
    attempt = db_session.get(SyncPairingAttempt, hash_token("127.0.0.1"))
    assert attempt is not None and attempt.failed_attempts == 5


def test_creating_new_qr_cancels_previous_pending_session(client, test_settings) -> None:  # type: ignore[no-untyped-def]
    old = create_session(client, test_settings)
    current = create_session(client, test_settings)
    old_status = client.get(f"/api/v1/sync/admin/qr-sessions/{old['id']}")
    assert old_status.json()["data"]["status"] == "CANCELLED"
    assert current["status"] == "WAITING_FOR_DEVICE"
    old_qr = old["qr_payload"]
    replay = client.post(
        f"/api/v1/sync/qr-sessions/{old_qr['session_id']}/claim",
        json={
            "challenge": old_qr["challenge"],
            "device_name": "Old QR client",
            "device_credential": secrets.token_urlsafe(48),
        },
    )
    assert replay.status_code == 409


def test_qr_confirmation_has_five_attempt_lockout(client, test_settings) -> None:  # type: ignore[no-untyped-def]
    created = create_session(client, test_settings)
    qr = created["qr_payload"]
    session_path = f"/api/v1/sync/qr-sessions/{qr['session_id']}"
    claim = client.post(
        session_path + "/claim",
        json={
            "challenge": qr["challenge"],
            "device_name": "Mock Android",
            "device_credential": secrets.token_urlsafe(48),
        },
    ).json()["data"]
    assert (
        client.post(
            session_path + "/ready", headers={"X-Claim-Ticket": claim["claim_ticket"]}
        ).json()["data"]["status"]
        == "AWAITING_CONFIRMATION"
    )
    wrong_code = "000000" if claim["confirmation_code"] != "000000" else "999999"
    path = f"/api/v1/sync/admin/qr-sessions/{qr['session_id']}/confirm"
    for _ in range(5):
        assert client.post(path, json={"confirmation_code": wrong_code}).status_code == 401
    assert (
        client.post(path, json={"confirmation_code": claim["confirmation_code"]}).status_code == 409
    )
