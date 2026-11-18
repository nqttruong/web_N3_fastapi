"""PR4 — AI practice generation (fake provider, no real API calls)."""

import json
import uuid
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.explanations.interfaces import ProviderError, ProviderTimeoutError, Usage
from app.explanations.providers.registry import set_generator_for_tests
from app.practice.context import PracticeContext
from app.practice.generator import PracticeResult, set_practice_generator_for_tests
from app.practice.models import GeneratedPracticeQuestion
from app.practice.payload import PracticeSet
from tests.explain_fakes import FakeGenerator
from tests.test_knowledge import attempt, confirm_all, explain, extract, with_grammar

API = "/api/v1"


def practice_question(text: str, options: list[str], answer: int = 0) -> dict[str, Any]:
    return {
        "question_type": "grammar_form",
        "question_text": text,
        "options": options,
        "answer_index": answer,
        "explanation_vi": "「ので」 nêu nguyên nhân khách quan dẫn tới kết quả ở vế sau.",
        "options_analysis": [
            {"option_index": i, "option_text": o, "reason": f"Lý do cho {o}"}
            for i, o in enumerate(options)
        ],
        "focus": "phân biệt ので/のに",
    }


GOOD = [
    practice_question(
        "電車が遅れた（　　）、会議に遅刻した。", ["ので", "のに", "ながら", "ばかりか"]
    ),
    practice_question("熱がある（　　）、今日は休みます。", ["ので", "のに", "くせに", "わりに"]),
]


class FakePractice:
    provider = "fake"
    model = "fake-practice-1"

    def __init__(self, steps: list[Any] | None = None) -> None:
        self.steps = list(steps or [])
        self.calls: list[tuple[PracticeContext, list[str] | None]] = []

    def generate(
        self, ctx: PracticeContext, *, feedback: list[str] | None = None
    ) -> PracticeResult:
        self.calls.append((ctx, feedback))
        step = self.steps.pop(0) if self.steps else None
        if isinstance(step, ProviderError):
            raise step
        questions = step if isinstance(step, list) else GOOD[: ctx.count]
        payload = PracticeSet.model_validate(
            {"schema_version": "1.0", "knowledge_id": str(ctx.knowledge_id), "questions": questions}
        )
        return PracticeResult(payload, Usage(800, 600), self.model)


