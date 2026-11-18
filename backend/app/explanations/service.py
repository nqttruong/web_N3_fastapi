"""Explanation business logic: generate (with cache + lock), versions, review, manual mode.

The verified answer in ``questions`` is read here but never written: an explanation that
disagrees with it is rejected by validation, and a model's doubt about it is only flagged.
"""

import hashlib
import json
import logging
import re
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Literal

from fastapi import status
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.attempts.models import AttemptAnswer, ExamAttempt
from app.core.config import Settings
from app.core.errors import AppError, ConflictError, DomainValidationError, NotFoundError
from app.core.time import utcnow
from app.database.enums import ExplanationOrigin, VerificationStatus
from app.exams.models import Question
from app.explanations import prompts, usage
from app.explanations.context import (
    Ineligible,
    QuestionContext,
    build_context,
    check_eligibility,
    current_content_hash,
    load_question,
    selected_answer_for,
)
from app.explanations.interfaces import (
    BadOutputError,
    ExplanationGenerator,
    GenerationResult,
    ProviderError,
)
from app.explanations.models import AIExplanation
from app.explanations.payload import (
    SCHEMA_VERSION,
    ExplanationPayload,
    learner_error_view,
    output_json_schema,
)
from app.explanations.providers import registry
from app.explanations.schemas import (
    Capabilities,
    ExplanationRead,
    ExportPromptResult,
    FindingRead,
    GenerateResult,
    ManualImportItem,
    ManualImportResult,
    QuestionExplanations,
    SkippedQuestion,
)
from app.explanations.validation import ValidationReport, validate

logger = logging.getLogger(__name__)
ACTIVE_STATUSES = (
    VerificationStatus.GENERATED.value,
    VerificationStatus.NEEDS_REVIEW.value,
    VerificationStatus.APPROVED.value,
)


# ------------------------------------------------------------------ errors
class IneligibleError(DomainValidationError):
    code = "question_not_eligible"


class AIUnavailableError(AppError):
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    code = "ai_unavailable"


class AIProviderFailureError(AppError):
    status_code = status.HTTP_502_BAD_GATEWAY
    code = "ai_provider_error"


class ExplanationInvalidError(AppError):
    status_code = status.HTTP_502_BAD_GATEWAY
    code = "ai_output_invalid"


class GenerationInProgressError(ConflictError):
    code = "generation_in_progress"


def provider_failure(exc: ProviderError) -> AIProviderFailureError:
    err = AIProviderFailureError(exc.user_message, details={"provider_code": exc.code})
    if exc.code == "provider_rate_limited":
        err.status_code = status.HTTP_429_TOO_MANY_REQUESTS
    return err


# ------------------------------------------------------------------ capabilities
def capabilities(db: Session, settings: Settings) -> Capabilities:
    st = registry.status(settings)
    spent = usage.spending(db)
    return Capabilities(
        api_available=st.available,
        provider=st.provider,
        model=st.model,
        reason=st.reason,
        prompt_version=prompts.CURRENT_VERSION,
        schema_version=SCHEMA_VERSION,
        max_concurrent_requests=settings.ai_max_concurrent_requests,
        batch_max_questions=settings.ai_batch_max_questions,
        budget={
            "max_requests_per_day": settings.ai_max_requests_per_day,
            "requests_today": spent.requests_today,
            "monthly_budget_usd": settings.ai_monthly_budget_usd or None,
            "month_cost_usd": spent.month_cost_usd
            if settings.ai_price_input_per_1m_tokens is not None
            else None,
            "month_input_tokens": spent.month_input_tokens,
            "month_output_tokens": spent.month_output_tokens,
            "prices_configured": settings.ai_price_input_per_1m_tokens is not None
            and settings.ai_price_output_per_1m_tokens is not None,
        },
    )


# ------------------------------------------------------------------ reading
def cache_key(content_hash: str, provider: str, model: str, prompt_version: str) -> str:
    raw = "|".join([content_hash, provider, model, prompt_version, SCHEMA_VERSION])
    return hashlib.sha256(raw.encode()).hexdigest()


