import uuid
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient

STARTED = "2026-01-01T09:00:00+09:00"


def _setup(client: TestClient, make_exam, make_question):  # type: ignore[no-untyped-def]
    exam = make_exam(title="採点テスト")
    q1 = make_question(exam["id"], 1, correct_answer=1)  # verified, key 1
    q2 = make_question(exam["id"], 2, correct_answer=3)  # verified, key 3
    q3 = make_question(exam["id"], 3, correct_answer=2)  # verified, key 2
    q4 = make_question(exam["id"], 4, correct_answer=4, answer_status="unverified")
    q5 = make_question(exam["id"], 5, correct_answer=None, answer_status=None)  # no key
    return exam, [q1, q2, q3, q4, q5]


def test_grading_counts(client: TestClient, make_exam, make_question) -> None:  # type: ignore[no-untyped-def]
    exam, (q1, q2, q3, q4, q5) = _setup(client, make_exam, make_question)
    response = client.post(
        "/api/v1/attempts",
        json={
            "exam_id": exam["id"],
            "started_at": STARTED,
            "completed_at": "2026-01-01T09:30:00+09:00",
            "answers": [
                {"question_id": q1["id"], "selected_answer": 1},  # correct
                {"question_id": q2["id"], "selected_answer": 2},  # incorrect
                {"question_id": q3["id"], "selected_answer": None},  # unanswered
                {"question_id": q4["id"], "selected_answer": 4},  # ungraded (unverified key)
                {"question_id": q5["id"], "selected_answer": 1},  # ungraded (no key)
            ],
        },
    )
    assert response.status_code == 201, response.text
    data = response.json()["data"]
    assert data["total_questions"] == 5
    assert (
        data["correct_count"],
        data["incorrect_count"],
        data["unanswered_count"],
        data["ungraded_count"],
    ) == (1, 1, 1, 2)
    assert data["accuracy"] == 0.5
    by_number = {a["question_number"]: a for a in data["answers"]}
    assert by_number[1]["is_correct"] is True
    assert by_number[2]["is_correct"] is False
    assert by_number[2]["correct_answer"] == 3
    assert by_number[3]["is_correct"] is None
    assert by_number[4]["correct_answer"] is None  # unverified key is not exposed as official
    assert by_number[4]["is_correct"] is None
    # Timestamps normalised to UTC
    assert data["started_at"].startswith("2026-01-01T00:00:00")


def test_omitted_questions_count_as_unanswered(
    client: TestClient, make_exam, make_question
) -> None:  # type: ignore[no-untyped-def]
    exam, (q1, *_rest) = _setup(client, make_exam, make_question)
    data = client.post(
        "/api/v1/attempts",
        json={
            "exam_id": exam["id"],
            "started_at": STARTED,
            "answers": [{"question_id": q1["id"], "selected_answer": 2}],
        },
    ).json()["data"]
    assert data["incorrect_count"] == 1
    assert data["unanswered_count"] == 4
    assert len(data["answers"]) == 5
    assert data["completed_at"] is not None


def test_history_is_stable_after_key_change(client: TestClient, make_exam, make_question) -> None:  # type: ignore[no-untyped-def]
    exam, (q1, *_rest) = _setup(client, make_exam, make_question)
    attempt = client.post(
        "/api/v1/attempts",
        json={
            "exam_id": exam["id"],
            "started_at": STARTED,
            "answers": [{"question_id": q1["id"], "selected_answer": 1}],
        },
    ).json()["data"]
    client.patch(
        f"/api/v1/questions/{q1['id']}", json={"correct_answer": 2, "answer_status": "verified"}
    )
    again = client.get(f"/api/v1/attempts/{attempt['id']}").json()["data"]
    assert again["correct_count"] == 1
    assert again["answers"][0]["is_correct"] is True
    assert again["answers"][0]["correct_answer"] == 1


