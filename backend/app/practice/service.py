"""Practice generation workflow. Output is always ``needs_review``; only the user approves."""

import json
import re
import uuid
from collections.abc import Callable
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.errors import ConflictError, DomainValidationError, NotFoundError
from app.core.time import utcnow
from app.database.enums import ExplanationOrigin, PracticeGenerationStatus, PracticeStatus
from app.explanations import prompts, usage
from app.explanations.interfaces import BadOutputError, ProviderError
from app.explanations.providers import registry
from app.explanations.service import AIUnavailableError, ExplanationInvalidError, provider_failure
from app.practice import context as pctx
from app.practice.generator import PracticeGenerator, PracticeResult, get_practice_generator
from app.practice.models import GeneratedPracticeQuestion, PracticeGeneration
from app.practice.payload import PracticeSet
from app.practice.schemas import (
    ExportResult,
    GenerationRead,
    ManualImportResult,
    PracticeQuestionRead,
    PreviewQuestion,
)
from app.practice.validation import SetReport, validate_set

_FENCE = re.compile(r"^\s*```(?:json)?\s*(.*?)\s*```\s*$", re.DOTALL)


def _save(
    db: Session,
    ctx: pctx.PracticeContext,
    report: SetReport,
    *,
    origin: ExplanationOrigin,
    provider: str,
    model: str,
    usage_info: dict[str, Any] | None,
) -> PracticeGeneration:
    accepted = report.accepted
    status = (
        PracticeGenerationStatus.FAILED
        if not accepted
        else PracticeGenerationStatus.COMPLETED
        if len(accepted) == len(report.questions)
        else PracticeGenerationStatus.PARTIAL
    )
    issues = report.set_errors + [
        {"index": q.index, **e} for q in report.questions for e in q.errors
    ]
    gen = PracticeGeneration(
        knowledge_id=ctx.knowledge_id,
        origin=origin.value,
        provider=provider,
        model=model,
        prompt_version=prompts.PRACTICE_VERSION,
        requested_count=ctx.count,
        accepted_count=len(accepted),
        status=status.value,
        issues=issues,
        usage=usage_info,
    )
    db.add(gen)
    db.flush()
    for q in accepted:
        assert q.question is not None and q.fingerprint is not None
        db.add(
            GeneratedPracticeQuestion(
                generation_id=gen.id,
                knowledge_id=ctx.knowledge_id,
                source_explanation_id=ctx.source_explanation_id,
                status=PracticeStatus.NEEDS_REVIEW.value,
                question_type=q.question.question_type,
                question_text=q.question.question_text,
                options=list(q.question.options),
                answer_index=q.question.answer_index,
                payload=q.question.model_dump(),
                fingerprint=q.fingerprint,
                validation_issues=q.warnings,
            )
        )
    db.commit()
    return gen


def generation_read(db: Session, gen: PracticeGeneration) -> GenerationRead:
    questions = db.scalars(
        select(GeneratedPracticeQuestion)
        .where(GeneratedPracticeQuestion.generation_id == gen.id)
        .order_by(GeneratedPracticeQuestion.created_at)
    )
    return GenerationRead(
        id=gen.id,
        knowledge_id=gen.knowledge_id,
        origin=ExplanationOrigin(gen.origin),
        provider=gen.provider,
        model=gen.model,
        prompt_version=gen.prompt_version,
        requested_count=gen.requested_count,
        accepted_count=gen.accepted_count,
        status=PracticeGenerationStatus(gen.status),
        issues=gen.issues,
        usage=gen.usage,
        created_at=gen.created_at,
        questions=[PracticeQuestionRead.model_validate(q) for q in questions],
    )


def _bind(
    generator: PracticeGenerator, ctx: pctx.PracticeContext, feedback: list[str] | None
) -> Callable[[], PracticeResult]:
    return lambda: generator.generate(ctx, feedback=feedback)