def find_current(db: Session, question_id: uuid.UUID, content_hash: str) -> AIExplanation | None:
    """Newest non-rejected explanation built on the current question content (approved first)."""
    rows = db.scalars(
        select(AIExplanation)
        .where(
            AIExplanation.question_id == question_id,
            AIExplanation.content_hash == content_hash,
            AIExplanation.verification_status.in_(ACTIVE_STATUSES),
        )
        .order_by(AIExplanation.created_at.desc())
    ).all()
    approved = [r for r in rows if r.verification_status == VerificationStatus.APPROVED]
    if approved:
        return approved[0]
    return rows[0] if rows else None


def to_read(
    explanation: AIExplanation,
    *,
    current_hash: str,
    current_id: uuid.UUID | None,
    selected_answer: int | None = None,
) -> ExplanationRead:
    try:
        payload: ExplanationPayload | None = ExplanationPayload.model_validate(
            explanation.explanation_json
        )
    except ValueError:
        payload = None  # legacy rows from before PR3
    learner = (
        learner_error_view(payload, selected_answer - 1)
        if payload is not None and selected_answer is not None
        else None
    )
    return ExplanationRead(
        id=explanation.id,
        question_id=explanation.question_id,
        provider=explanation.provider,
        model=explanation.model,
        origin=ExplanationOrigin(explanation.origin),
        status=VerificationStatus(explanation.verification_status),
        stale=explanation.content_hash != current_hash,
        is_current=explanation.id == current_id,
        prompt_version=explanation.prompt_version,
        schema_version=explanation.schema_version,
        verified_answer_snapshot=explanation.verified_answer_snapshot,
        flagged_answer_concern=explanation.flagged_answer_concern,
        validation_issues=[FindingRead.model_validate(i) for i in explanation.validation_issues],
        payload=payload,
        learner_error_analysis=learner,
        usage=explanation.usage,
        review_note=explanation.review_note,
        reviewed_at=explanation.reviewed_at,
        created_at=explanation.created_at,
        updated_at=explanation.updated_at,
    )


def read_one(
    db: Session, explanation: AIExplanation, selected_answer: int | None = None
) -> ExplanationRead:
    question = db.get(Question, explanation.question_id)
    assert question is not None
    current_hash = current_content_hash(db, question)
    current = find_current(db, question.id, current_hash)
    return to_read(
        explanation,
        current_hash=current_hash,
        current_id=current.id if current else None,
        selected_answer=selected_answer,
    )


def question_explanations(
    db: Session, question_id: uuid.UUID, attempt_answer_id: uuid.UUID | None = None
) -> QuestionExplanations:
    question, passage, _ = load_question(db, question_id)
    selected = selected_answer_for(db, question_id, attempt_answer_id)
    current_hash = current_content_hash(db, question)
    current = find_current(db, question_id, current_hash)
    rows = db.scalars(
        select(AIExplanation)
        .where(AIExplanation.question_id == question_id)
        .order_by(AIExplanation.created_at.desc())
    ).all()
    problem = check_eligibility(question, passage)
    return QuestionExplanations(
        question_id=question_id,
        current_id=current.id if current else None,
        eligible=problem is None,
        ineligible_code=problem.code if problem else None,
        ineligible_message=problem.message if problem else None,
        versions=[
            to_read(
                r,
                current_hash=current_hash,
                current_id=current.id if current else None,
                selected_answer=selected,
            )
            for r in rows
        ],
    )


def get_explanation(
    db: Session, explanation_id: uuid.UUID, attempt_answer_id: uuid.UUID | None = None
) -> ExplanationRead:
    explanation = db.get(AIExplanation, explanation_id)
    if explanation is None:
        raise NotFoundError(
            "Không tìm thấy lời giải.", details={"explanation_id": str(explanation_id)}
        )
    selected = selected_answer_for(db, explanation.question_id, attempt_answer_id)
    return read_one(db, explanation, selected)


