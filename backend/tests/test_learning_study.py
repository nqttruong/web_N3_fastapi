"""Real PostgreSQL API checks for durable Web learning and source-specific rights."""

from uuid import uuid4

from app.core.config import get_settings
from app.learning_content.models import LearningItem
from app.learning_content.service import apply_snapshot
from app.learning_content.source import scan_source
from app.learning_content.study_models import LearningStudyEvent, LearningStudyProgress
from tests.test_learning_content_sync import create_run, fixture_pack, git_source


def _import_fixture(db_session, test_settings, root):  # type: ignore[no-untyped-def]
    run = create_run(db_session)
    apply_snapshot(db_session, run.id, scan_source(root), test_settings)
    db_session.commit()


def test_study_session_persists_rating_and_retries_idempotently(
    client,
    db_session,
    test_settings,
    tmp_path,  # type: ignore[no-untyped-def]
) -> None:
    root = tmp_path / "android"
    git_source(root, fixture_pack())
    _import_fixture(db_session, test_settings, root)
    lessons = client.get("/api/v1/learning-content/lessons").json()["data"]
    assert len(lessons) == 1
    assert lessons[0]["total"] == 3
    assert lessons[0]["learned"] == 0
    detail = client.get("/api/v1/learning-content/lessons/fixture-n3/lesson-1")
    assert detail.status_code == 200
    assert len(detail.json()["data"]["items"]) == 3
    first_item_id = detail.json()["data"]["items"][0]["id"]
    assert client.put(f"/api/v1/learning-content/items/{first_item_id}/saved").json()["data"] == {
        "saved": True
    }
    assert len(client.get("/api/v1/learning-content/saved").json()["data"]) == 1
    assert client.delete(f"/api/v1/learning-content/items/{first_item_id}/saved").json()[
        "data"
    ] == {"saved": False}
    assert client.get("/api/v1/learning-content/saved").json()["data"] == []
    started = client.post(
        "/api/v1/learning-content/study/sessions",
        json={"mode": "lesson", "pack_id": "fixture-n3", "lesson_id": "lesson-1"},
    )
    assert started.status_code == 201, started.text
    session = started.json()["data"]
    assert session["total"] == 3
    event_id = str(uuid4())
    payload = {"request_id": event_id, "rating": "good", "time_zone": "Asia/Bangkok"}
    rated = client.post(
        f"/api/v1/learning-content/study/sessions/{session['id']}/rate", json=payload
    )
    assert rated.status_code == 200, rated.text
    assert rated.json()["data"]["position"] == 1
    retry = client.post(
        f"/api/v1/learning-content/study/sessions/{session['id']}/rate", json=payload
    )
    assert retry.status_code == 200
    assert retry.json()["data"]["position"] == 1
    assert db_session.query(LearningStudyEvent).count() == 1
    assert db_session.query(LearningStudyProgress).count() == 0
    review = client.post("/api/v1/learning-content/study/sessions", json={"mode": "review"})
    assert review.status_code == 201, review.text
    review_id = review.json()["data"]["id"]
    assert review.json()["data"]["total"] == 3
    rated_review = client.post(
        f"/api/v1/learning-content/study/sessions/{review_id}/rate",
        json={"request_id": str(uuid4()), "rating": "good", "time_zone": "Asia/Bangkok"},
    )
    assert rated_review.status_code == 200, rated_review.text
    progress = db_session.query(LearningStudyProgress).one()
    assert progress.step_index == 1
    assert progress.review_count == 1
    assert progress.interval_minutes == 60
    overview = client.get("/api/v1/learning-content/study/overview?time_zone=Asia/Bangkok")
    assert overview.status_code == 200
    assert overview.json()["data"]["learned"] == 1
    assert overview.json()["data"]["recent_activity"][0]["origin"] == "web"
    assert overview.json()["data"]["available_new"] == 2
    assert (
        client.get(f"/api/v1/learning-content/study/sessions/{session['id']}").json()["data"][
            "position"
        ]
        == 1
    )


