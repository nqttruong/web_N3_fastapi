import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.analytics.router import router as analytics_router
from app.attempts.router import router as attempts_router
from app.core.config import API_VERSION, get_settings
from app.core.errors import register_exception_handlers
from app.core.health import router as health_router
from app.exams.router import router as exams_router
from app.explanations.providers import registry
from app.explanations.router import router as explanations_router
from app.imports.router import router as imports_router
from app.knowledge.router import router as knowledge_router
from app.learning_content.dictionary import router as dictionary_router
from app.learning_content.my_words import router as my_words_router
from app.learning_content.router import router as learning_content_router
from app.learning_content.study import router as learning_study_router
from app.practice.router import router as practice_router
from app.reviews.router import router as reviews_router
from app.sync.router import router as sync_router

API_PREFIX = "/api/v1"


def create_app(*, start_worker: bool | None = None) -> FastAPI:
    settings = get_settings()
    logging.basicConfig(level=settings.log_level)
    run_worker = settings.ai_worker_enabled if start_worker is None else start_worker

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        worker = None
        if run_worker and registry.status(settings).available:
            from app.database.session import get_sessionmaker
            from app.explanations.worker import ExplanationWorker

            worker = ExplanationWorker(get_sessionmaker(), settings)
            worker.start()  # recovers items left 'running' by a previous process
        yield
        if worker is not None:
            worker.stop()

    app = FastAPI(
        title=settings.app_name,
        version=API_VERSION,
        description=(
            "Backend for JLPT AI Review: exams, questions and graded attempts. "
            "PR2 adds import drafts (paste text/HTML, screenshots + local OCR) with preview and "
            "explicit answer confirmation. PR3 adds AI explanations (OpenAI Structured Outputs or "
            "manual ChatGPT import) with validation, caching, review and batch jobs."
        ),
        openapi_url=f"{API_PREFIX}/openapi.json",
        docs_url=f"{API_PREFIX}/docs",
        redoc_url=f"{API_PREFIX}/redoc",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=[
            "Content-Type",
            "Authorization",
            "X-Learning-Sync-Token",
            "X-Sync-Admin-Key",
            "X-Pairing-Key",
        ],
    )
    register_exception_handlers(app)

    for router in (
        health_router,
        exams_router,
        attempts_router,
        analytics_router,
        imports_router,
        explanations_router,
        knowledge_router,
        learning_content_router,
        learning_study_router,
        my_words_router,
        dictionary_router,
        reviews_router,
        practice_router,
        sync_router,
    ):
        app.include_router(router, prefix=API_PREFIX)
    return app


app = create_app()
