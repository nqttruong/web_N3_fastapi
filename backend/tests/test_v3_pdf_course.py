"""Verified Mimikara source extraction and source-preserving lesson grouping."""

from uuid import uuid4

import pytest

from app.learning_content.course import group_course_items
from app.learning_content.mimikara_pdf import PACK_ID, SOURCE_ID, extract_words
from app.learning_content.models import LearningContentPack, LearningItem
from app.learning_content.pdf_import import pdf_snapshot
from app.learning_content.service import apply_snapshot
from app.learning_content.study_models import LearningSourceRight
from tests.test_learning_content_sync import create_run


def test_pdf_extracts_verified_rows_and_unicode(test_settings) -> None:  # type: ignore[no-untyped-def]
    path = test_settings.mimikara_pdf_path
    if not path.is_file():
        pytest.skip("Operator-supplied private PDF is not present in this checkout")
    digest, rows = extract_words(path)
    assert digest == "a943ffaf90149f7d98bff5fb4d4296195adc942796600a2aefe9ce8243ac5728"
    assert len(rows) == 880
    assert [row.number for row in rows] == list(range(1, 881))
    assert rows[0].expression and rows[0].reading and rows[0].meaning_vi
    assert all(ord(char) > 127 for char in rows[0].expression)
    assert rows[439].expression and rows[439].meaning_vi
    assert rows[-1].expression and rows[-1].meaning_vi
    assert sum(row.reading is None for row in rows) == 41
    assert rows[795].expression and any(ord(char) > 127 for char in rows[795].expression)


def test_pdf_preview_shows_source_samples_without_import(client, db_session, test_settings) -> None:  # type: ignore[no-untyped-def]
    if not test_settings.mimikara_pdf_path.is_file():
        pytest.skip("Operator-supplied private PDF is not present in this checkout")
    response = client.get("/api/v1/learning-content/rights/pdf-preview")
    assert response.status_code == 200
    preview = response.json()["data"]
    assert preview["row_count"] == 880
    assert [row["number"] for row in preview["samples"]] == [1, 2, 3, 439, 440, 441, 878, 879, 880]
    assert preview["samples"][0]["expression"]
    assert preview["samples"][0]["reading"]
    assert db_session.query(LearningItem).count() == 0


def test_grouping_caps_and_incomplete_last_lesson() -> None:
    groups = group_course_items(
        {
            "vocabulary": list(range(880)),
            "grammar": list(range(64)),
            "kanji": list(range(393)),
        }
    )
    assert len(groups) == 30
    assert {kind: len(groups[0][kind]) for kind in groups[0]} == {
        "vocabulary": 30,
        "grammar": 7,
        "kanji": 24,
    }
    assert {kind: len(groups[-1][kind]) for kind in groups[-1]} == {
        "vocabulary": 10,
        "grammar": 0,
        "kanji": 0,
    }
    assert [item for group in groups for item in group["vocabulary"]] == list(range(880))


def test_private_pdf_import_is_idempotent_and_keeps_other_packs(
    db_session,
    test_settings,  # type: ignore[no-untyped-def]
) -> None:
    if not test_settings.mimikara_pdf_path.is_file():
        pytest.skip("Operator-supplied private PDF is not present in this checkout")
    digest, _ = extract_words(test_settings.mimikara_pdf_path)
    db_session.add(
        LearningSourceRight(
            pack_id=PACK_ID,
            source_id=SOURCE_ID,
            source_name="Private PDF",
            source_content_hash=digest,
            rights_holder="Operator declaration",
            rights_basis="Private use only for this exact document",
            allowed_usage="Private local study application only",
            scope="private",
            approved=True,
        )
    )
    db_session.commit()
    source = pdf_snapshot(db_session, test_settings)
    first = create_run(db_session)
    counts = apply_snapshot(db_session, first.id, source, test_settings, managed_path_prefix="pdf:")
    db_session.commit()
    assert counts["new_vocabulary"] == 880
    assert db_session.query(LearningItem).filter_by(item_type="vocabulary").count() == 880
    again = create_run(db_session)
    counts = apply_snapshot(
        db_session,
        again.id,
        pdf_snapshot(db_session, test_settings),
        test_settings,
        managed_path_prefix="pdf:",
    )
    db_session.commit()
    assert counts.get("new_vocabulary", 0) == 0
    assert db_session.query(LearningItem).count() == 880
    assert db_session.query(LearningContentPack).filter_by(id=PACK_ID).one().is_archived is False


def test_course_session_progress_persists_without_mutating_srs(
    client,
    db_session,
    test_settings,  # type: ignore[no-untyped-def]
) -> None:
    if not test_settings.mimikara_pdf_path.is_file():
        pytest.skip("Operator-supplied private PDF is not present in this checkout")
    digest, _ = extract_words(test_settings.mimikara_pdf_path)
    db_session.add(
        LearningSourceRight(
            pack_id=PACK_ID,
            source_id=SOURCE_ID,
            source_name="Private PDF",
            source_content_hash=digest,
            rights_holder="Operator declaration",
            rights_basis="Private use only for this exact document",
            allowed_usage="Private local study application only",
            scope="private",
            approved=True,
        )
    )
    db_session.commit()
    run = create_run(db_session)
    apply_snapshot(
        db_session,
        run.id,
        pdf_snapshot(db_session, test_settings),
        test_settings,
        managed_path_prefix="pdf:",
    )
    db_session.commit()
    lessons = client.get("/api/v1/learning-content/course").json()["data"]
    assert len(lessons) == 30 and lessons[0]["counts"]["vocabulary"] == 30
    started = client.post(
        "/api/v1/learning-content/study/sessions",
        json={"mode": "course", "course_number": 1, "item_type": "vocabulary"},
    )
    assert started.status_code == 201 and started.json()["data"]["total"] == 30
    session_id = started.json()["data"]["id"]
    request_id = str(uuid4())
    rated = client.post(
        f"/api/v1/learning-content/study/sessions/{session_id}/rate",
        json={"request_id": request_id, "rating": "good"},
    )
    assert rated.status_code == 200
    assert client.get("/api/v1/learning-content/course").json()["data"][0]["learned"] == 1
    assert (
        client.post(
            f"/api/v1/learning-content/study/sessions/{session_id}/rate",
            json={"request_id": request_id, "rating": "good"},
        ).status_code
        == 200
    )
