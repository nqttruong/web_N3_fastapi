import json
import subprocess
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from threading import Barrier, Thread
from typing import Any, cast

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings
from app.exams.models import Exam
from app.learning_content.models import (
    LearningContentChange,
    LearningContentPack,
    LearningItem,
    LearningSyncRun,
)
from app.learning_content.service import apply_snapshot, enqueue_sync, recover_stale_runs
from app.learning_content.source import (
    SourceValidationError,
    canonical_hash,
    scan_source,
)


def fixture_pack(*, version: int = 1) -> dict[str, Any]:
    return {
        "format": "n3sensei-content-pack",
        "formatVersion": 1,
        "pack": {
            "id": "fixture-n3",
            "title": "N3 Fixture",
            "version": version,
            "jlptLevel": "N3",
            "defaultSourceId": "authored",
        },
        "sources": [
            {
                "id": "authored",
                "name": "Fixture Author",
                "license": "CC BY 4.0",
                "licenseVerified": True,
            }
        ],
        "examples": [
            {
                "id": "ex-word",
                "japanese": "日本で{勉強|べんきょう}する。",
                "furigana": "日本で{勉強|べんきょう}する。",
                "translationVi": "Học ở Nhật.",
            },
            {
                "id": "ex-kanji",
                "japanese": "学校へ行く。",
                "furigana": "{学校|がっこう}へ{行|い}く。",
                "translationVi": "Đi đến trường.",
            },
        ],
        "lessons": [
            {
                "id": "lesson-1",
                "number": 1,
                "title": "Bài học một",
                "description": "Fixture",
                "vocabulary": [
                    {
                        "id": "word-1",
                        "expression": "勉強",
                        "reading": "べんきょう",
                        "furigana": "{勉強|べんきょう}",
                        "meaningVi": "học tập",
                        "examples": ["ex-word"],
                    }
                ],
                "kanji": [
                    {
                        "id": "kanji-1",
                        "character": "学",
                        "onReadings": ["ガク"],
                        "kunReadings": ["まな.ぶ"],
                        "meaningVi": "học",
                        "examples": ["ex-kanji"],
                    }
                ],
                "grammar": [
                    {
                        "id": "grammar-1",
                        "pattern": "〜ている",
                        "structure": "Vて + いる",
                        "meaningVi": "đang…",
                        "usage": "Hành động đang diễn ra.",
                        "examples": [],
                        "exercises": [],
                    }
                ],
            }
        ],
    }


def git_source(root: Path, data: dict[str, object]) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    subprocess.run(["git", "-C", str(root), "config", "user.name", "Sync Fixture"], check=True)
    subprocess.run(
        ["git", "-C", str(root), "config", "user.email", "sync-fixture@example.test"],
        check=True,
    )
    path = root / "app/src/main/assets/content/fixture.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    subprocess.run(["git", "-C", str(root), "add", str(path.relative_to(root))], check=True)
    subprocess.run(["git", "-C", str(root), "commit", "-qm", "fixture pack v1"], check=True)
    return path


def create_run(db_session: Session, trigger: str = "manual") -> LearningSyncRun:
    run = LearningSyncRun(status="running", trigger=trigger, attempts=1)
    db_session.add(run)
    db_session.flush()
    return run


def test_scanner_reads_only_tracked_assets_and_preserves_unicode(tmp_path: Path) -> None:
    root = tmp_path / "android"
    data = fixture_pack()
    path = git_source(root, data)
    untracked = path.with_name("untracked.json")
    untracked.write_text(json.dumps(fixture_pack(), ensure_ascii=False), encoding="utf-8")

    snapshot = scan_source(root)
    assert len(snapshot.packs) == 1
    pack = snapshot.packs[0]
    assert pack.source_commit_sha
    assert pack.version == 1
    assert len(pack.lessons) == 1
    assert len(pack.lessons[0].content_items) == 3
    assert len(pack.examples) == 2
    vocabulary = pack.lessons[0].content_items[0]
    assert vocabulary.payload["expression"] == "勉強"
    assert vocabulary.payload["furigana"] == "{勉強|べんきょう}"
    assert untracked.exists()  # the scanner did not modify or delete source files


def test_unverified_source_records_are_quarantined_without_partial_publish(tmp_path: Path) -> None:
    root = tmp_path / "android"
    data = fixture_pack()
    data["sources"][0]["licenseVerified"] = False
    git_source(root, data)

    pack = scan_source(root).packs[0]
    assert pack.lessons == ()
    assert pack.examples == ()
    assert pack.blocked_count == 5


def test_source_schema_and_foreign_keys_fail_closed(tmp_path: Path) -> None:
    root = tmp_path / "android"
    data = fixture_pack()
    data["lessons"][0]["vocabulary"][0]["examples"] = ["missing"]
    git_source(root, data)
    with pytest.raises(SourceValidationError, match="Example FK"):
        scan_source(root)


