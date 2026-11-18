"""PR4 — knowledge extraction, dedup, confirmation, reviews, sessions, analytics."""

import uuid
from datetime import timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.core.time import utcnow
from app.explanations.providers.registry import set_generator_for_tests
from app.knowledge.models import KnowledgeItem
from app.reviews.models import ReviewEvent, ReviewItem
from tests.explain_fakes import FakeGenerator

API = "/api/v1"
STARTED = "2026-01-05T00:00:00Z"


@pytest.fixture(autouse=True)
def _fake_ai(monkeypatch: pytest.MonkeyPatch) -> FakeGenerator:
    monkeypatch.setattr("app.explanations.retry.time.sleep", lambda s: None)
    gen = FakeGenerator()
    set_generator_for_tests(gen)
    return gen


def with_grammar(*patterns: tuple[str, str]):  # type: ignore[no-untyped-def]
    def mutate(p: dict[str, Any]) -> dict[str, Any]:
        p["grammar_points"] = [
            {
                "pattern": pat,
                "meaning_vi": mean,
                "usage": "…",
                "contrast": None,
                "example_ja": f"雨が降った{pat.strip('〜')}、中止になった。",
            }
            for pat, mean in patterns
        ]
        return p

    return mutate


def explain(
    client: TestClient, qid: str, *, approve: bool = True, steps: list[Any] | None = None
) -> dict[str, Any]:
    if steps is not None:
        set_generator_for_tests(FakeGenerator(steps))
    exp = client.post(
        f"{API}/explanations/generate", json={"question_id": qid, "force": True}
    ).json()["data"]["explanation"]
    if approve:
        client.post(f"{API}/explanations/{exp['id']}/approve", json={})
    return exp


def attempt(
    client: TestClient, exam_id: str, answers: dict[str, int | None], when: str = STARTED
) -> dict[str, Any]:
    return client.post(
        f"{API}/attempts",
        json={
            "exam_id": exam_id,
            "started_at": when,
            "answers": [{"question_id": q, "selected_answer": s} for q, s in answers.items()],
        },
    ).json()["data"]


def extract(client: TestClient, **body: Any) -> dict[str, Any]:
    r = client.post(f"{API}/knowledge/extract", json=body)
    assert r.status_code == 200, r.text
    return r.json()["data"]


def confirm_all(client: TestClient, extraction: dict[str, Any], **overrides: Any) -> dict[str, Any]:
    items, relations = [], []
    for q in extraction["questions"]:
        for c in q["candidates"]:
            action = overrides.get(
                c["ref"],
                "skip" if not c["selected"] else ("link" if c["action"] == "link" else "create"),
            )
            item = {
                k: c[k]
                for k in (
                    "ref",
                    "question_id",
                    "explanation_id",
                    "knowledge_type",
                    "title",
                    "summary",
                    "details",
                    "role",
                )
            }
            item["action"] = action
            if action == "link":
                item["target_knowledge_id"] = c["match"]["knowledge_id"]
            items.append(item)
        relations += [
            {
                "source_ref": r["source_ref"],
                "target_ref": r["target_ref"],
                "relation_type": r["relation_type"],
            }
            for r in q["relations"]
        ]
    r = client.post(f"{API}/knowledge/confirm", json={"items": items, "relations": relations})
    assert r.status_code == 200, r.text
    return r.json()["data"]


@pytest.fixture
def grammar_exam(make_exam, make_question):  # type: ignore[no-untyped-def]
    exam = make_exam(title="文法", category="grammar")
    q1 = make_question(exam["id"], 1)  # options ので のに ながら ばかりか, key 1 (ので)
    q2 = make_question(exam["id"], 2, question_text="風邪をひいた（　　）、学校を休んだ。")
    return exam, q1, q2


