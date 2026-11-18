"""Approved explanation → knowledge candidates (preview only, no writes).

Only the *current, approved, non-stale* explanation of a question is used. Everything else
(generated, needs_review, rejected, stale, no explanation, answer not verified) is skipped
with a reason so the UI can show "chờ duyệt".

Roles (``question_knowledge.relation_type``):
* tests       the item the question checks (matches the verified option / underlined word)
* distractor  appears in a wrong option (→ ``confused_with`` the tested item)
* context     merely appears in the sentence — not selected for review by default
"""

import hashlib
import re
import uuid
from dataclasses import dataclass, field
from typing import Any, Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.enums import KnowledgeRelation, KnowledgeStatus, KnowledgeType, VerificationStatus
from app.exams.models import Question
from app.explanations import service as explanations
from app.explanations.context import Ineligible, build_context
from app.explanations.models import AIExplanation
from app.explanations.payload import ExplanationPayload
from app.knowledge import normalize as nz
from app.knowledge.models import KnowledgeItem

Action = Literal["create", "link", "needs_decision"]
UNDERLINE = re.compile(r"<u>(.*?)</u>")
MEANING_LINK_THRESHOLD = 0.25
FUZZY_TITLE_THRESHOLD = 0.6


@dataclass
class Match:
    knowledge_id: uuid.UUID
    title: str
    content: str
    reason: Literal["same_key", "similar_title"]
    meaning_similarity: float


@dataclass
class Candidate:
    ref: str
    question_id: uuid.UUID
    explanation_id: uuid.UUID
    knowledge_type: KnowledgeType
    canonical_key: str
    title: str
    summary: str
    details: dict[str, Any]
    role: KnowledgeRelation
    selected: bool
    action: Action
    match: Match | None = None
    warnings: list[str] = field(default_factory=list)


@dataclass
class RelationCandidate:
    source_ref: str
    target_ref: str
    relation_type: Literal["confused_with"] = "confused_with"


@dataclass
class QuestionExtraction:
    question_id: uuid.UUID
    question_number: int
    explanation_id: uuid.UUID | None
    skipped_code: str | None
    skipped_message: str | None
    candidates: list[Candidate] = field(default_factory=list)
    relations: list[RelationCandidate] = field(default_factory=list)


def _ref(question_id: uuid.UUID, ktype: str, key: str) -> str:
    return hashlib.sha256(f"{question_id}|{ktype}|{key}".encode()).hexdigest()[:16]


# ------------------------------------------------------------------ explanation choice
def approved_explanation(
    db: Session, question: Question
) -> tuple[AIExplanation | None, str | None, str | None]:
    ctx = build_context(db, question.id)
    if isinstance(ctx, Ineligible):
        return None, ctx.code, ctx.message
    current = explanations.find_current(db, question.id, ctx.content_hash)
    if current is not None and current.verification_status == VerificationStatus.APPROVED:
        return current, None, None
    if current is not None:
        return (
            None,
            "explanation_not_approved",
            "Lời giải hiện hành chưa được bạn xác nhận (chờ duyệt).",
        )
    stale_approved = db.scalar(
        select(AIExplanation.id).where(
            AIExplanation.question_id == question.id,
            AIExplanation.verification_status == VerificationStatus.APPROVED.value,
        )
    )
    if stale_approved is not None:
        return None, "explanation_stale", "Lời giải đã duyệt đã cũ (câu hỏi hoặc đáp án đã đổi)."
    return None, "no_explanation", "Câu này chưa có lời giải AI."


# ------------------------------------------------------------------ candidates
def _role(
    text_forms: list[str], correct: str, wrong: list[str], underlined: str | None
) -> KnowledgeRelation:
    forms = [f for f in text_forms if nz.clean(f)]
    if any(nz.contains(correct, f) or nz.contains(f, correct) for f in forms):
        return KnowledgeRelation.TESTS
    if underlined and any(nz.contains(underlined, f) or nz.contains(f, underlined) for f in forms):
        return KnowledgeRelation.TESTS
    if any(nz.contains(w, f) for w in wrong for f in forms):
        return KnowledgeRelation.DISTRACTOR
    return KnowledgeRelation.CONTEXT