def test_attempt_validation(client: TestClient, make_exam, make_question) -> None:  # type: ignore[no-untyped-def]
    exam, (q1, *_rest) = _setup(client, make_exam, make_question)
    other = make_exam(title="別の試験")
    foreign = make_question(other["id"], 1)
    future = (datetime.now(UTC) + timedelta(days=1)).isoformat()
    cases = [
        {"exam_id": exam["id"], "started_at": "2026-01-01T09:00:00"},  # naive datetime
        {"exam_id": exam["id"], "started_at": future},
        {
            "exam_id": exam["id"],
            "started_at": STARTED,
            "completed_at": "2025-12-31T00:00:00Z",
        },
        {
            "exam_id": exam["id"],
            "started_at": STARTED,
            "answers": [{"question_id": foreign["id"], "selected_answer": 1}],
        },
        {
            "exam_id": exam["id"],
            "started_at": STARTED,
            "answers": [{"question_id": q1["id"], "selected_answer": 7}],
        },
        {
            "exam_id": exam["id"],
            "started_at": STARTED,
            "answers": [
                {"question_id": q1["id"], "selected_answer": 1},
                {"question_id": q1["id"], "selected_answer": 2},
            ],
        },
        {"exam_id": str(uuid.uuid4()), "started_at": STARTED},
    ]
    for payload in cases:
        response = client.post("/api/v1/attempts", json=payload)
        assert response.status_code == 422, (payload, response.text)
        assert response.json()["error"]["code"] == "validation_error"


def test_option_out_of_range_for_two_option_question(
    client: TestClient, make_exam, make_question
) -> None:  # type: ignore[no-untyped-def]
    exam = make_exam()
    q = make_question(exam["id"], 1, options=["はい", "いいえ"], correct_answer=1)
    response = client.post(
        "/api/v1/attempts",
        json={
            "exam_id": exam["id"],
            "started_at": STARTED,
            "answers": [{"question_id": q["id"], "selected_answer": 3}],
        },
    )
    assert response.status_code == 422
    assert response.json()["error"]["details"][0]["loc"] == ["answers", 0, "selected_answer"]


def test_empty_or_archived_exam_rejected(client: TestClient, make_exam, make_question) -> None:  # type: ignore[no-untyped-def]
    empty = make_exam(title="empty")
    assert (
        client.post("/api/v1/attempts", json={"exam_id": empty["id"], "started_at": STARTED})
    ).status_code == 422
    archived = make_exam(title="archived")
    make_question(archived["id"], 1)
    client.patch(f"/api/v1/exams/{archived['id']}", json={"status": "archived"})
    assert (
        client.post("/api/v1/attempts", json={"exam_id": archived["id"], "started_at": STARTED})
    ).status_code == 422


def test_list_and_get_attempts(client: TestClient, make_exam, make_question) -> None:  # type: ignore[no-untyped-def]
    exam, _ = _setup(client, make_exam, make_question)
    for day in (1, 2, 3):
        client.post(
            "/api/v1/attempts",
            json={"exam_id": exam["id"], "started_at": f"2026-01-0{day}T00:00:00Z"},
        )
    listed = client.get("/api/v1/attempts", params={"page_size": 2}).json()
    assert listed["meta"]["total"] == 3
    assert listed["meta"]["total_pages"] == 2
    assert listed["data"][0]["started_at"].startswith("2026-01-03")
    assert listed["data"][0]["exam_title"] == "採点テスト"
    assert listed["data"][0]["approved_explanation_count"] == 0
    assert listed["data"][0]["pending_explanation_count"] == 0
    assert (
        client.get("/api/v1/attempts", params={"exam_id": str(uuid.uuid4())}).json()["meta"][
            "total"
        ]
        == 0
    )

    detail = client.get(f"/api/v1/attempts/{listed['data'][0]['id']}")
    assert detail.status_code == 200
    assert detail.json()["data"]["exam_source_url"] is None
    assert client.get(f"/api/v1/attempts/{uuid.uuid4()}").status_code == 404