@pytest.fixture(autouse=True)
def _providers(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.explanations.retry.time.sleep", lambda s: None)
    set_generator_for_tests(FakeGenerator())
    yield
    set_practice_generator_for_tests(None)


@pytest.fixture
def knowledge(client: TestClient, make_exam, make_question) -> dict[str, Any]:  # type: ignore[no-untyped-def]
    exam = make_exam(title="練習", category="grammar")
    q = make_question(exam["id"], 1)  # 雨が降っている（　　）、… options ので のに ながら ばかりか
    explain(client, q["id"], steps=[with_grammar(("〜ので", "vì"), ("〜のに", "vậy mà"))])
    attempt(client, exam["id"], {q["id"]: 2})
    confirm_all(client, extract(client, question_ids=[q["id"]]))
    k = next(
        k
        for k in client.get(f"{API}/knowledge").json()["data"]
        if k["canonical_key"] == "grammar:ので"
    )
    return {"knowledge": k, "question": q}


def test_generate_saves_needs_review_and_approval_enables_use(
    client, knowledge, db_session: Session
) -> None:  # type: ignore[no-untyped-def]
    fake = FakePractice()
    set_practice_generator_for_tests(fake)
    kid = knowledge["knowledge"]["id"]
    r = client.post(f"{API}/practice/generate", json={"knowledge_id": kid, "count": 2})
    assert r.status_code == 201, r.text
    gen = r.json()["data"]
    assert gen["status"] == "completed" and gen["accepted_count"] == 2
    assert all(q["status"] == "needs_review" for q in gen["questions"])
    ctx, _ = fake.calls[0]
    assert ctx.confusions[0]["title"] == "〜のに"  # confusable item from the knowledge graph
    assert any("雨が降っている" in a["question_text"] for a in ctx.avoid_questions)
    assert (
        client.get(f"{API}/practice/generation-jobs/{gen['id']}").json()["data"]["id"] == gen["id"]
    )

    # Not approved → never used in reviews
    session = client.post(f"{API}/reviews/sessions", json={}).json()["data"]
    assert all(c["kind"] != "practice" for c in session["cards"])

    q1 = gen["questions"][0]["id"]
    approved = client.post(f"{API}/practice/{q1}/approve", json={"note": "ok"}).json()["data"]
    assert approved["status"] == "approved" and approved["reviewed_at"]
    client.post(f"{API}/practice/{gen['questions'][1]['id']}/reject", json={})
    assert (
        client.post(f"{API}/practice/{gen['questions'][1]['id']}/approve", json={}).status_code
        == 409
    )
    session = client.post(f"{API}/reviews/sessions", json={}).json()["data"]
    practice_cards = [c for c in session["cards"] if c["kind"] == "practice"]
    assert len(practice_cards) == 1 and practice_cards[0]["prompt"] == GOOD[0]["question_text"]


def test_invalid_and_duplicate_questions_are_dropped(
    client, knowledge, db_session: Session
) -> None:  # type: ignore[no-untyped-def]
    src = knowledge["question"]
    reordered = practice_question(src["question_text"], list(reversed(src["options"])))
    same_stem = practice_question(src["question_text"], ["ので", "から", "ため", "けど"])
    broken = practice_question("Không có tiếng Nhật", ["a", "a"])
    set_practice_generator_for_tests(FakePractice([[GOOD[0], reordered, same_stem, broken]]))
    gen = client.post(
        f"{API}/practice/generate", json={"knowledge_id": knowledge["knowledge"]["id"], "count": 4}
    ).json()["data"]
    assert gen["status"] == "partial" and gen["accepted_count"] == 1
    codes = {i["code"] for i in gen["issues"]}
    assert {"reordered_duplicate", "same_stem", "bad_options", "not_japanese"} <= codes

    # Generating the same question again is a duplicate of the stored one → retried, then refused
    set_practice_generator_for_tests(FakePractice([[GOOD[0]], [GOOD[0]]]))
    r = client.post(
        f"{API}/practice/generate", json={"knowledge_id": knowledge["knowledge"]["id"], "count": 1}
    )
    assert r.status_code == 502
    assert db_session.scalar(select(func.count(GeneratedPracticeQuestion.id))) == 1


def test_provider_failures_and_unavailable(
    client, knowledge, test_settings, db_session: Session
) -> None:  # type: ignore[no-untyped-def]
    kid = knowledge["knowledge"]["id"]
    test_settings.ai_max_retries = 1
    set_practice_generator_for_tests(
        FakePractice([ProviderTimeoutError("t"), ProviderTimeoutError("t")])
    )
    r = client.post(f"{API}/practice/generate", json={"knowledge_id": kid, "count": 1})
    assert (
        r.status_code == 502 and r.json()["error"]["details"]["provider_code"] == "provider_timeout"
    )
    assert db_session.scalar(select(func.count(GeneratedPracticeQuestion.id))) == 0

    set_practice_generator_for_tests(None)
    set_generator_for_tests(None)
    test_settings.openai_api_key = None
    r = client.post(f"{API}/practice/generate", json={"knowledge_id": kid, "count": 1})
    assert r.status_code == 503 and r.json()["error"]["details"]["fallback"] == "manual"
    exported = client.post(f"{API}/practice/export-prompt", json={"knowledge_id": kid, "count": 2})
    assert exported.status_code == 200
    prompt = exported.json()["data"]["prompt"]
    assert kid in prompt and "<practice_data>" in prompt and "〜のに" in prompt


def test_manual_import_preview_and_save(client, knowledge) -> None:  # type: ignore[no-untyped-def]
    kid = knowledge["knowledge"]["id"]
    body = {"knowledge_id": kid, "count": 2,
            "raw_json": "```json\n" + json.dumps({"schema_version": "1.0", "knowledge_id": kid, "questions": GOOD}, ensure_ascii=False) + "\n```"}  # fmt: skip
    preview = client.post(f"{API}/practice/manual-import", json=body).json()["data"]
    assert preview["saved"] is False and all(q["ok"] for q in preview["questions"])
    saved = client.post(
        f"{API}/practice/manual-import", json=body | {"save": True, "model_label": "ChatGPT"}
    )
    assert saved.status_code == 201
    gen = saved.json()["data"]["generation"]
    assert gen["origin"] == "manual" and gen["model"] == "ChatGPT" and gen["accepted_count"] == 2
    assert all(q["status"] == "needs_review" for q in gen["questions"])

    foreign = {"schema_version": "1.0", "knowledge_id": str(uuid.uuid4()), "questions": GOOD[:1]}
    r = client.post(
        f"{API}/practice/manual-import", json={"knowledge_id": kid, "raw_json": json.dumps(foreign)}
    ).json()["data"]
    assert r["set_errors"][0]["code"] == "knowledge_id_mismatch"
    assert (
        client.post(
            f"{API}/practice/manual-import", json={"knowledge_id": kid, "raw_json": "{x"}
        ).status_code
        == 422
    )


def test_practice_requires_active_knowledge_with_approved_source(client, knowledge) -> None:  # type: ignore[no-untyped-def]
    set_practice_generator_for_tests(FakePractice())
    k = knowledge["knowledge"]
    detail = client.get(f"{API}/knowledge/{k['id']}").json()["data"]
    client.patch(
        f"{API}/knowledge/{k['id']}", json={"version": detail["version"], "status": "archived"}
    )
    assert (
        client.post(
            f"{API}/practice/generate", json={"knowledge_id": k["id"], "count": 1}
        ).status_code
        == 422
    )
    assert (
        client.post(
            f"{API}/practice/generate", json={"knowledge_id": str(uuid.uuid4()), "count": 1}
        ).status_code
        == 404
    )
    assert (
        client.post(
            f"{API}/practice/generate", json={"knowledge_id": k["id"], "count": 9}
        ).status_code
        == 422
    )