def _grammar(
    payload: ExplanationPayload, q: Question, exp: AIExplanation, correct: str, wrong: list[str]
) -> list[Candidate]:
    out: list[Candidate] = []
    for gp in payload.grammar_points:
        core = nz.grammar_core(gp.pattern)
        if not core:
            continue
        role = _role([core], correct, wrong, None)
        key = nz.grammar_key(gp.pattern)
        out.append(
            Candidate(
                ref=_ref(q.id, "grammar", key),
                question_id=q.id,
                explanation_id=exp.id,
                knowledge_type=KnowledgeType.GRAMMAR,
                canonical_key=key,
                title=gp.pattern.strip(),
                summary=gp.meaning_vi.strip(),
                details={
                    "pattern": gp.pattern.strip(),
                    "core": core,
                    "meaning_vi": gp.meaning_vi,
                    "usage": gp.usage,
                    "contrast": gp.contrast,
                    "examples": [gp.example_ja] if gp.example_ja else [],
                },
                role=role,
                selected=role != KnowledgeRelation.CONTEXT,
                action="create",
            )
        )
    return out


def _vocabulary(
    payload: ExplanationPayload,
    q: Question,
    exp: AIExplanation,
    correct: str,
    wrong: list[str],
    underlined: str | None,
    skip_surfaces: set[str],
) -> list[Candidate]:
    out: list[Candidate] = []
    for v in payload.vocabulary:
        if not v.surface.strip() or nz.clean(v.surface) in skip_surfaces:
            continue
        role = _role([v.surface], correct, wrong, underlined)
        key = nz.vocab_key(v.surface, v.reading or v.surface)
        confusions = [
            {"option": o.option_text, "meaning_vi": o.meaning_vi}
            for o in payload.options_analysis
            if not o.is_correct and nz.contains(o.option_text, v.surface) is False
        ]
        out.append(
            Candidate(
                ref=_ref(q.id, "vocabulary", key),
                question_id=q.id,
                explanation_id=exp.id,
                knowledge_type=KnowledgeType.VOCABULARY,
                canonical_key=key,
                title=v.surface.strip(),
                summary=v.meaning_vi.strip(),
                details={
                    "surface": v.surface.strip(),
                    "reading": v.reading.strip(),
                    "meaning_vi": v.meaning_vi,
                    "note": v.note,
                    "context": q.question_text,
                    "confusions": confusions if role == KnowledgeRelation.TESTS else [],
                },
                role=role,
                selected=role != KnowledgeRelation.CONTEXT,
                action="create",
            )
        )
    return out


def _kanji_word(
    payload: ExplanationPayload, q: Question, exp: AIExplanation, correct: str
) -> list[Candidate]:
    underlined = next(iter(UNDERLINE.findall(q.question_text)), None)
    if not underlined:
        return []
    if q.question_type == "kanji_reading":
        word, reading = underlined, correct
    else:  # orthography: the underlined part is kana, the answer is the kanji word
        word, reading = correct, underlined
    gloss = next(
        (v.meaning_vi for v in payload.vocabulary if nz.clean(v.surface) == nz.clean(word)), ""
    )
    key = nz.kanji_key(word, reading)
    return [
        Candidate(
            ref=_ref(q.id, "kanji", key),
            question_id=q.id,
            explanation_id=exp.id,
            knowledge_type=KnowledgeType.KANJI,
            canonical_key=key,
            title=f"{nz.clean(word)}（{nz.clean(reading)}）",
            summary=gloss or payload.key_takeaway,
            details={
                "word": nz.clean(word),
                "reading": nz.clean(reading),
                "meaning_vi": gloss,
                "kanji": [k.model_dump() for k in payload.kanji],
                # Wrong options of the verified question = confusable forms (approved source).
                "confusions": [
                    {"option": o.option_text, "reason": o.reason}
                    for o in payload.options_analysis
                    if not o.is_correct
                ],
            },
            role=KnowledgeRelation.TESTS,
            selected=True,
            action="create",
            warnings=[] if gloss else ["Không tìm thấy nghĩa của từ trong lời giải — hãy bổ sung."],
        )
    ]


def _reading(payload: ExplanationPayload, q: Question, exp: AIExplanation) -> list[Candidate]:
    skill = nz.guess_reading_skill(q.question_text, q.question_type)
    key = nz.reading_key(skill or "unknown")
    warnings = (
        [] if skill else ["Chưa đủ căn cứ để gán kỹ năng đọc — hãy chọn kỹ năng trước khi lưu."]
    )
    return [
        Candidate(
            ref=_ref(q.id, "reading_skill", key),
            question_id=q.id,
            explanation_id=exp.id,
            knowledge_type=KnowledgeType.READING_SKILL,
            canonical_key=key,
            title=nz.READING_SKILLS.get(skill or "", "Kỹ năng đọc (chưa xác định)"),
            summary=payload.solution_summary_vi,
            details={
                "skill": skill,
                "question_type": q.question_type,
                "evidence": [e.model_dump() for e in payload.evidence],
                "strategy": payload.recognition_tips or payload.key_takeaway,
            },
            role=KnowledgeRelation.TESTS,
            selected=skill is not None,
            action="create" if skill else "needs_decision",
            warnings=warnings,
        )
    ]