# ----------------------------------------------------------------- extraction rules
def test_only_approved_current_explanations_are_used(client, grammar_exam) -> None:  # type: ignore[no-untyped-def]
    _exam, q1, q2 = grammar_exam
    data = extract(client, question_ids=[q1["id"]])["questions"][0]
    assert data["skipped_code"] == "no_explanation" and data["candidates"] == []

    exp = explain(client, q1["id"], approve=False)
    assert (
        extract(client, question_ids=[q1["id"]])["questions"][0]["skipped_code"]
        == "explanation_not_approved"
    )
    client.post(f"{API}/explanations/{exp['id']}/reject", json={})
    assert (
        extract(client, question_ids=[q1["id"]])["questions"][0]["skipped_code"] == "no_explanation"
    )

    explain(client, q1["id"])
    ok = extract(client, question_ids=[q1["id"]])["questions"][0]
    assert ok["skipped_code"] is None
    grammar = [c for c in ok["candidates"] if c["knowledge_type"] == "grammar"]
    assert (
        grammar[0]["canonical_key"] == "grammar:ので"
        and grammar[0]["role"] == "tests"
        and grammar[0]["selected"]
    )
    vocab = [c for c in ok["candidates"] if c["knowledge_type"] == "vocabulary"]
    assert vocab[0]["role"] == "context" and not vocab[0]["selected"]  # 試合 only in the sentence

    # Changing the verified answer makes the approved explanation stale → not used
    client.patch(
        f"{API}/questions/{q1['id']}", json={"correct_answer": 2, "answer_status": "verified"}
    )
    assert (
        extract(client, question_ids=[q1["id"]])["questions"][0]["skipped_code"]
        == "explanation_stale"
    )
    unverified = client.patch(f"{API}/questions/{q2['id']}", json={"answer_status": "unverified"})
    assert unverified.status_code == 200
    assert (
        extract(client, question_ids=[q2["id"]])["questions"][0]["skipped_code"]
        == "answer_not_verified"
    )


def test_confirm_refuses_unapproved_explanation(client, grammar_exam) -> None:  # type: ignore[no-untyped-def]
    _exam, q1, _ = grammar_exam
    explain(client, q1["id"])
    data = extract(client, question_ids=[q1["id"]])
    exp_id = data["questions"][0]["explanation_id"]
    client.post(f"{API}/explanations/{exp_id}/reject", json={})
    c = data["questions"][0]["candidates"][0]
    item = {
        k: c[k]
        for k in (
            "ref",
            "question_id",
            "explanation_id",
            "knowledge_type",
            "title",
            "summary",
            "details",
            "role",
        )
    }
    r = client.post(f"{API}/knowledge/confirm", json={"items": [item | {"action": "create"}]})
    assert r.status_code == 409
    assert r.json()["error"]["details"]["code"] == "explanation_not_approved"


# ----------------------------------------------------------------- dedup & relations
def test_two_mistakes_share_one_grammar_item_and_reviews_are_idempotent(
    client, grammar_exam, db_session: Session
) -> None:  # type: ignore[no-untyped-def]
    exam, q1, q2 = grammar_exam
    steps = [with_grammar(("〜ので", "vì (nguyên nhân khách quan)"), ("〜のに", "vậy mà"))]
    explain(client, q1["id"], steps=list(steps))
    explain(client, q2["id"], steps=list(steps))
    attempt(client, exam["id"], {q1["id"]: 2, q2["id"]: 2})  # both wrong (chose のに)

    data = extract(client, attempt_id=None, question_ids=[q1["id"], q2["id"]])
    roles = {
        (c["question_id"], c["canonical_key"]): c["role"]
        for q in data["questions"]
        for c in q["candidates"]
    }
    assert (
        roles[(q1["id"], "grammar:ので")] == "tests"
        and roles[(q1["id"], "grammar:のに")] == "distractor"
    )
    first = confirm_all(client, data)
    assert first["created"] >= 2 and first["linked"] >= 2  # second question links to the same items
    ids = {i["knowledge_id"] for i in first["items"] if i["knowledge_id"]}
    titles = set(
        db_session.scalars(select(KnowledgeItem.canonical_key).where(KnowledgeItem.id.in_(ids)))
    )
    assert {"grammar:ので", "grammar:のに"} <= titles  # ので and のに are NOT merged

    types = dict(
        db_session.execute(
            select(ReviewItem.review_type, func.count()).group_by(ReviewItem.review_type)
        ).all()
    )
    assert types == {"original_question": 2, "knowledge_recall": 2, "contrast": 1}

    # Repeating the whole workflow creates nothing new
    again = confirm_all(client, extract(client, question_ids=[q1["id"], q2["id"]]))
    assert again["created"] == 0 and again["review_items_created"] == 0
    assert db_session.scalar(select(func.count(ReviewItem.id))) == 5

    noda = next(
        k
        for k in client.get(f"{API}/knowledge").json()["data"]
        if k["canonical_key"] == "grammar:ので"
    )
    detail = client.get(f"{API}/knowledge/{noda['id']}").json()["data"]
    assert len(detail["questions"]) == 2 and all(
        len(q["mistakes"]) == 1 for q in detail["questions"]
    )
    assert detail["stats"]["incorrect"] == 2
    assert [r["title"] for r in detail["related"]] == ["〜のに"] and detail["related"][0][
        "relation_type"
    ] == "confused_with"
    assert all(e["explanation_status"] == "approved" for e in detail["evidence"])