# ------------------------------------------------------------------ generation
@contextmanager
def generation_lock(db: Session, key: str) -> Iterator[None]:
    """Session-level advisory lock on a dedicated connection, held during the provider call."""
    lock_id = int.from_bytes(hashlib.sha256(key.encode()).digest()[:8], "big", signed=True)
    with db.get_bind().connect() as conn:  # type: ignore[union-attr]
        acquired = conn.execute(text("SELECT pg_try_advisory_lock(:k)"), {"k": lock_id}).scalar()
        if not acquired:
            raise GenerationInProgressError("Lời giải cho câu này đang được tạo. Hãy chờ giây lát.")
        try:
            yield
        finally:
            conn.execute(text("SELECT pg_advisory_unlock(:k)"), {"k": lock_id})
            conn.commit()


def _call_provider(
    db: Session,
    settings: Settings,
    generator: ExplanationGenerator,
    ctx: QuestionContext,
    feedback: list[str] | None,
) -> GenerationResult:
    try:
        return usage.guarded_call(
            db, settings, provider=generator.provider, model=generator.model,
            question_id=ctx.question_id, fn=lambda: generator.generate(ctx, feedback=feedback),
        )  # fmt: skip
    except ProviderError as exc:
        logger.warning("AI call failed for question %s: %s", ctx.question_id, exc.code)
        raise


def generate_validated(
    db: Session, settings: Settings, generator: ExplanationGenerator, ctx: QuestionContext
) -> tuple[GenerationResult, ValidationReport]:
    """Provider call + two-layer validation, with a bounded number of format retries."""
    feedback: list[str] | None = None
    last_errors: list[dict[str, str]] = []
    for _ in range(settings.ai_max_format_retries + 1):
        try:
            result = _call_provider(db, settings, generator, ctx, feedback)
        except BadOutputError as exc:
            message = f"Kết quả không đúng JSON schema ({exc.detail})."
            last_errors = [{"code": "bad_output", "message": message}]
            feedback = [message]
            continue
        report = validate(result.payload, ctx)
        if report.ok:
            return result, report
        last_errors = [{"code": f.code, "message": f.message} for f in report.errors]
        feedback = report.error_messages()
    raise ExplanationInvalidError(
        "AI trả lời không hợp lệ sau khi thử lại; lời giải không được lưu.",
        details={"errors": last_errors},
    )


def save_explanation(
    db: Session,
    ctx: QuestionContext,
    payload: ExplanationPayload,
    report: ValidationReport,
    *,
    provider: str,
    model: str,
    origin: ExplanationOrigin,
    usage_info: dict[str, Any] | None = None,
) -> AIExplanation:
    explanation = AIExplanation(
        question_id=ctx.question_id,
        provider=provider,
        model=model,
        explanation_json=payload.model_dump(mode="json"),
        verification_status=report.status(manual=origin == ExplanationOrigin.MANUAL).value,
        origin=origin.value,
        prompt_version=prompts.CURRENT_VERSION,
        schema_version=SCHEMA_VERSION,
        content_hash=ctx.content_hash,
        cache_key=cache_key(ctx.content_hash, provider, model, prompts.CURRENT_VERSION),
        verified_answer_snapshot=ctx.verified_answer,
        validation_issues=[f.as_dict() for f in report.findings],
        flagged_answer_concern=bool(payload.quality.source_answer_concern),
        usage=usage_info,
    )
    db.add(explanation)
    db.flush()
    return explanation


@dataclass
class Outcome:
    kind: Literal["cached", "generated"]
    explanation: AIExplanation
    selected_answer: int | None


