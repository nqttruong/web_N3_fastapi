from threading import Event, Thread
from uuid import uuid4

from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect, text

from app.exams.fingerprints import question_fingerprint
from app.models import Base
from tests.conftest import _test_url, alembic_config, recreate_database

EXPECTED_TABLES = {
    "exam_sources",
    "exams",
    "passages",
    "questions",
    "exam_attempts",
    "attempt_answers",
    "ai_explanations",
    "knowledge_items",
    "question_knowledge",
    "review_items",
    "review_events",
    "sync_changes",
    "sync_pairing_codes",
    "sync_pairing_attempts",
    "sync_devices",
    "import_drafts",
    "import_assets",
    "explanation_jobs",
    "explanation_job_items",
    "ai_requests",
    "knowledge_relations",
    "knowledge_evidence",
    "review_sessions",
    "practice_generations",
    "generated_practice_questions",
    "learning_content_packs",
    "learning_content_lessons",
    "learning_content_items",
    "learning_content_examples",
    "learning_content_item_examples",
    "learning_content_sync_runs",
    "learning_content_changes",
    "learning_content_sync_queue_lock",
    "learning_source_rights",
    "learning_study_sessions",
    "learning_study_progress",
    "learning_study_events",
    "learning_saved_items",
    "learning_exercise_answers",
    "my_words",
    "my_word_progress",
    "my_word_review_events",
    "my_word_extension_credentials",
    "sync_qr_sessions",
    "sync_qr_audit",
}


def test_single_migration_head() -> None:
    url = _test_url()
    heads = ScriptDirectory.from_config(alembic_config(url)).get_heads()
    assert len(heads) == 1


def test_upgrade_downgrade_roundtrip_and_no_drift() -> None:
    url = _test_url("_migrations")
    recreate_database(url)
    cfg = alembic_config(url)
    engine = create_engine(url)
    try:
        command.upgrade(cfg, "head")
        assert set(inspect(engine).get_table_names()) >= EXPECTED_TABLES

        # Models and migrations must describe the same schema.
        with engine.connect() as conn:
            diff = compare_metadata(MigrationContext.configure(conn), Base.metadata)
        assert diff == [], diff

        command.downgrade(cfg, "base")
        assert set(inspect(engine).get_table_names()) <= {"alembic_version"}

        command.upgrade(cfg, "head")
        assert set(inspect(engine).get_table_names()) >= EXPECTED_TABLES
    finally:
        engine.dispose()


def test_database_is_utf8_and_utc(engine) -> None:  # type: ignore[no-untyped-def]
    with engine.connect() as conn:
        assert conn.execute(text("SHOW server_encoding")).scalar() == "UTF8"
        assert conn.execute(text("SHOW TIME ZONE")).scalar() == "UTC"
        column_types = (
            conn.execute(
                text(
                    "SELECT data_type FROM information_schema.columns "
                    "WHERE table_schema='public' AND column_name IN ('created_at','updated_at') "
                    "GROUP BY data_type"
                )
            )
            .scalars()
            .all()
        )
        assert column_types == ["timestamp with time zone"]


def test_v3_migrations_keep_existing_exams_rights_and_study_sessions() -> None:
    """Upgrade a populated 0011 database through the additive V3 migrations."""
    url = _test_url("_migrations")
    recreate_database(url)
    cfg = alembic_config(url)
    engine = create_engine(url)
    try:
        command.upgrade(cfg, "0011")
        study_id = uuid4()
        with engine.begin() as conn:
            conn.execute(
                text("INSERT INTO exams(title,category,level) VALUES ('既存の試験','grammar','N3')")
            )
            conn.execute(
                text(
                    "INSERT INTO learning_source_rights"
                    "(pack_id,source_id,source_name,rights_holder,rights_basis,allowed_usage)"
                    " VALUES ('pack','source','Existing source','Operator','Private use','Private use')"
                )
            )
            conn.execute(
                text(
                    "INSERT INTO learning_study_sessions(id,mode,item_ids)"
                    " VALUES (:id,'lesson','[]'::jsonb)"
                ),
                {"id": study_id},
            )
        command.upgrade(cfg, "head")
        with engine.connect() as conn:
            assert conn.execute(text("SELECT count(*) FROM exams")).scalar_one() == 1
            assert (
                conn.execute(text("SELECT count(*) FROM learning_study_sessions")).scalar_one() == 1
            )
            assert (
                conn.execute(
                    text(
                        "SELECT source_content_hash FROM learning_source_rights"
                        " WHERE pack_id='pack' AND source_id='source'"
                    )
                ).scalar_one()
                is None
            )
            assert conn.execute(text("SELECT count(*) FROM my_words")).scalar_one() == 0
            assert conn.execute(text("SELECT count(*) FROM sync_qr_sessions")).scalar_one() == 0
    finally:
        engine.dispose()