def test_homograph_needs_decision_and_new_sense(client, make_exam, make_question) -> None:  # type: ignore[no-untyped-def]
    exam = make_exam(title="語彙", category="vocabulary")
    q1 = make_question(
        exam["id"],
        1,
        question_type="contextual_definition",
        question_text="川に（　　）がかかっている。",
        options=["はし", "いし", "えだ", "なみ"],
    )
    q2 = make_question(
        exam["id"],
        2,
        question_type="contextual_definition",
        question_text="（　　）でご飯を食べる。",
        options=["はし", "さら", "なべ", "かぎ"],
    )

    def vocab(meaning: str):  # type: ignore[no-untyped-def]
        def m(p: dict[str, Any]) -> dict[str, Any]:
            p["vocabulary"] = [
                {"surface": "はし", "reading": "はし", "meaning_vi": meaning, "note": None}
            ]
            return p

        return m

    explain(client, q1["id"], steps=[vocab("cây cầu")])
    confirm_all(client, extract(client, question_ids=[q1["id"]]))
    explain(client, q2["id"], steps=[vocab("đôi đũa ăn cơm")])
    data = extract(client, question_ids=[q2["id"]])
    cand = next(
        c for c in data["questions"][0]["candidates"] if c["knowledge_type"] == "vocabulary"
    )
    assert cand["action"] == "needs_decision" and cand["match"]["reason"] == "same_key"
    result = confirm_all(client, data, **{cand["ref"]: "create_new_sense"})
    assert result["created"] == 1
    keys = sorted(
        k["canonical_key"]
        for k in client.get(f"{API}/knowledge", params={"type": "vocabulary"}).json()["data"]
    )
    assert keys == ["vocab:はし|はし", "vocab:はし|はし#2"]


def test_kanji_word_keyed_by_reading_in_context(client, make_exam, make_question) -> None:  # type: ignore[no-untyped-def]
    exam = make_exam(title="漢字", category="vocabulary")
    q1 = make_question(
        exam["id"],
        1,
        question_type="kanji_reading",
        question_text="部屋の書類を<u>整理</u>する。",
        options=["せいり", "せいりん", "しょうり", "しょり"],
    )
    q2 = make_question(
        exam["id"],
        2,
        question_type="kanji_reading",
        question_text="<u>生</u>の魚を食べる。",
        options=["なま", "せい", "しょう", "いき"],
    )
    q3 = make_question(
        exam["id"],
        3,
        question_type="kanji_reading",
        question_text="<u>生</u>活が楽になった。",
        options=["せい", "なま", "しょう", "いき"],
    )
    for q in (q1, q2, q3):
        explain(client, q["id"])
    data = extract(client, question_ids=[q1["id"], q2["id"], q3["id"]])
    keys = [
        c["canonical_key"]
        for q in data["questions"]
        for c in q["candidates"]
        if c["knowledge_type"] == "kanji"
    ]
    assert keys == [
        "kanji:整理|せいり",
        "kanji:生|なま",
        "kanji:生|せい",
    ]  # same kanji, different readings
    kanji = data["questions"][0]["candidates"][0]
    assert [x["option"] for x in kanji["details"]["confusions"]] == [
        "せいりん",
        "しょうり",
        "しょり",
    ]