def generate_for_question(
    db: Session,
    settings: Settings,
    question_id: uuid.UUID,
    *,
    force: bool = False,
    attempt_answer_id: uuid.UUID | None = None,
) -> Outcome:
    ctx = build_context(db, question_id, attempt_answer_id)
    if isinstance(ctx, Ineligible):
        raise IneligibleError(ctx.message, details={"reason": ctx.code})
    if not force:
        cached = find_current(db, question_id, ctx.content_hash)
        if cached is not None:
            return Outcome("cached", cached, ctx.selected_answer)
    generator = registry.get_generator(settings)
    if generator is None:
        reason = registry.status(settings).reason or "AI chưa được cấu hình."
        raise AIUnavailableError(reason, details={"fallback": "manual"})

    key = cache_key(ctx.content_hash, generator.provider, generator.model, prompts.CURRENT_VERSION)
    with generation_lock(db, key):
        if not force:
            cached = find_current(db, question_id, ctx.content_hash)
            if cached is not None:
                return Outcome("cached", cached, ctx.selected_answer)
        try:
            result, report = generate_validated(db, settings, generator, ctx)
        except ProviderError as exc:
            raise provider_failure(exc) from exc
        cost = usage.estimate_cost(settings, result.usage)
        explanation = save_explanation(
            db, ctx, result.payload, report,
            provider=generator.provider, model=result.model, origin=ExplanationOrigin.API,
            usage_info={
                "input_tokens": result.usage.input_tokens,
                "output_tokens": result.usage.output_tokens,
                "cost_usd": float(cost) if cost is not None else None,
            },
        )  # fmt: skip
        db.commit()
    return Outcome("generated", explanation, ctx.selected_answer)


def generate_result(db: Session, outcome: Outcome) -> GenerateResult:
    return GenerateResult(
        outcome=outcome.kind,
        explanation=read_one(db, outcome.explanation, outcome.selected_answer),
    )


# ------------------------------------------------------------------ review
def _review(
    db: Session, explanation_id: uuid.UUID, target: VerificationStatus, note: str | None
) -> ExplanationRead:
    explanation = db.scalar(
        select(AIExplanation).where(AIExplanation.id == explanation_id).with_for_update()
    )
    if explanation is None:
        raise NotFoundError("Không tìm thấy lời giải.")
    question = db.get(Question, explanation.question_id)
    assert question is not None
    if target == VerificationStatus.APPROVED:
        if explanation.content_hash != current_content_hash(db, question):
            raise ConflictError(
                "Lời giải đã cũ (câu hỏi hoặc đáp án đã thay đổi); hãy tạo lời giải mới.",
                details={"code": "stale"},
            )
        if explanation.verification_status == VerificationStatus.REJECTED:
            raise ConflictError("Lời giải đã bị đánh dấu chưa chính xác; hãy tạo lời giải mới.")
    explanation.verification_status = target.value
    explanation.reviewed_at = utcnow()
    explanation.review_note = note
    db.commit()
    return read_one(db, explanation)


def approve(db: Session, explanation_id: uuid.UUID, note: str | None) -> ExplanationRead:
    return _review(db, explanation_id, VerificationStatus.APPROVED, note)


def reject(db: Session, explanation_id: uuid.UUID, note: str | None) -> ExplanationRead:
    return _review(db, explanation_id, VerificationStatus.REJECTED, note)


# ------------------------------------------------------------------ manual mode
def export_prompt(
    db: Session, question_ids: list[uuid.UUID], attempt_id: uuid.UUID | None = None
) -> ExportPromptResult:
    contexts: list[QuestionContext] = []
    skipped: list[SkippedQuestion] = []
    answers_by_question = (
        {question.id: answer for answer, question in attempt_answers(db, attempt_id)}
        if attempt_id
        else {}
    )
    for qid in dict.fromkeys(question_ids):
        answer = answers_by_question.get(qid)
        if attempt_id and answer is None:
            raise DomainValidationError(
                "Một số câu không thuộc bài làm này.", details={"question_id": str(qid)}
            )
        ctx = build_context(db, qid, answer.id if answer else None)  # 404 for unknown ids
        if isinstance(ctx, Ineligible):
            skipped.append(SkippedQuestion(question_id=qid, code=ctx.code, message=ctx.message))
        else:
            contexts.append(ctx)
    if not contexts:
        raise IneligibleError(
            "Không có câu nào đủ điều kiện để xuất prompt.",
            details={"skipped": [s.model_dump(mode="json") for s in skipped]},
        )
    return ExportPromptResult(
        prompt=prompts.render_manual(contexts),
        prompt_version=prompts.CURRENT_VERSION,
        schema_version=SCHEMA_VERSION,
        question_ids=[c.question_id for c in contexts],
        skipped=skipped,
        json_schema=output_json_schema(),
    )