def generate(
    db: Session, settings: Settings, knowledge_id: uuid.UUID, count: int, question_type: str | None
) -> GenerationRead:
    ctx = pctx.build(db, knowledge_id, count, question_type)
    generator = get_practice_generator(settings)
    if generator is None:
        raise AIUnavailableError(
            registry.status(settings).reason or "AI chưa được cấu hình.",
            details={"fallback": "manual"},
        )
    feedback: list[str] | None = None
    last: SetReport | None = None
    result: PracticeResult | None = None
    for _ in range(settings.ai_max_format_retries + 1):
        try:
            result = usage.guarded_call(
                db,
                settings,
                provider=generator.provider,
                model=generator.model,
                question_id=None,
                fn=_bind(generator, ctx, feedback),
            )
        except BadOutputError as exc:
            feedback = [f"Kết quả không đúng JSON schema ({exc.detail})."]
            continue
        except ProviderError as exc:
            raise provider_failure(exc) from exc
        last = validate_set(result.payload, ctx)
        if last.accepted:
            break
        feedback = last.error_messages()[:10]
    if last is None or result is None or not last.accepted:
        raise ExplanationInvalidError(
            "AI không tạo được câu luyện hợp lệ sau khi thử lại; không có gì được lưu.",
            details={"errors": (last.error_messages() if last else feedback) or []},
        )
    cost = usage.estimate_cost(settings, result.usage)
    gen = _save(
        db,
        ctx,
        last,
        origin=ExplanationOrigin.API,
        provider=generator.provider,
        model=result.model,
        usage_info={
            "input_tokens": result.usage.input_tokens,
            "output_tokens": result.usage.output_tokens,
            "cost_usd": float(cost) if cost is not None else None,
        },
    )
    return generation_read(db, gen)


def export_prompt(
    db: Session, knowledge_id: uuid.UUID, count: int, question_type: str | None
) -> ExportResult:
    ctx = pctx.build(db, knowledge_id, count, question_type)
    return ExportResult(
        prompt=prompts.render_practice_manual(ctx),
        prompt_version=prompts.PRACTICE_VERSION,
        json_schema=PracticeSet.model_json_schema(),
    )


def manual_import(
    db: Session,
    knowledge_id: uuid.UUID,
    count: int,
    raw_json: str,
    *,
    save: bool,
    model_label: str | None,
) -> ManualImportResult:
    ctx = pctx.build(db, knowledge_id, count, None)
    match = _FENCE.match(raw_json)
    try:
        data = json.loads(match.group(1) if match else raw_json)
    except json.JSONDecodeError as exc:
        raise DomainValidationError(
            f"JSON không hợp lệ ở dòng {exc.lineno}, cột {exc.colno}: {exc.msg}."
        ) from exc
    if not isinstance(data, dict):
        raise DomainValidationError("JSON phải là một object.")
    report = validate_set(data, ctx)
    preview = [
        PreviewQuestion(
            index=q.index,
            ok=q.ok and not report.set_errors,
            errors=q.errors,
            warnings=q.warnings,
            question=q.question.model_dump() if q.question else None,
        )
        for q in report.questions
    ]
    generation = None
    if save:
        if not report.accepted:
            raise DomainValidationError(
                "Không có câu hợp lệ để lưu.", details={"errors": report.error_messages()}
            )
        gen = _save(
            db,
            ctx,
            report,
            origin=ExplanationOrigin.MANUAL,
            provider="manual",
            model=model_label or "chatgpt-manual",
            usage_info=None,
        )
        generation = generation_read(db, gen)
    return ManualImportResult(
        saved=save, set_errors=report.set_errors, questions=preview, generation=generation
    )


def get_generation(db: Session, generation_id: uuid.UUID) -> GenerationRead:
    gen = db.get(PracticeGeneration, generation_id)
    if gen is None:
        raise NotFoundError("Không tìm thấy lần tạo câu luyện.")
    return generation_read(db, gen)


def list_questions(
    db: Session, knowledge_id: uuid.UUID | None, status: PracticeStatus | None
) -> list[PracticeQuestionRead]:
    stmt = select(GeneratedPracticeQuestion)
    if knowledge_id:
        stmt = stmt.where(GeneratedPracticeQuestion.knowledge_id == knowledge_id)
    if status:
        stmt = stmt.where(GeneratedPracticeQuestion.status == status.value)
    return [
        PracticeQuestionRead.model_validate(q)
        for q in db.scalars(stmt.order_by(GeneratedPracticeQuestion.created_at.desc()))
    ]


def review(
    db: Session, question_id: uuid.UUID, target: PracticeStatus, note: str | None
) -> PracticeQuestionRead:
    q = db.scalar(
        select(GeneratedPracticeQuestion)
        .where(GeneratedPracticeQuestion.id == question_id)
        .with_for_update()
    )
    if q is None:
        raise NotFoundError("Không tìm thấy câu luyện.")
    if target == PracticeStatus.APPROVED and q.status == PracticeStatus.REJECTED:
        raise ConflictError("Câu đã bị từ chối; hãy tạo câu mới.")
    q.status = target.value
    q.reviewed_at = utcnow()
    q.review_note = note
    db.commit()
    return PracticeQuestionRead.model_validate(q)