def test_hash_uses_canonical_unicode_json() -> None:
    assert canonical_hash({"日本": "学ぶ", "reading": "まなぶ"}) == canonical_hash(
        {"reading": "まなぶ", "日本": "学ぶ"}
    )
    assert canonical_hash({"漢字": "学"}) != canonical_hash({"漢字": "校"})


def test_first_import_no_change_update_archive_and_web_data_preservation(
    tmp_path: Path,
    db_session: Session,
    test_settings: Settings,
) -> None:
    root = tmp_path / "android"
    path = git_source(root, fixture_pack())
    first = scan_source(root)
    original_sha = first.commit_sha
    exam = Exam(title="User Web exam", category="grammar", level="N3")
    db_session.add(exam)
    run1 = create_run(db_session)
    counts1 = apply_snapshot(db_session, run1.id, first, test_settings)
    db_session.commit()

    assert counts1["new_vocabulary"] == 1
    assert counts1["new_kanji"] == 1
    assert counts1["new_grammar"] == 1
    assert counts1["new_lessons"] == 1
    assert db_session.query(Exam).filter_by(title="User Web exam").count() == 1
    assert db_session.query(LearningContentChange).filter_by(run_id=run1.id).count() >= 7
    assert db_session.query(LearningContentPack).one().source_commit_sha == original_sha
    assert db_session.scalar(select(LearningItem.source_version).limit(1)) == 1

    unchanged = scan_source(root)
    run2 = create_run(db_session)
    counts2 = apply_snapshot(db_session, run2.id, unchanged, test_settings)
    db_session.commit()
    assert run2.status == "no_changes"
    assert counts2.get("new_vocabulary", 0) == 0
    assert db_session.scalar(select(func.count()).select_from(LearningItem)) == 3

    updated = fixture_pack(version=2)
    updated_lesson = updated["lessons"][0]
    updated_lesson["title"] = "Bài học đã cập nhật"
    updated_lesson["vocabulary"][0]["meaningVi"] = "học tập, nghiên cứu"
    updated_lesson["vocabulary"].append(
        {
            "id": "word-2",
            "expression": "学校",
            "reading": "がっこう",
            "furigana": "{学校|がっこう}",
            "meaningVi": "trường học",
            "examples": [],
        }
    )
    updated_lesson["kanji"] = []
    path.write_text(json.dumps(updated, ensure_ascii=False, indent=2), encoding="utf-8")
    subprocess.run(["git", "-C", str(root), "add", str(path.relative_to(root))], check=True)
    subprocess.run(["git", "-C", str(root), "commit", "-qm", "fixture pack v2"], check=True)
    changed_snapshot = scan_source(root)
    run3 = create_run(db_session)
    counts3 = apply_snapshot(db_session, run3.id, changed_snapshot, test_settings)
    db_session.commit()

    assert counts3["changed_vocabulary"] == 1
    assert counts3["new_vocabulary"] == 1
    assert counts3["archived_kanji"] == 1
    assert counts3["changed_lessons"] == 1
    archived = db_session.scalar(select(LearningItem).where(LearningItem.item_type == "kanji"))
    assert archived is not None and archived.is_archived is True
    assert db_session.scalar(select(func.count()).select_from(Exam)) == 1


def test_invalid_apply_rolls_back_all_rows_and_keeps_previous_content(
    tmp_path: Path,
    db_session: Session,
    test_settings: Settings,
) -> None:
    root = tmp_path / "android"
    path = git_source(root, fixture_pack())
    snapshot = scan_source(root)
    run1 = create_run(db_session)
    apply_snapshot(db_session, run1.id, snapshot, test_settings)
    db_session.commit()
    old_hash = db_session.scalar(select(LearningContentPack.source_hash))

    safe_record = snapshot.packs[0].lessons[0].content_items[0]
    bad_record = replace(safe_record, example_refs=("does-not-exist",))
    old_lesson = snapshot.packs[0].lessons[0]
    bad_lesson = replace(old_lesson, content_items=(bad_record,))
    bad_pack = replace(snapshot.packs[0], lessons=(bad_lesson,), source_hash="f" * 64)
    bad_snapshot = replace(snapshot, packs=(bad_pack,))
    path.write_text("unchanged fixture source", encoding="utf-8")
    run2 = create_run(db_session)
    with pytest.raises(SourceValidationError, match="missing/blocked example"):
        apply_snapshot(db_session, run2.id, bad_snapshot, test_settings)
    db_session.rollback()

    assert db_session.scalar(select(LearningContentPack.source_hash)) == old_hash
    assert db_session.scalar(select(func.count()).select_from(LearningItem)) == 3
    existing = db_session.scalar(select(LearningItem).where(LearningItem.item_type == "kanji"))
    assert existing is not None and existing.is_archived is False