def test_reading_skill_requires_evidence_or_user_choice(client, make_exam, make_question) -> None:  # type: ignore[no-untyped-def]
    exam = make_exam(title="読解", category="reading")
    passage = client.post(
        f"{API}/exams/{exam['id']}/passages",
        json={"content": "図書館は夜九時まで開いている。仕事の後でも行ける。"},
    ).json()["data"]
    q1 = make_question(
        exam["id"],
        1,
        question_type="reading_short",
        passage_id=passage["id"],
        question_text="筆者が一番伝えたいことは何か。",
        options=["a", "b", "c", "d"],
    )
    q2 = make_question(
        exam["id"],
        2,
        question_type="reading_short",
        passage_id=passage["id"],
        question_text="図書館について述べよ。",
        options=["e", "f", "g", "h"],
    )
    explain(client, q1["id"])
    explain(client, q2["id"])
    data = extract(client, question_ids=[q1["id"], q2["id"]])
    r1 = next(
        c for c in data["questions"][0]["candidates"] if c["knowledge_type"] == "reading_skill"
    )
    r2 = next(
        c for c in data["questions"][1]["candidates"] if c["knowledge_type"] == "reading_skill"
    )
    assert r1["details"]["skill"] == "author_view" and r1["details"]["evidence"]
    assert (
        r2["details"]["skill"] is None and r2["action"] == "needs_decision" and not r2["selected"]
    )
    item = {
        k: r2[k]
        for k in (
            "ref",
            "question_id",
            "explanation_id",
            "knowledge_type",
            "title",
            "summary",
            "details",
            "role",
        )
    }
    bad = client.post(f"{API}/knowledge/confirm", json={"items": [item | {"action": "create"}]})
    assert bad.status_code == 422  # no skill chosen → refused, not guessed
    item["details"] = item["details"] | {"skill": "detail_match"}
    ok = client.post(f"{API}/knowledge/confirm", json={"items": [item | {"action": "create"}]})
    assert ok.status_code == 200


def test_fuzzy_title_is_suggested_not_merged(client, grammar_exam) -> None:  # type: ignore[no-untyped-def]
    _exam, q1, q2 = grammar_exam
    explain(client, q1["id"], steps=[with_grammar(("〜ために", "để"))])
    first = extract(client, question_ids=[q1["id"]])
    ref = next(
        c["ref"] for c in first["questions"][0]["candidates"] if c["knowledge_type"] == "grammar"
    )
    confirm_all(client, first, **{ref: "create"})
    explain(client, q2["id"], steps=[with_grammar(("〜ためか", "có lẽ vì"))])
    cand = extract(client, question_ids=[q2["id"]])["questions"][0]["candidates"][0]
    assert cand["action"] == "needs_decision" and cand["match"]["reason"] == "similar_title"


# ----------------------------------------------------------------- merge / split
def test_merge_and_split(client, grammar_exam, make_question, db_session: Session) -> None:  # type: ignore[no-untyped-def]
    exam, q1, _ = grammar_exam
    q2 = make_question(
        exam["id"],
        3,
        question_text="暑い（　　）、窓を開けた。",
        options=["から", "のに", "ながら", "ばかりか"],
    )
    explain(client, q1["id"], steps=[with_grammar(("〜ので", "vì"))])
    explain(client, q2["id"], steps=[with_grammar(("〜から", "vì"))])
    attempt(client, exam["id"], {q1["id"]: 2, q2["id"]: 3})
    confirm_all(client, extract(client, question_ids=[q1["id"], q2["id"]]))
    items = {k["canonical_key"]: k for k in client.get(f"{API}/knowledge").json()["data"]}
    target, source = items["grammar:ので"], items["grammar:から"]
    merged = client.post(
        f"{API}/knowledge/merge", json={"target_id": target["id"], "source_ids": [source["id"]]}
    ).json()["data"]
    assert len(merged["questions"]) == 2
    src = db_session.get(KnowledgeItem, uuid.UUID(source["id"]))
    db_session.refresh(src)
    assert src.status == "merged" and str(src.merged_into_id) == target["id"]
    active_recall = db_session.scalar(
        select(func.count()).where(
            ReviewItem.review_type == "knowledge_recall", ReviewItem.status == "active"
        )
    )
    assert active_recall == 1  # duplicate recall card archived, not deleted

    split = client.post(
        f"{API}/knowledge/{target['id']}/split",
        json={"title": "〜から (lý do chủ quan)", "question_ids": [q2["id"]]},
    )
    assert split.status_code == 200, split.text
    new = split.json()["data"]
    assert new["canonical_key"] == "grammar:ので#2" and [
        q["question_id"] for q in new["questions"]
    ] == [q2["id"]]
    assert (
        client.post(
            f"{API}/knowledge/{target['id']}/split", json={"title": "x", "question_ids": [q1["id"]]}
        ).status_code
        == 422
    )