def test_sync_cursor_allocation_follows_transaction_commit_order() -> None:
    """A later transaction cannot commit a higher cursor while an earlier cursor is uncommitted."""
    url = _test_url("_migrations")
    recreate_database(url)
    cfg = alembic_config(url)
    command.upgrade(cfg, "head")
    engine = create_engine(url)
    started = Event()
    finished = Event()
    second_ids: list[int] = []
    try:
        first = engine.connect()
        first_tx = first.begin()
        first_id = first.execute(
            text(
                "INSERT INTO sync_changes(entity_type,entity_id,operation,version) VALUES ('exam',:id,'insert',1) RETURNING id"
            ),
            {"id": uuid4()},
        ).scalar_one()

        def insert_second() -> None:
            with engine.begin() as connection:
                started.set()
                second_ids.append(
                    connection.execute(
                        text(
                            "INSERT INTO sync_changes(entity_type,entity_id,operation,version) VALUES ('exam',:id,'insert',1) RETURNING id"
                        ),
                        {"id": uuid4()},
                    ).scalar_one()
                )
            finished.set()

        thread = Thread(target=insert_second)
        thread.start()
        assert started.wait(2)
        assert not finished.wait(0.1), "Cursor row lock should hold until first transaction commits"
        first_tx.commit()
        first.close()
        thread.join(timeout=5)
        assert finished.is_set()
        assert second_ids and second_ids[0] > first_id
    finally:
        engine.dispose()


def test_0002_upgrades_existing_data_without_loss() -> None:
    """PR2 migration runs on a PR1 database that already has data (e.g. the seed)."""
    url = _test_url("_migrations")
    recreate_database(url)
    cfg = alembic_config(url)
    engine = create_engine(url)
    try:
        command.upgrade(cfg, "0001")
        with engine.begin() as conn:
            exam_id = conn.execute(
                text(
                    "INSERT INTO exams (title, category, level, status) "
                    "VALUES ('既存の試験', 'grammar', 'N3', 'ready') RETURNING id"
                )
            ).scalar_one()
            conn.execute(
                text(
                    "INSERT INTO questions (exam_id, question_number, question_type, question_text,"
                    " options, correct_answer, answer_status, content_hash) VALUES "
                    "(:e, 1, 'grammar_form', 'ＡＢＣ　です', '[\"ので\", \"のに\"]', 1, 'verified', 'h1'),"
                    "(:e, 2, 'grammar_form', '答えなし', '[\"あ\", \"い\"]', NULL, 'missing', 'h2')"
                ),
                {"e": exam_id},
            )
            conn.execute(
                text(
                    "INSERT INTO exam_attempts (exam_id, started_at, completed_at, total_questions,"
                    " correct_count, incorrect_count, unanswered_count, ungraded_count)"
                    " VALUES (:e, now(), now(), 2, 0, 0, 2, 0)"
                ),
                {"e": exam_id},
            )

        command.upgrade(cfg, "head")
        with engine.connect() as conn:
            rows = conn.execute(
                text(
                    "SELECT question_number, answer_source, fingerprint, question_text "
                    "FROM questions ORDER BY question_number"
                )
            ).all()
            assert [r.answer_source for r in rows] == ["manual", None]
            assert rows[0].question_text == "ＡＢＣ　です"  # text untouched
            assert rows[0].fingerprint == question_fingerprint("ＡＢＣ　です", ["ので", "のに"])
            assert conn.execute(text("SELECT source FROM exam_attempts")).scalar_one() == "practice"

        command.downgrade(cfg, "0001")
        with engine.connect() as conn:
            assert conn.execute(text("SELECT count(*) FROM questions")).scalar_one() == 2
            assert conn.execute(text("SELECT count(*) FROM exam_attempts")).scalar_one() == 1
            assert "import_drafts" not in inspect(engine).get_table_names()
    finally:
        engine.dispose()


