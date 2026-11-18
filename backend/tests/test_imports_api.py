"""Import draft lifecycle through the HTTP API (text/HTML modes)."""

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.exams.models import Question
from app.imports.models import ImportDraft
from tests.conftest import fixture_text

DETHI_URL = "https://dethitiengnhat.com/jlpt/N3/99/3"


def _create_html(client: TestClient, **extra: Any) -> dict[str, Any]:
    body = {"html": fixture_text("dethitiengnhat_like_scored.html")} | extra
    r = client.post("/api/v1/imports/html", json=body)
    assert r.status_code == 201, r.text
    return r.json()["data"]  # type: ignore[no-any-return]


def _save(client: TestClient, draft: dict[str, Any], content: dict[str, Any]) -> dict[str, Any]:
    r = client.patch(
        f"/api/v1/imports/{draft['id']}", json={"version": draft["version"], "content": content}
    )
    assert r.status_code == 200, r.text
    return r.json()["data"]  # type: ignore[no-any-return]


def _review_all(content: dict[str, Any]) -> dict[str, Any]:
    for q in content["questions"]:
        q["reviewed"] = True
    return content


def _times() -> dict[str, str]:
    end = datetime.now(UTC) - timedelta(minutes=1)
    return {
        "started_at": (end - timedelta(minutes=20)).isoformat(),
        "completed_at": end.isoformat(),
    }


def _browser_capture(**overrides: Any) -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "capture_id": "f0d8f90e-67cb-48cc-8a55-77e5ea8d4bad",
        "source": "dethitiengnhat",
        "source_url": DETHI_URL,
        "level": "N3",
        "exam_title": "N3 文法・読解",
        "category": "grammar",
        "capture_state": "graded",
        "captured_at": datetime.now(UTC).isoformat(),
        "questions": [
            {
                "number": 1,
                "section_heading": "文法",
                "question_text": "雨が降っている（　　）、試合は中止になった。",
                "options": ["ので", "のに", "ながら", "ばかりか"],
                "selected_answer_index": 0,
                "source_correct_answer_index": 1,
                "answer_source": "page_result",
                "passage": "昨日、雨が降りました。",
            }
        ],
    } | overrides


def _enable_extension_token(client: TestClient, test_settings: Any) -> str:
    token = "pr5-test-extension-token-" + "x" * 40
    client.app.dependency_overrides[get_settings] = lambda: test_settings.model_copy(
        update={"extension_import_token": SecretStr(token)}
    )
    return token


def _capture(client: TestClient, payload: dict[str, Any], token: str, **headers: str):
    return client.post(
        "/api/v1/imports/browser-capture",
        json=payload,
        headers={"Authorization": f"Bearer {token}", **headers},
    )


def test_browser_capture_creates_unverified_draft_and_reuses_retry(
    client: TestClient, db_session: Session, test_settings: Any
) -> None:
    token = _enable_extension_token(client, test_settings)
    payload = _browser_capture()

    response = _capture(client, payload, token, Origin="https://untrusted.example")
    assert response.status_code == 201, response.text
    draft = response.json()["data"]
    assert draft["method"] == "browser_capture"
    assert draft["adapter"] == "dethitiengnhat_capture"
    assert draft["exam_id"] is None
    question = draft["content"]["questions"][0]
    assert question["options"] == ["ので", "のに", "ながら", "ばかりか"]
    assert question["correct_answer"] == 2  # 0-based source index converted to PR2's 1-based value
    assert question["site_answer"] == 2
    assert question["user_answer"] == 1
    assert question["answer_confirmed"] is False
    assert draft["content"]["passages"][0]["content"] == "昨日、雨が降りました。"
    assert db_session.scalar(select(func.count(Question.id))) == 0
    assert db_session.scalar(select(func.count(ImportDraft.id))) == 1

    again = _capture(client, payload, token)
    assert again.status_code == 200, again.text
    assert again.json()["data"]["id"] == draft["id"]
    assert db_session.scalar(select(func.count(ImportDraft.id))) == 1


