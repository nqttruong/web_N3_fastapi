import uuid

from fastapi.testclient import TestClient


def test_create_and_list_questions(client: TestClient, make_exam, make_question) -> None:  # type: ignore[no-untyped-def]
    exam = make_exam()
    make_question(exam["id"], 2)
    make_question(exam["id"], 1)

    listed = client.get(f"/api/v1/exams/{exam['id']}/questions").json()
    assert [q["question_number"] for q in listed["data"]] == [1, 2]
    assert listed["data"][0]["options"] == ["ので", "のに", "ながら", "ばかりか"]
    assert listed["data"][0]["correct_answer"] == 1

    hidden = client.get(
        f"/api/v1/exams/{exam['id']}/questions", params={"include_answers": "false"}
    ).json()
    assert all(q["correct_answer"] is None for q in hidden["data"])

    detail = client.get(f"/api/v1/exams/{exam['id']}").json()["data"]
    assert detail["question_count"] == 2
    assert detail["verified_answer_count"] == 2


def test_answer_status_defaults(client: TestClient, make_exam) -> None:  # type: ignore[no-untyped-def]
    exam = make_exam()
    base = {"question_type": "kanji_reading", "options": ["あ", "い"]}
    with_answer = client.post(
        f"/api/v1/exams/{exam['id']}/questions",
        json=base | {"question_number": 1, "question_text": "問1", "correct_answer": 2},
    ).json()["data"]
    assert with_answer["answer_status"] == "unverified"  # never trusted implicitly
    without = client.post(
        f"/api/v1/exams/{exam['id']}/questions",
        json=base | {"question_number": 2, "question_text": "問2"},
    ).json()["data"]
    assert without["answer_status"] == "missing"
    assert without["correct_answer"] is None


def test_question_validation(client: TestClient, make_exam) -> None:  # type: ignore[no-untyped-def]
    exam = make_exam()
    url = f"/api/v1/exams/{exam['id']}/questions"
    valid = {
        "question_number": 1,
        "question_type": "grammar_form",
        "question_text": "文",
        "options": ["a", "b", "c", "d"],
    }
    cases = [
        valid | {"options": ["only one"]},
        valid | {"options": ["a", "a"]},
        valid | {"options": ["a", " "]},
        valid | {"correct_answer": 5},
        valid | {"correct_answer": 0},
        valid | {"answer_status": "verified"},  # verified without an answer
        valid | {"correct_answer": 1, "answer_status": "missing"},
        valid | {"question_number": 0},
        valid | {"question_text": "   "},
        valid | {"question_type": "listening"},
        valid | {"passage_id": str(uuid.uuid4())},  # passage from nowhere
    ]
    for payload in cases:
        response = client.post(url, json=payload)
        assert response.status_code == 422, (payload, response.text)
    assert client.post(f"/api/v1/exams/{uuid.uuid4()}/questions", json=valid).status_code == 404


def test_duplicate_questions_rejected(client: TestClient, make_exam, make_question) -> None:  # type: ignore[no-untyped-def]
    exam = make_exam()
    first = make_question(exam["id"], 1)
    url = f"/api/v1/exams/{exam['id']}/questions"

    same_number = client.post(
        url,
        json={
            "question_number": 1,
            "question_type": "grammar_form",
            "question_text": "別の問題",
            "options": ["a", "b"],
        },
    )
    assert same_number.status_code == 409

    # Same content, different number; full-width/half-width variants count as duplicates.
    same_content = client.post(
        url,
        json={
            "question_number": 2,
            "question_type": "grammar_form",
            "question_text": str(first["question_text"]).replace("#1", "＃１") + "  ",
            "options": first["options"],
        },
    )
    assert same_content.status_code == 409

    # The same question in a *different* exam is fine.
    other = make_exam(title="other")
    make_question(other["id"], 1)


def test_passages_and_same_exam_rule(client: TestClient, make_exam, make_question) -> None:  # type: ignore[no-untyped-def]
    exam = make_exam(category="reading")
    passage = client.post(
        f"/api/v1/exams/{exam['id']}/passages", json={"content": "これは読解用の短い文章です。"}
    )
    assert passage.status_code == 201
    passage_id = passage.json()["data"]["id"]
    q = make_question(exam["id"], 1, passage_id=passage_id, question_type="reading_short")
    assert q["passage_id"] == passage_id
    assert len(client.get(f"/api/v1/exams/{exam['id']}/passages").json()["data"]) == 1

    other = make_exam(title="other")
    response = client.post(
        f"/api/v1/exams/{other['id']}/questions",
        json={
            "question_number": 1,
            "question_type": "reading_short",
            "question_text": "問",
            "options": ["a", "b"],
            "passage_id": passage_id,
        },
    )
    assert response.status_code == 422


def test_patch_question_answer_trust(client: TestClient, make_exam, make_question) -> None:  # type: ignore[no-untyped-def]
    exam = make_exam()
    q = make_question(exam["id"], 1)
    url = f"/api/v1/questions/{q['id']}"

    changed = client.patch(url, json={"correct_answer": 2}).json()["data"]
    assert changed["correct_answer"] == 2
    assert changed["answer_status"] == "unverified"  # changing the key drops verification

    confirmed = client.patch(url, json={"answer_status": "verified"}).json()["data"]
    assert confirmed["answer_status"] == "verified"

    # Shrinking options below the key is rejected
    assert client.patch(url, json={"options": ["x", "y"], "correct_answer": 3}).status_code == 422
    assert client.patch(url, json={"options": ["a"]}).status_code == 422
    cleared = client.patch(url, json={"correct_answer": None}).json()["data"]
    assert cleared["answer_status"] == "missing"
    assert (
        client.patch(f"/api/v1/questions/{uuid.uuid4()}", json={"question_text": "x"}).status_code
        == 404
    )


def test_delete_question(client: TestClient, make_exam, make_question) -> None:  # type: ignore[no-untyped-def]
    exam = make_exam()
    q1 = make_question(exam["id"], 1)
    q2 = make_question(exam["id"], 2)
    assert client.delete(f"/api/v1/questions/{q1['id']}").status_code == 204
    assert client.delete(f"/api/v1/questions/{q1['id']}").status_code == 404

    client.post(
        "/api/v1/attempts",
        json={"exam_id": exam["id"], "started_at": "2026-01-01T00:00:00Z", "answers": []},
    )
    blocked = client.delete(f"/api/v1/questions/{q2['id']}")
    assert blocked.status_code == 409