def test_0003_keeps_existing_explanations_and_data() -> None:
    """PR3 migration on a database that already has PR1/PR2 data and a pre-PR3 explanation."""
    url = _test_url("_migrations")
    recreate_database(url)
    cfg = alembic_config(url)
    engine = create_engine(url)
    try:
        command.upgrade(cfg, "0002")
        with engine.begin() as conn:
            exam_id = conn.execute(
                text(
                    "INSERT INTO exams (title, category, level) VALUES ('試験', 'grammar', 'N3') RETURNING id"
                )
            ).scalar_one()
            qid = conn.execute(
                text(
                    "INSERT INTO questions (exam_id, question_number, question_type, question_text,"
                    " options, correct_answer, answer_status, answer_source, content_hash, fingerprint)"
                    " VALUES (:e, 1, 'grammar_form', '文', '[\"あ\", \"い\"]', 1, 'verified',"
                    " 'manual', 'h', 'f') RETURNING id"
                ),
                {"e": exam_id},
            ).scalar_one()
            conn.execute(
                text(
                    "INSERT INTO ai_explanations (question_id, provider, model, explanation_json,"
                    " verification_status) VALUES (:q, 'old', 'm', '{}', 'verified'),"
                    " (:q, 'old', 'm', '{}', 'unverified')"
                ),
                {"q": qid},
            )
        command.upgrade(cfg, "head")
        with engine.connect() as conn:
            rows = conn.execute(
                text(
                    "SELECT verification_status, content_hash, origin, reviewed_at IS NOT NULL AS r"
                    " FROM ai_explanations ORDER BY verification_status"
                )
            ).all()
            assert [(r.verification_status, r.content_hash, r.origin, r.r) for r in rows] == [
                ("approved", "legacy", "api", True),
                ("needs_review", "legacy", "api", False),
            ]
            assert conn.execute(text("SELECT count(*) FROM questions")).scalar_one() == 1
        command.downgrade(cfg, "0002")
        with engine.connect() as conn:
            statuses = (
                conn.execute(text("SELECT verification_status FROM ai_explanations"))
                .scalars()
                .all()
            )
            assert sorted(statuses) == ["unverified", "verified"]
            assert "explanation_jobs" not in inspect(engine).get_table_names()
    finally:
        engine.dispose()


def test_0004_keeps_existing_knowledge_and_reviews() -> None:
    """PR4 migration on a database with PR1-PR3 data and schema-only knowledge/review rows."""
    url = _test_url("_migrations")
    recreate_database(url)
    cfg = alembic_config(url)
    engine = create_engine(url)
    try:
        command.upgrade(cfg, "0003")
        with engine.begin() as conn:
            kid = conn.execute(
                text(
                    "INSERT INTO knowledge_items (knowledge_type, jlpt_level, title, content)"
                    " VALUES ('grammar', 'N3', '〜ので', 'vì') RETURNING id"
                )
            ).scalar_one()
            rid = conn.execute(
                text(
                    "INSERT INTO review_items (knowledge_id, due_at) VALUES (:k, now()) RETURNING id"
                ),
                {"k": kid},
            ).scalar_one()
            conn.execute(
                text(
                    "INSERT INTO review_events (review_item_id, rating, reviewed_at) VALUES (:r, 'good', now())"
                ),
                {"r": rid},
            )
        command.upgrade(cfg, "head")
        with engine.connect() as conn:
            k = conn.execute(
                text("SELECT canonical_key, status, details FROM knowledge_items")
            ).one()
            assert (k.canonical_key, k.status, k.details) == (f"legacy:{kid}", "active", {})
            r = conn.execute(
                text("SELECT review_type, dedup_key, srs_state, review_count FROM review_items")
            ).one()
            assert (r.review_type, r.dedup_key, r.srs_state, r.review_count) == (
                "knowledge_recall",
                f"k:{kid}",
                "new",
                0,
            )
            assert conn.execute(text("SELECT count(*) FROM review_events")).scalar_one() == 1
        command.downgrade(cfg, "0003")
        with engine.connect() as conn:
            assert conn.execute(text("SELECT count(*) FROM review_items")).scalar_one() == 1
            assert "knowledge_relations" not in inspect(engine).get_table_names()
    finally:
        engine.dispose()