# ----------------------------------------------------------------- reviews
def _setup_reviews(client, grammar_exam) -> tuple[Any, ...]:  # type: ignore[no-untyped-def]
    exam, q1, q2 = grammar_exam
    explain(
        client, q1["id"], steps=[with_grammar(("〜ので", "vì (nguyên nhân)"), ("〜のに", "vậy mà"))]
    )
    attempt(client, exam["id"], {q1["id"]: 2, q2["id"]: None})
    confirm_all(client, extract(client, question_ids=[q1["id"]]))
    return exam, q1, q2


def test_session_hides_answers_and_only_ratings_count(
    client, grammar_exam, db_session: Session
) -> None:  # type: ignore[no-untyped-def]
    _setup_reviews(client, grammar_exam)
    due = client.get(f"{API}/reviews", params={"bucket": "due"}).json()["data"]
    assert due["counts"]["due"] == 4  # A + B(ので) + B(のに) + C
    session = client.post(f"{API}/reviews/sessions", json={"limit": 10}).json()["data"]
    assert len(session["cards"]) == 4
    assert all("answer_index" not in c for c in session["cards"])
    card = next(c for c in session["cards"] if c["kind"] == "question")
    assert card["options"] == ["ので", "のに", "ながら", "ばかりか"]

    # Rating before answering a gradable card is refused
    r = client.post(f"{API}/reviews/events", json={"request_id": str(uuid.uuid4()), "review_item_id": card["review_item_id"],
                                                     "rating": "good", "session_id": session["id"], "card_id": card["card_id"]})  # fmt: skip
    assert r.status_code == 422
    answered = client.post(
        f"{API}/reviews/sessions/{session['id']}/answer",
        json={"card_id": card["card_id"], "selected_index": 1},
    ).json()["data"]
    assert answered["card"]["correct"] is False and answered["card"]["answer_index"] == 0
    assert answered["reveal"]["type"] == "explanation"
    assert db_session.scalar(select(func.count(ReviewEvent.id))) == 0  # viewing ≠ reviewing
    item = db_session.get(ReviewItem, uuid.UUID(card["review_item_id"]))
    assert item.review_count == 0

    req = str(uuid.uuid4())
    body = {"request_id": req, "review_item_id": card["review_item_id"], "rating": "again", "timezone": "Asia/Ho_Chi_Minh",
            "session_id": session["id"], "card_id": card["card_id"]}  # fmt: skip
    first = client.post(f"{API}/reviews/events", json=body)
    assert first.status_code == 201
    ev = first.json()["data"]
    assert ev["event"]["answer_correct"] is False and ev["event"]["selected_answer_index"] == 1
    assert (
        ev["event"]["previous_state"]["state"] == "new"
        and ev["event"]["next_state"]["state"] == "learning"
    )
    assert ev["item"]["review_count"] == 1 and ev["item"]["step_index"] == 0
    replay = client.post(f"{API}/reviews/events", json=body)
    assert replay.status_code == 200 and replay.json()["data"]["duplicate"] is True
    assert db_session.scalar(select(func.count(ReviewEvent.id))) == 1


@pytest.mark.parametrize(
    ("rating", "step", "minutes"),
    [("again", 0, 20), ("hard", 0, 20), ("good", 1, 60), ("easy", 2, 1440)],
)
def test_ratings_schedule_new_items(
    client, grammar_exam, rating: str, step: int, minutes: int
) -> None:  # type: ignore[no-untyped-def]
    _setup_reviews(client, grammar_exam)
    item = client.get(f"{API}/reviews/due").json()["data"][0]
    assert item["srs_state"] == "new" and item["due_at"] is not None
    ev = client.post(f"{API}/reviews/events", json={"request_id": str(uuid.uuid4()), "review_item_id": item["id"],
                                                      "rating": rating, "timezone": "Asia/Ho_Chi_Minh"}).json()["data"]  # fmt: skip
    assert ev["item"]["step_index"] == step and ev["item"]["interval_minutes"] == minutes
    assert ev["event"]["algorithm_version"] == "ladder-v1"
    history = client.get(f"{API}/reviews/history", params={"review_item_id": item["id"]}).json()[
        "data"
    ]
    assert [h["rating"] for h in history] == [rating]
    assert (
        client.get(f"{API}/reviews", params={"bucket": "completed"}).json()["data"]["counts"][
            "completed"
        ]
        == 1
    )