_FENCE = re.compile(r"^\s*```(?:json)?\s*(.*?)\s*```\s*$", re.DOTALL)


def _parse_manual_json(raw: str) -> list[Any]:
    match = _FENCE.match(raw)
    body = match.group(1) if match else raw  # tolerate a ```json fence; nothing else is altered
    try:
        data = json.loads(body)
    except json.JSONDecodeError as exc:
        raise DomainValidationError(
            f"JSON không hợp lệ ở dòng {exc.lineno}, cột {exc.colno}: {exc.msg}.",
            details={"line": exc.lineno, "column": exc.colno},
        ) from exc
    if isinstance(data, dict) and isinstance(data.get("explanations"), list):
        return list(data["explanations"])
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        return [data]
    raise DomainValidationError('JSON phải là object có khoá "explanations" (danh sách).')


def manual_import(
    db: Session,
    question_ids: list[uuid.UUID],
    raw_json: str,
    *,
    save: bool,
    model_label: str | None,
) -> ManualImportResult:
    allowed = {str(q) for q in question_ids}
    items_raw = _parse_manual_json(raw_json)
    if len(items_raw) > len(allowed):
        raise DomainValidationError("JSON có nhiều lời giải hơn số câu đã chọn.")
    seen: set[str] = set()
    results: list[ManualImportItem] = []
    contexts: dict[int, tuple[QuestionContext, ValidationReport]] = {}

    for index, item in enumerate(items_raw):
        qid = item.get("question_id") if isinstance(item, dict) else None
        qid = qid if isinstance(qid, str) else None

        def fail(code: str, message: str, qid: str | None = qid, index: int = index) -> None:
            results.append(
                ManualImportItem(
                    index=index, question_id=qid, ok=False, status=None, payload=None,
                    findings=[FindingRead(severity="error", code=code, message=message)],
                )
            )  # fmt: skip

        if qid is None:
            fail("missing_question_id", "Lời giải không có question_id.")
            continue
        if qid not in allowed:
            fail(
                "question_not_selected", "question_id không thuộc các câu đã chọn khi xuất prompt."
            )
            continue
        if qid in seen:
            fail("duplicate_question", "Có hai lời giải cho cùng một câu.")
            continue
        seen.add(qid)
        ctx = build_context(db, uuid.UUID(qid))
        if isinstance(ctx, Ineligible):
            fail(ctx.code, ctx.message)
            continue
        report = validate(item, ctx)
        contexts[index] = (ctx, report)
        results.append(
            ManualImportItem(
                index=index,
                question_id=qid,
                ok=report.ok,
                status=report.status(manual=True) if report.ok else None,
                findings=[FindingRead.model_validate(f.as_dict()) for f in report.findings],
                payload=report.payload,
            )
        )

    if save:
        if not any(r.ok for r in results):
            raise DomainValidationError(
                "Không có lời giải hợp lệ để lưu.",
                details=[r.model_dump(mode="json", exclude={"payload"}) for r in results],
            )
        for r in results:
            if not r.ok:
                continue
            ctx, report = contexts[r.index]
            assert report.payload is not None
            saved = save_explanation(
                db, ctx, report.payload, report,
                provider="manual", model=model_label or "chatgpt-manual",
                origin=ExplanationOrigin.MANUAL,
            )  # fmt: skip
            r.saved_explanation_id = saved.id
        db.commit()
    missing = [q for q in dict.fromkeys(question_ids) if str(q) not in seen]
    return ManualImportResult(saved=save, items=results, missing_question_ids=missing)


# ------------------------------------------------------------------ attempts
def attempt_answers(db: Session, attempt_id: uuid.UUID) -> list[tuple[AttemptAnswer, Question]]:
    if db.get(ExamAttempt, attempt_id) is None:
        raise NotFoundError("Không tìm thấy bài làm.", details={"attempt_id": str(attempt_id)})
    return [
        (a, q)
        for a, q in db.execute(
            select(AttemptAnswer, Question)
            .join(Question, Question.id == AttemptAnswer.question_id)
            .where(AttemptAnswer.attempt_id == attempt_id)
            .order_by(AttemptAnswer.question_number)
        ).all()
    ]