def test_browser_capture_auth_schema_and_missing_answers(
    client: TestClient, test_settings: Any
) -> None:
    payload = _browser_capture()
    assert client.post("/api/v1/imports/browser-capture", json=payload).status_code == 503
    token = _enable_extension_token(client, test_settings)
    assert _capture(client, payload, "wrong-token").status_code == 401

    untrusted = _browser_capture(source_url="https://example.com/jlpt/N3/32/3")
    assert _capture(client, untrusted, token).status_code == 422
    invalid_index = _browser_capture()
    invalid_index["questions"][0]["selected_answer_index"] = 4
    assert _capture(client, invalid_index, token).status_code == 422

    client.app.dependency_overrides[get_settings] = lambda: test_settings.model_copy(
        update={"extension_import_token": SecretStr(token), "import_max_html_bytes": 64}
    )
    oversized = _capture(client, payload, token)
    assert oversized.status_code == 413
    client.app.dependency_overrides[get_settings] = lambda: test_settings.model_copy(
        update={"extension_import_token": SecretStr(token)}
    )

    missing = _browser_capture()
    missing["questions"][0]["selected_answer_index"] = None
    missing["questions"][0]["source_correct_answer_index"] = None
    missing["questions"][0]["answer_source"] = None
    response = _capture(client, missing, token)
    assert response.status_code == 201, response.text
    question = response.json()["data"]["content"]["questions"][0]
    assert question["correct_answer"] is None
    assert question["user_answer"] is None
    assert question["answer_confirmed"] is False
    assert "missing_source_answer" in {note["code"] for note in question["parser_notes"]}


# ------------------------------------------------------------------ create / read
def test_text_import_creates_preview_without_touching_exams(
    client: TestClient, db_session: Session
) -> None:
    r = client.post(
        "/api/v1/imports/text",
        json={"text": fixture_text("text_basic.txt"), "source_url": "https://example.com/t1"},
    )
    assert r.status_code == 201, r.text
    draft = r.json()["data"]
    assert draft["method"] == "text"
    assert draft["adapter"] == "generic_text"
    assert draft["raw_input"] == fixture_text("text_basic.txt")  # original kept verbatim
    assert draft["status"] in {"ready", "needs_review"}
    s = draft["summary"]
    assert s["total_questions"] == 3
    assert s["missing_answer"] == 1  # Q2 has only the user's answer, no key
    assert s["confirmed_answers"] == 0
    assert s["with_user_answer"] == 1
    q1 = draft["content"]["questions"][0]
    assert q1["answer_source"] == "site_key"
    assert q1["answer_confirmed"] is False
    # Nothing is written to exams/questions before commit
    assert db_session.scalar(select(func.count(Question.id))) == 0
    assert client.get("/api/v1/exams").json()["meta"]["total"] == 0

    listed = client.get("/api/v1/imports").json()
    assert listed["meta"]["total"] == 1
    assert listed["data"][0]["title"] == "N3 模擬テスト（自作）第１回"
    assert isinstance(listed["data"][0]["issues"], list)
    assert client.get(f"/api/v1/imports/{draft['id']}").status_code == 200


def test_html_import_reads_canonical_url_and_flags(client: TestClient) -> None:
    draft = _create_html(client)
    assert draft["adapter"] == "dethitiengnhat_html"
    assert draft["source_url"] == DETHI_URL
    assert draft["summary"]["total_questions"] == 6
    assert draft["summary"]["included_questions"] == 5  # example excluded
    assert "<script" in draft["raw_input"]  # raw kept for audit, never rendered
    assert "alert" not in str(draft["content"])


def test_create_validation_and_limits(client: TestClient, test_settings) -> None:  # type: ignore[no-untyped-def]
    assert client.post("/api/v1/imports/text", json={"text": ""}).status_code == 422
    assert (
        client.post("/api/v1/imports/text", json={"text": "x", "source_url": "ftp://a"}).status_code
        == 422
    )
    assert client.post("/api/v1/imports/text", json={"text": "x", "fetch": True}).status_code == 422
    big = "あ" * (test_settings.import_max_text_chars + 1)
    r = client.post("/api/v1/imports/text", json={"text": big})
    assert r.status_code == 413
    assert r.json()["error"]["code"] == "payload_too_large"
    assert client.get(f"/api/v1/imports/{uuid.uuid4()}").status_code == 404


