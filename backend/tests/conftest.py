"""Test fixtures.

Tests run against a real PostgreSQL database (``TEST_DATABASE_URL``) because the schema relies
on PostgreSQL features (JSONB, partial unique indexes, CHECK constraints referencing JSONB,
composite FKs). The database is created if missing and migrated with Alembic once per session.
"""

import logging
from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings, get_settings
from app.core.ratelimit import import_limiter
from app.database.session import build_engine, get_db
from app.explanations.providers.registry import set_generator_for_tests
from app.imports.ocr import set_engine_for_tests
from app.main import create_app
from app.models import Base

logging.getLogger("httpx").setLevel(logging.WARNING)

BACKEND_DIR = Path(__file__).resolve().parents[1]


def _test_url(suffix: str = "") -> str:
    settings = get_settings()
    base = settings.test_database_url
    if not base:
        pytest.exit("TEST_DATABASE_URL is not set (see .env.example)", returncode=2)
    url = make_url(base)
    assert url.database and url.database.endswith("_test"), (
        "Refusing to run tests against a database whose name does not end with '_test'"
    )
    if suffix:
        url = url.set(database=f"{url.database}{suffix}")
    return url.render_as_string(hide_password=False)


def recreate_database(url: str) -> None:
    target = make_url(url)
    admin = create_engine(target.set(database="postgres"), isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        conn.execute(text(f'DROP DATABASE IF EXISTS "{target.database}" WITH (FORCE)'))
        conn.execute(
            text(f"CREATE DATABASE \"{target.database}\" ENCODING 'UTF8' TEMPLATE template0")
        )
    admin.dispose()


def alembic_config(url: str) -> Config:
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    cfg.attributes["database_url"] = url
    cfg.attributes["configure_logger"] = False
    return cfg


@pytest.fixture(scope="session")
def database_url() -> str:
    url = _test_url()
    recreate_database(url)
    command.upgrade(alembic_config(url), "head")
    return url


@pytest.fixture(scope="session")
def engine(database_url: str) -> Iterator[Engine]:
    eng = build_engine(database_url)
    yield eng
    eng.dispose()


@pytest.fixture
def db_session(engine: Engine) -> Iterator[Session]:
    factory = sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)
    session = factory()
    yield session
    session.close()
    # Clean slate for the next test (fast: tables are tiny).
    tables = ", ".join(f'"{t.name}"' for t in reversed(Base.metadata.sorted_tables))
    with engine.begin() as conn:
        conn.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))


@pytest.fixture
def test_settings(tmp_path: Path) -> Settings:
    return get_settings().model_copy(
        update={"import_storage_dir": tmp_path / "imports", "app_env": "test"}
    )


@pytest.fixture(autouse=True)
def _reset_import_state() -> Iterator[None]:
    import_limiter.reset()
    yield
    set_engine_for_tests(None)
    set_generator_for_tests(None)
    import_limiter.reset()


@pytest.fixture
def client(engine: Engine, db_session: Session, test_settings: Settings) -> Iterator[TestClient]:
    factory = sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)

    def _get_db() -> Iterator[Session]:
        session = factory()
        try:
            yield session
        finally:
            session.close()

    app = create_app(start_worker=False)
    app.dependency_overrides[get_db] = _get_db
    app.dependency_overrides[get_settings] = lambda: test_settings
    with TestClient(app, client=("127.0.0.1", 12345)) as test_client:
        yield test_client


# ----------------------------------------------------------------- helpers
@pytest.fixture
def make_exam(client: TestClient):  # type: ignore[no-untyped-def]
    def _make(**overrides: object) -> dict[str, object]:
        payload: dict[str, object] = {"title": "N3 文法 練習 1", "category": "grammar"} | overrides
        response = client.post("/api/v1/exams", json=payload)
        assert response.status_code == 201, response.text
        return response.json()["data"]  # type: ignore[no-any-return]

    return _make


@pytest.fixture
def make_question(client: TestClient):  # type: ignore[no-untyped-def]
    def _make(exam_id: str, number: int = 1, **overrides: object) -> dict[str, object]:
        payload: dict[str, object] = {
            "question_number": number,
            "question_type": "grammar_form",
            "question_text": f"雨が降っている（　　）、試合は中止になった。#{number}",
            "options": ["ので", "のに", "ながら", "ばかりか"],
            "correct_answer": 1,
            "answer_status": "verified",
        } | overrides
        response = client.post(f"/api/v1/exams/{exam_id}/questions", json=payload)
        assert response.status_code == 201, response.text
        return response.json()["data"]  # type: ignore[no-any-return]

    return _make


FIXTURES = Path(__file__).resolve().parent / "fixtures" / "imports"


def fixture_text(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")