def test_web_learning_api_returns_verified_content_and_examples(
    client: TestClient,
    tmp_path: Path,
    db_session: Session,
    test_settings: Settings,
) -> None:
    root = tmp_path / "android"
    git_source(root, fixture_pack())
    snapshot = scan_source(root)

    # API sync is queued; apply the validated fixture through the same service as the worker.
    run = create_run(db_session)
    apply_snapshot(db_session, run.id, snapshot, test_settings)
    db_session.commit()

    response = client.get("/api/v1/learning-content/items", params={"type": "vocabulary"})
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["total"] == 1
    assert data["items"][0]["payload"]["expression"] == "勉強"
    assert data["items"][0]["examples"][0]["translationVi"] == "Học ở Nhật."


def test_manual_sync_queues_work_and_requires_configured_secret(
    client: TestClient,
    test_settings: Settings,
) -> None:
    status_response = client.get("/api/v1/learning-content/sync/status")
    assert status_response.status_code == 200
    assert status_response.json()["data"]["source_available"] is True

    secret = "a" * 48
    secured = test_settings.model_copy(
        update={"learning_content_sync_token": SecretStr(secret), "app_env": "production"}
    )
    from app.core.config import get_settings

    cast(FastAPI, client.app).dependency_overrides[get_settings] = lambda: secured
    rejected = client.post("/api/v1/learning-content/sync")
    assert rejected.status_code == 401
    queued = client.post(
        "/api/v1/learning-content/sync",
        headers={"X-Learning-Sync-Token": secret},
    )
    assert queued.status_code == 202
    assert queued.json()["data"]["status"] == "queued"


def test_manual_queue_is_idempotent_under_concurrent_requests(db_session: Session) -> None:
    factory = sessionmaker(bind=db_session.get_bind(), expire_on_commit=False, autoflush=False)
    gate = Barrier(2)
    ids: list[str] = []

    def queue() -> None:
        with factory() as session:
            gate.wait(timeout=5)
            run = enqueue_sync(session, "manual")
            ids.append(str(run.id))

    first = Thread(target=queue)
    second = Thread(target=queue)
    first.start()
    second.start()
    first.join(timeout=10)
    second.join(timeout=10)
    assert not first.is_alive() and not second.is_alive()
    assert len(ids) == 2 and ids[0] == ids[1]
    assert (
        db_session.scalar(
            select(func.count())
            .select_from(LearningSyncRun)
            .where(LearningSyncRun.status == "queued")
        )
        == 1
    )


def test_worker_restart_recovers_stale_run_with_bounded_attempts(db_session: Session) -> None:
    now = datetime.now(UTC)
    retryable = LearningSyncRun(
        status="running", trigger="interval", attempts=1, started_at=now - timedelta(hours=1)
    )
    exhausted = LearningSyncRun(
        status="running", trigger="startup", attempts=3, started_at=now - timedelta(hours=1)
    )
    db_session.add_all([retryable, exhausted])
    db_session.flush()

    recover_stale_runs(db_session, max_run_seconds=300, now=now)
    db_session.expire_all()
    assert retryable.status == "queued"
    assert retryable.error == "Worker restarted before the previous run completed"
    assert exhausted.status == "failed"
    assert exhausted.finished_at == now


def test_web_progress_and_existing_user_data_are_not_part_of_content_upsert(
    tmp_path: Path,
    db_session: Session,
    test_settings: Settings,
) -> None:
    root = tmp_path / "android"
    git_source(root, fixture_pack())
    snapshot = scan_source(root)
    db_session.execute(
        text(
            "INSERT INTO knowledge_items (knowledge_type,jlpt_level,title,content,canonical_key) VALUES ('grammar','N3','〜ので','vì','web:manual')"
        )
    )
    db_session.execute(
        text(
            "INSERT INTO review_items (review_type,dedup_key,knowledge_id,srs_state,step_index,interval_minutes,review_count,lapse_count,algorithm_version,ladder,version) SELECT 'knowledge_recall','k:'||id,id,'learning',1,1440,7,2,'ladder-v1','20m,1h,1d',4 FROM knowledge_items WHERE canonical_key='web:manual'"
        )
    )
    db_session.commit()
    run = create_run(db_session)
    apply_snapshot(db_session, run.id, snapshot, test_settings)
    db_session.commit()
    progress = db_session.execute(
        text("SELECT interval_minutes,review_count,lapse_count,version FROM review_items")
    ).one()
    assert tuple(progress) == (1440, 7, 2, 4)