def test_composite_course_mixed_and_type_sessions_resume_without_changing_srs(
    client,
    db_session,
    test_settings,
    tmp_path,  # type: ignore[no-untyped-def]
) -> None:
    root = tmp_path / "android"
    git_source(root, fixture_pack())
    _import_fixture(db_session, test_settings, root)

    courses = client.get("/api/v1/learning-content/course").json()["data"]
    assert len(courses) == 1
    assert courses[0]["counts"] == {"vocabulary": 1, "grammar": 1, "kanji": 1}

    started = client.post(
        "/api/v1/learning-content/study/sessions",
        json={"mode": "course", "course_number": 1},
    )
    assert started.status_code == 201, started.text
    session = started.json()["data"]
    assert session["total"] == 3
    assert session["current"]["item_type"] == "vocabulary"

    rated = client.post(
        f"/api/v1/learning-content/study/sessions/{session['id']}/rate",
        json={"request_id": str(uuid4()), "rating": "good"},
    )
    assert rated.status_code == 200, rated.text
    assert rated.json()["data"]["position"] == 1
    # A new GET after the rating simulates reopening the page/app route.
    resumed = client.get(f"/api/v1/learning-content/study/sessions/{session['id']}")
    assert resumed.status_code == 200
    assert resumed.json()["data"]["position"] == 1
    assert resumed.json()["data"]["current"]["item_type"] == "grammar"
    assert db_session.query(LearningStudyEvent).one().origin == "web_practice"
    assert db_session.query(LearningStudyProgress).count() == 0

    for item_type in ("vocabulary", "grammar", "kanji"):
        filtered = client.post(
            "/api/v1/learning-content/study/sessions",
            json={"mode": "course", "course_number": 1, "item_type": item_type},
        )
        assert filtered.status_code == 201, filtered.text
        assert filtered.json()["data"]["total"] == 1
        assert filtered.json()["data"]["current"]["item_type"] == item_type


def test_source_rights_are_specific_and_restore_blocked_vocabulary(
    client,
    db_session,
    test_settings,
    tmp_path,  # type: ignore[no-untyped-def]
) -> None:
    root = tmp_path / "android"
    pack = fixture_pack()
    pack["sources"][0]["licenseVerified"] = False
    git_source(root, pack)
    _import_fixture(db_session, test_settings, root)
    assert db_session.query(LearningItem).count() == 0
    client.app.dependency_overrides[get_settings] = lambda: test_settings.model_copy(
        update={"android_learning_source_dir": root}
    )
    declaration = client.put(
        "/api/v1/learning-content/rights/sources",
        json={
            "pack_id": "fixture-n3",
            "source_id": "authored",
            "rights_holder": "Fixture Author",
            "rights_basis": "Personal-use licence for this fixture",
            "allowed_usage": "Private JLPT learning on this instance",
            "scope": "private",
            "approved": True,
        },
    )
    assert declaration.status_code == 200, declaration.text
    from app.learning_content.study_models import LearningSourceRight

    approved = db_session.get(LearningSourceRight, ("fixture-n3", "authored"))
    assert approved is not None and approved.approved
    run = create_run(db_session)
    apply_snapshot(
        db_session, run.id, scan_source(root, {("fixture-n3", "authored")}), test_settings
    )
    db_session.commit()
    assert db_session.query(LearningItem).count() == 3
    assert db_session.query(LearningItem).filter_by(item_type="vocabulary").count() == 1
    run = create_run(db_session)
    apply_snapshot(
        db_session, run.id, scan_source(root, {("fixture-n3", "authored")}), test_settings
    )
    db_session.commit()
    assert db_session.query(LearningItem).count() == 3


def test_grammar_exercise_answer_is_durable_idempotent_and_does_not_change_srs(
    client,
    db_session,
    test_settings,
    tmp_path,  # type: ignore[no-untyped-def]
) -> None:
    from app.learning_content.study_models import LearningExerciseAnswer

    root = tmp_path / "android"
    pack = fixture_pack()
    pack["lessons"][0]["grammar"][0]["exercises"] = [
        {
            "id": "grammar-ex-1",
            "prompt": "{日本|にほん}に＿＿＿ばかりです。",
            "options": ["{来|く}る", "{来|き}た", "{来|き}て", "{来|こ}ない"],
            "answerIndex": 1,
            "explanationVi": "Thể た + ばかり",
        }
    ]
    git_source(root, pack)
    _import_fixture(db_session, test_settings, root)
    item = db_session.query(LearningItem).filter_by(item_type="grammar").one()
    route = f"/api/v1/learning-content/items/{item.id}/exercises/grammar-ex-1/answers"
    request_id = str(uuid4())
    answer = client.post(route, json={"request_id": request_id, "selected_index": 0})
    assert answer.status_code == 201, answer.text
    assert answer.json()["data"]["is_correct"] is False
    assert answer.json()["data"]["answer_index"] == 1
    retry = client.post(route, json={"request_id": request_id, "selected_index": 0})
    assert retry.status_code == 201
    assert retry.json()["data"]["duplicate"] is True
    assert (
        client.post(route, json={"request_id": request_id, "selected_index": 1}).status_code == 409
    )
    correct = client.post(route, json={"request_id": str(uuid4()), "selected_index": 1})
    assert correct.status_code == 201 and correct.json()["data"]["is_correct"] is True
    assert db_session.query(LearningExerciseAnswer).count() == 2
    assert db_session.query(LearningStudyProgress).count() == 0
    detail = client.get("/api/v1/learning-content/lessons/fixture-n3/lesson-1").json()["data"]
    grammar = next(row for row in detail["items"] if row["item_type"] == "grammar")
    assert grammar["exercise_results"]["grammar-ex-1"]["is_correct"] is True