def test_dashboard_summary_reflects_data(client: TestClient, make_exam, make_question) -> None:  # type: ignore[no-untyped-def]
    empty = client.get("/api/v1/analytics/summary").json()["data"]
    assert empty["total_exams"] == 0
    assert empty["accuracy"] is None

    exam, (q1, q2, *_rest) = _setup(client, make_exam, make_question)
    client.post(
        "/api/v1/attempts",
        json={
            "exam_id": exam["id"],
            "started_at": STARTED,
            "answers": [
                {"question_id": q1["id"], "selected_answer": 1},
                {"question_id": q2["id"], "selected_answer": 1},
            ],
        },
    )
    summary = client.get("/api/v1/analytics/summary").json()["data"]
    assert summary["total_exams"] == 1
    assert summary["total_questions"] == 5
    assert summary["total_attempts"] == 1
    assert summary["total_correct"] == 1
    assert summary["total_incorrect"] == 1
    assert summary["accuracy"] == 0.5
    assert summary["recent_exams"][0]["id"] == exam["id"]
    assert len(summary["recent_attempts"]) == 1


def test_mistakes_aggregate_wrong_occurrences_and_exclude_blank_ungraded(
    client: TestClient, make_exam, make_question
) -> None:  # type: ignore[no-untyped-def]
    exam, (q1, q2, q3, *_rest) = _setup(client, make_exam, make_question)
    for day in (1, 2):
        client.post(
            "/api/v1/attempts",
            json={
                "exam_id": exam["id"],
                "started_at": f"2026-01-0{day}T00:00:00Z",
                "answers": [
                    {"question_id": q1["id"], "selected_answer": 2},
                    {"question_id": q2["id"], "selected_answer": 2},
                    {"question_id": q3["id"], "selected_answer": None},
                ],
            },
        )

    response = client.get("/api/v1/attempts/mistakes", params={"page_size": 10})
    assert response.status_code == 200, response.text
    assert response.json()["meta"]["total"] == 2
    first = next(item for item in response.json()["data"] if item["question_id"] == q1["id"])
    assert first["occurrences"] == 2
    assert first["latest_selected_answer"] == 2
    assert first["correct_answer_at_submission"] == 1
    assert first["status"] == "derived"
    assert (
        client.get("/api/v1/attempts/mistakes", params={"q": "採点テスト"}).json()["meta"]["total"]
        == 2
    )
    assert (
        client.get("/api/v1/attempts/mistakes", params={"exam_id": str(uuid.uuid4())}).json()[
            "meta"
        ]["total"]
        == 0
    )


def test_jlpt_analytics_uses_exact_grade_buckets_and_no_official_score(
    client: TestClient, make_exam, make_question
) -> None:  # type: ignore[no-untyped-def]
    exam, (q1, q2, q3, q4, q5) = _setup(client, make_exam, make_question)
    client.post(
        "/api/v1/attempts",
        json={
            "exam_id": exam["id"],
            "started_at": STARTED,
            "completed_at": "2026-01-01T09:30:00+09:00",
            "answers": [
                {"question_id": q1["id"], "selected_answer": 1},
                {"question_id": q2["id"], "selected_answer": 2},
                {"question_id": q3["id"], "selected_answer": None},
                {"question_id": q4["id"], "selected_answer": 4},
                {"question_id": q5["id"], "selected_answer": 1},
            ],
        },
    )
    report = client.get("/api/v1/analytics/jlpt").json()["data"]
    assert (report["attempt_count"], report["correct"], report["incorrect"]) == (1, 1, 1)
    assert (report["unanswered"], report["ungraded"], report["accuracy"]) == (1, 2, 0.5)
    assert report["correct_over_all"] == 0.2
    assert report["average_duration_seconds"] == 1800
    assert report["skill_results"]["grammar"]["total"] == 5
    assert report["android_attempt_count"] is None
    assert "không phải điểm JLPT chính thức" in report["score_note"]