def test_event_validation(client, grammar_exam) -> None:  # type: ignore[no-untyped-def]
    _setup_reviews(client, grammar_exam)
    item = client.get(f"{API}/reviews/due").json()["data"][0]
    base = {"review_item_id": item["id"], "rating": "good"}
    assert (
        client.post(
            f"{API}/reviews/events",
            json=base | {"request_id": str(uuid.uuid4()), "timezone": "Mars/Base"},
        ).status_code
        == 422
    )
    future = (utcnow() + timedelta(days=1)).isoformat()
    assert (
        client.post(
            f"{API}/reviews/events",
            json=base | {"request_id": str(uuid.uuid4()), "reviewed_at": future},
        ).status_code
        == 422
    )
    paused = client.patch(
        f"{API}/reviews/{item['id']}", json={"version": item["version"], "status": "suspended"}
    ).json()["data"]
    assert paused["status"] == "suspended"
    assert (
        client.post(
            f"{API}/reviews/events", json=base | {"request_id": str(uuid.uuid4())}
        ).status_code
        == 409
    )


def test_blocked_items_go_to_insufficient_bucket(client, grammar_exam) -> None:  # type: ignore[no-untyped-def]
    _exam, q1, _ = _setup_reviews(client, grammar_exam)
    client.patch(f"{API}/questions/{q1['id']}", json={"answer_status": "unverified"})
    data = client.get(f"{API}/reviews", params={"bucket": "insufficient"}).json()["data"]
    assert [i["blocked_reason"] for i in data["items"]] == ["answer_not_verified"]
    assert all(
        c["kind"] != "question"
        for c in client.post(f"{API}/reviews/sessions", json={}).json()["data"]["cards"]
    )


# ----------------------------------------------------------------- analytics
def test_analytics_use_real_data_and_respect_sample_size(
    client, grammar_exam, db_session: Session
) -> None:  # type: ignore[no-untyped-def]
    exam, q1, q2 = grammar_exam
    explain(client, q1["id"], steps=[with_grammar(("〜ので", "vì"))])
    explain(client, q2["id"], steps=[with_grammar(("〜ので", "vì"))])
    attempt(
        client, exam["id"], {q1["id"]: 2, q2["id"]: None}, "2026-01-05T00:00:00Z"
    )  # 1 wrong, 1 blank
    confirm_all(client, extract(client, question_ids=[q1["id"], q2["id"]]))
    k = next(
        k
        for k in client.get(f"{API}/knowledge").json()["data"]
        if k["canonical_key"] == "grammar:ので"
    )
    s = k["stats"]
    assert (s["incorrect"], s["unanswered"], s["correct"]) == (1, 1, 0)  # blank is NOT wrong
    assert s["error_rate"] == 1.0 and s["confidence"] == "low"
    # due review → review_now; once reviewed far ahead with few observations → insufficient_data
    db_session.execute(update(ReviewItem).values(due_at=utcnow() + timedelta(days=30)))
    db_session.commit()
    s = client.get(f"{API}/analytics/knowledge/{k['id']}").json()["data"]["windows"]["all"]
    assert s["priority"] == "insufficient_data"

    for day in ("2026-01-06", "2026-01-07", "2026-01-08"):
        attempt(client, exam["id"], {q1["id"]: 2, q2["id"]: 2}, f"{day}T00:00:00Z")
    report = client.get(f"{API}/analytics/weaknesses").json()["data"]
    top = report["top_knowledge"][0]
    assert top["incorrect"] == 7 and top["confidence"] == "medium" and top["error_rate_low"] > 0.5
    assert (
        report["categories"]["grammar"]["unanswered"] == 1
        and report["categories"]["grammar"]["incorrect"] == 7
    )
    assert report["min_observations"] == 3
    progress = client.get(f"{API}/analytics/review-progress").json()["data"]
    assert progress["total_reviews"] == 0  # nothing invented