def _match(db: Session, cand: Candidate) -> None:
    if cand.action == "needs_decision" and cand.knowledge_type == KnowledgeType.READING_SKILL:
        return
    same_key = db.scalar(
        select(KnowledgeItem).where(
            KnowledgeItem.knowledge_type == cand.knowledge_type.value,
            KnowledgeItem.canonical_key == cand.canonical_key,
            KnowledgeItem.status == KnowledgeStatus.ACTIVE.value,
        )
    )
    if same_key is not None:
        sim = nz.meaning_similarity(cand.summary, same_key.content)
        cand.match = Match(same_key.id, same_key.title, same_key.content, "same_key", sim)
        if cand.knowledge_type == KnowledgeType.READING_SKILL or sim >= MEANING_LINK_THRESHOLD:
            cand.action = "link"
        else:
            cand.action = "needs_decision"
            cand.warnings.append(
                f"Trùng khoá với “{same_key.title}” nhưng nghĩa khác (“{same_key.content}”) "
                "— có thể là "
                "từ đồng hình hoặc chức năng khác. Hãy chọn gộp hoặc tạo mục riêng."
            )
        return
    others = db.scalars(
        select(KnowledgeItem).where(
            KnowledgeItem.knowledge_type == cand.knowledge_type.value,
            KnowledgeItem.status == KnowledgeStatus.ACTIVE.value,
        )
    ).all()

    def comparable(title: str) -> str:
        # Grammar is compared on its core pattern (ので vs のに = 0.5, ために vs ためか = 0.67).
        return nz.grammar_core(title) if cand.knowledge_type == KnowledgeType.GRAMMAR else title

    def score(k: KnowledgeItem) -> float:
        return nz.title_similarity(comparable(k.title), comparable(cand.title))

    best = max(others, key=score, default=None)
    if best is not None and score(best) >= FUZZY_TITLE_THRESHOLD:
        sim = nz.meaning_similarity(cand.summary, best.content)
        cand.match = Match(best.id, best.title, best.content, "similar_title", sim)
        cand.action = "needs_decision"
        cand.warnings.append(f"Gần giống “{best.title}” — kiểm tra trước khi gộp; không tự gộp.")


def extract_for_question(db: Session, question_id: uuid.UUID) -> QuestionExtraction:
    q = db.get(Question, question_id)
    if q is None:
        from app.core.errors import NotFoundError

        raise NotFoundError("Không tìm thấy câu hỏi.", details={"question_id": str(question_id)})
    exp, code, message = approved_explanation(db, q)
    result = QuestionExtraction(q.id, q.question_number, exp.id if exp else None, code, message)
    if exp is None:
        return result
    payload = ExplanationPayload.model_validate(exp.explanation_json)
    correct = q.options[payload.correct_answer_index]
    wrong = [o for i, o in enumerate(q.options) if i != payload.correct_answer_index]
    underlined = next(iter(UNDERLINE.findall(q.question_text)), None)
    category = build_context(db, q.id)
    cat = category.category if not isinstance(category, Ineligible) else "vocabulary"

    candidates: list[Candidate] = []
    if cat == "reading":
        candidates += _reading(payload, q, exp)
    if cat == "kanji":
        kanji = _kanji_word(payload, q, exp, correct)
        candidates += kanji
        skip = {k.details["word"] for k in kanji}
    else:
        skip = set()
    candidates += _grammar(payload, q, exp, correct, wrong)
    candidates += _vocabulary(payload, q, exp, correct, wrong, underlined, skip)
    if cat == "grammar" and not any(
        c.knowledge_type == KnowledgeType.GRAMMAR and c.role == KnowledgeRelation.TESTS
        for c in candidates
    ):
        for c in candidates:
            if c.knowledge_type == KnowledgeType.GRAMMAR:
                c.warnings.append(
                    "Không xác định chắc mẫu nào là mẫu được hỏi — hãy kiểm tra vai trò."
                )

    seen: set[str] = set()
    unique: list[Candidate] = []
    for c in candidates:
        if c.ref in seen:
            continue
        seen.add(c.ref)
        _match(db, c)
        unique.append(c)
    result.candidates = unique

    tested = [c for c in unique if c.role == KnowledgeRelation.TESTS]
    for t in tested:
        for d in unique:
            if d.role == KnowledgeRelation.DISTRACTOR and d.knowledge_type == t.knowledge_type:
                result.relations.append(RelationCandidate(t.ref, d.ref))
    return result