def test_no_server_side_url_fetching(client: TestClient, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    import socket
    import urllib.request

    def _boom(*_a: object, **_k: object) -> None:
        raise AssertionError("network access attempted")

    monkeypatch.setattr(socket, "create_connection", _boom)
    monkeypatch.setattr(urllib.request, "urlopen", _boom)
    r = client.post(
        "/api/v1/imports/html",
        json={
            "html": "<p>1. 文</p><p>1) あ</p><p>2) い</p>",
            "source_url": "https://example.com/x",
        },
    )
    assert r.status_code == 201
    paths = client.get("/api/v1/openapi.json").json()["paths"]
    assert not any("url" in p.split("/")[-1] for p in paths if p.startswith("/api/v1/imports"))


# ------------------------------------------------------------------ edit / confirm
def test_patch_confirm_and_reconfirm_after_change(client: TestClient) -> None:
    draft = _create_html(client)
    content = draft["content"]
    q2 = content["questions"][1]
    q2["answer_confirmed"] = True
    draft = _save(client, draft, content)
    q2 = draft["content"]["questions"][1]
    assert q2["answer_confirmed"] is True
    assert q2["answer_source"] == "site_key"

    # Changing a confirmed answer silently drops the confirmation (must re-confirm)
    content = draft["content"]
    content["questions"][1]["correct_answer"] = 3
    draft = _save(client, draft, content)
    q2 = draft["content"]["questions"][1]
    assert q2["answer_confirmed"] is False
    assert q2["answer_source"] == "user_entered"

    # Stale version → 409
    r = client.patch(
        f"/api/v1/imports/{draft['id']}", json={"version": 1, "content": draft["content"]}
    )
    assert r.status_code == 409


def test_patch_rejects_invalid_content(client: TestClient) -> None:
    draft = _create_html(client)
    content = draft["content"]
    content["questions"][1]["answer_confirmed"] = True
    content["questions"][1]["correct_answer"] = None
    r = client.patch(
        f"/api/v1/imports/{draft['id']}", json={"version": draft["version"], "content": content}
    )
    assert r.status_code == 422
    content["questions"][1]["correct_answer"] = 9
    r = client.patch(
        f"/api/v1/imports/{draft['id']}", json={"version": draft["version"], "content": content}
    )
    assert r.status_code == 422


def test_validation_issues_block_until_fixed(client: TestClient) -> None:
    draft = client.post(
        "/api/v1/imports/text", json={"text": "1. 文がある\n1) あ\n2) い\n3) う"}
    ).json()["data"]
    assert draft["status"] == "needs_review"
    codes = {i["code"] for i in draft["issues"]}
    assert {"missing_title", "missing_category", "needs_review"} <= codes

    content = draft["content"]
    content["exam"]["title"] = "自作テスト"
    content["exam"]["category"] = "grammar"
    content["questions"][0]["options"].append("え")
    content["questions"][0]["reviewed"] = True
    draft = _save(client, draft, content)
    assert draft["status"] == "ready", draft["issues"]
    # Commit refuses while errors exist; works once fixed
    r = client.post(f"/api/v1/imports/{draft['id']}/validate")
    assert r.json()["data"]["status"] == "ready"


def test_duplicate_options_and_answer_range_errors(client: TestClient) -> None:
    draft = client.post(
        "/api/v1/imports/text",
        json={
            "text": "1. 文\n1) あ\n2) あ\n3) う\n4) え\n正解: 4",
            "title": "t",
            "category": "grammar",
        },
    ).json()["data"]
    content = draft["content"]
    content["questions"][0]["options"] = ["あ", "あ", "う"]
    r = client.patch(
        f"/api/v1/imports/{draft['id']}", json={"version": draft["version"], "content": content}
    )
    codes = {i["code"] for i in r.json()["data"]["issues"]}
    assert {"duplicate_options", "answer_out_of_range"} <= codes


# ------------------------------------------------------------------ commit
def test_commit_creates_exam_with_trust_levels_and_is_idempotent(
    client: TestClient, db_session: Session
) -> None:
    draft = _create_html(client)
    content = _review_all(draft["content"])
    content["questions"][1]["answer_confirmed"] = True  # Q2 confirmed
    # Q3 left unconfirmed; Q4 answer cleared → missing
    content["questions"][3]["correct_answer"] = None
    draft = _save(client, draft, content)
    assert draft["status"] == "ready", draft["issues"]

    r = client.post(f"/api/v1/imports/{draft['id']}/commit", json={"target": "new"})
    assert r.status_code == 201, r.text
    result = r.json()["data"]
    assert result["already_committed"] is False
    assert result["created_questions"] == 5
    assert result["attempt_id"] is None
    exam_id = result["exam_id"]

    # Same request again (double click) → same exam, nothing duplicated
    again = client.post(f"/api/v1/imports/{draft['id']}/commit", json={"target": "new"})
    assert again.status_code == 200
    assert again.json()["data"]["already_committed"] is True
    assert again.json()["data"]["exam_id"] == exam_id
    assert db_session.scalar(select(func.count(Question.id))) == 5

    # Visible through the PR1 API
    exam = client.get(f"/api/v1/exams/{exam_id}").json()["data"]
    assert exam["source_url"] == DETHI_URL
    assert exam["verified_answer_count"] == 1
    qs = {
        q["question_number"]: q
        for q in client.get(f"/api/v1/exams/{exam_id}/questions").json()["data"]
    }
    assert set(qs) == {2, 3, 4, 5, 6}
    assert (qs[2]["answer_status"], qs[2]["answer_source"]) == ("verified", "site_key")
    assert (qs[3]["answer_status"], qs[3]["answer_source"]) == ("unverified", "site_key")
    assert (qs[4]["answer_status"], qs[4]["correct_answer"]) == ("missing", None)
    assert qs[2]["question_text"] == "雨が降っている（　　）、試合は<u>中止</u>になった。"
    assert qs[5]["passage_id"] == qs[6]["passage_id"] is not None
    passages = client.get(f"/api/v1/exams/{exam_id}/passages").json()["data"]
    assert len(passages) == 1  # shared, not duplicated per question

    # Committed draft is read-only
    stored = client.get(f"/api/v1/imports/{draft['id']}").json()["data"]
    assert stored["status"] == "committed"
    assert (
        client.patch(
            f"/api/v1/imports/{draft['id']}",
            json={"version": stored["version"], "source_url": None},
        ).status_code
        == 409
    )


def test_commit_refused_with_errors(client: TestClient) -> None:
    draft = _create_html(client)  # parser notes? none here, but example needs nothing
    content = draft["content"]
    content["exam"]["title"] = ""
    draft = _save(client, draft, content)
    r = client.post(f"/api/v1/imports/{draft['id']}/commit", json={"target": "new"})
    assert r.status_code == 422
    assert any(d["code"] == "missing_title" for d in r.json()["error"]["details"])


def test_commit_with_attempt_from_user_answers(client: TestClient) -> None:
    draft = _create_html(client)
    content = _review_all(draft["content"])
    for q in content["questions"]:
        if q["correct_answer"] is not None:
            q["answer_confirmed"] = True
    content["attempt"] = {"create": True, "started_at": None, "completed_at": None}
    draft = _save(client, draft, content)
    assert draft["status"] == "needs_review"
    assert any(i["code"] == "attempt_times_required" for i in draft["issues"])

    content = draft["content"]
    content["attempt"] = {"create": True, **_times()}
    draft = _save(client, draft, content)
    assert draft["status"] == "ready", draft["issues"]
    result = client.post(f"/api/v1/imports/{draft['id']}/commit", json={"target": "new"}).json()[
        "data"
    ]
    attempt = client.get(f"/api/v1/attempts/{result['attempt_id']}").json()["data"]
    # Fixture: Q2 wrong (picked 1, key 2), Q3 right, Q4 blank, Q5 wrong, Q6 right
    assert attempt["source"] == "import"
    assert attempt["total_questions"] == 5
    assert (attempt["correct_count"], attempt["incorrect_count"], attempt["unanswered_count"]) == (
        2,
        2,
        1,
    )
    assert (
        client.get(f"/api/v1/imports/{draft['id']}").json()["data"]["attempt_id"]
        == result["attempt_id"]
    )


def test_attempt_needs_user_answers(client: TestClient) -> None:
    raw = (
        fixture_text("dethitiengnhat_like_scored.html")
        .replace("不正解:　", "")
        .replace("正解:　", "")
    )
    draft = client.post("/api/v1/imports/html", json={"html": raw}).json()["data"]
    content = draft["content"]
    content["attempt"] = {"create": True, **_times()}
    draft = _save(client, draft, content)
    assert any(i["code"] == "attempt_no_answers" for i in draft["issues"])


def test_duplicate_import_detected_and_reuse_existing_exam(client: TestClient) -> None:
    first = _create_html(client)
    content = _review_all(first["content"])
    first = _save(client, first, content)
    exam_id = client.post(f"/api/v1/imports/{first['id']}/commit", json={"target": "new"}).json()[
        "data"
    ]["exam_id"]

    second = _create_html(client)
    codes = {i["code"] for i in second["issues"]}
    assert {"duplicate_source_url", "duplicate_draft"} <= codes
    # Same content under a different URL is still recognised as the same exam
    third = _create_html(client, source_url="https://example.com/copy")
    dup = [i for i in third["issues"] if i["code"] == "duplicate_exam"]
    assert dup and dup[0]["data"]["exam_id"] == exam_id
    assert client.delete(f"/api/v1/imports/{third['id']}").status_code == 204
    content = _review_all(second["content"])
    content["questions"][1]["answer_confirmed"] = True
    content["attempt"] = {"create": True, **_times()}
    second = _save(client, second, content)

    # Creating a second exam with the same URL is refused…
    r = client.post(f"/api/v1/imports/{second['id']}/commit", json={"target": "new"})
    assert r.status_code == 409
    assert r.json()["error"]["details"]["existing_exam_id"] == exam_id
    # …reusing it adds a new attempt and upgrades the newly confirmed answer, nothing duplicated
    r = client.post(
        f"/api/v1/imports/{second['id']}/commit",
        json={"target": "existing", "existing_exam_id": exam_id},
    )
    assert r.status_code == 201, r.text
    result = r.json()["data"]
    assert (
        result["created_questions"],
        result["reused_questions"],
        result["upgraded_answers"],
    ) == (0, 5, 1)
    assert result["exam_id"] == exam_id
    assert client.get(f"/api/v1/exams/{exam_id}").json()["data"]["question_count"] == 5
    assert client.get("/api/v1/attempts", params={"exam_id": exam_id}).json()["meta"]["total"] == 1
    assert client.get(f"/api/v1/exams/{exam_id}/passages").json()["data"].__len__() == 1


def test_reuse_existing_reports_conflicts(client: TestClient, make_exam, make_question) -> None:  # type: ignore[no-untyped-def]
    exam = make_exam(title="既存")
    make_question(exam["id"], 2)  # number 2 taken by a different question
    draft = _create_html(client, source_url="https://example.com/other")
    draft = _save(client, draft, _review_all(draft["content"]))
    r = client.post(
        f"/api/v1/imports/{draft['id']}/commit",
        json={"target": "existing", "existing_exam_id": exam["id"]},
    )
    assert r.status_code == 409
    assert r.json()["error"]["details"]["conflicts"][0]["question_number"] == 2
    assert (
        client.get(f"/api/v1/exams/{exam['id']}").json()["data"]["question_count"] == 1
    )  # rolled back


def test_reparse_with_corrected_text(client: TestClient) -> None:
    draft = client.post(
        "/api/v1/imports/text", json={"text": "ただの文章", "title": "直す"}
    ).json()["data"]
    assert draft["summary"]["total_questions"] == 0
    r = client.post(
        f"/api/v1/imports/{draft['id']}/parse",
        json={"raw_input": "1. 文\n1) あ\n2) い\n3) う\n4) え"},
    )
    data = r.json()["data"]
    assert data["summary"]["total_questions"] == 1
    assert data["content"]["exam"]["title"] == "直す"  # user meta preserved
    assert data["version"] == draft["version"] + 1


def test_delete_draft_keeps_committed_exam_and_attempt(client: TestClient) -> None:
    draft = _create_html(client)
    content = _review_all(draft["content"])
    content["attempt"] = {"create": True, **_times()}
    draft = _save(client, draft, content)
    result = client.post(f"/api/v1/imports/{draft['id']}/commit", json={"target": "new"}).json()[
        "data"
    ]
    assert client.delete(f"/api/v1/imports/{draft['id']}").status_code == 204
    assert client.get(f"/api/v1/imports/{draft['id']}").status_code == 404
    assert client.get(f"/api/v1/exams/{result['exam_id']}").status_code == 200
    assert (
        client.get(f"/api/v1/attempts/{result['attempt_id']}").json()["data"]["source"] == "import"
    )


def test_rate_limit(client: TestClient, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    from app.core import ratelimit

    monkeypatch.setattr(
        ratelimit, "get_settings", lambda: type("S", (), {"import_rate_limit_per_minute": 2})()
    )
    for _ in range(2):
        assert client.post("/api/v1/imports/text", json={"text": "1. 文"}).status_code == 201
    r = client.post("/api/v1/imports/text", json={"text": "1. 文"})
    assert r.status_code == 429
    assert r.json()["error"]["code"] == "rate_limited"


def test_pr1_flows_unaffected(client: TestClient, make_exam, make_question) -> None:  # type: ignore[no-untyped-def]
    exam = make_exam()
    q = make_question(exam["id"], 1)
    assert q["answer_source"] == "manual"
    cleared = client.patch(f"/api/v1/questions/{q['id']}", json={"correct_answer": None}).json()[
        "data"
    ]
    assert cleared["answer_source"] is None
    hidden = client.get(
        f"/api/v1/exams/{exam['id']}/questions", params={"include_answers": "false"}
    )
    assert hidden.json()["data"][0]["answer_source"] is None
    att = client.post(
        "/api/v1/attempts", json={"exam_id": exam["id"], "started_at": "2026-01-01T00:00:00Z"}
    ).json()["data"]
    assert att["source"] == "practice"
