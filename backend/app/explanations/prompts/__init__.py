"""Versioned prompt templates.

A prompt version is immutable: editing any file of a registered version must come with a new
version directory and a new entry here (``tests/test_explanation_prompts.py`` checks the
checksums). The version is part of every explanation's cache key.
"""

import hashlib
import json
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import TYPE_CHECKING

from app.explanations.context import QuestionContext
from app.explanations.payload import Category, output_json_schema

if TYPE_CHECKING:
    from app.practice.context import PracticeContext

PROMPTS_DIR = Path(__file__).resolve().parent
CURRENT_VERSION = "n3-explain-v1"
PRACTICE_VERSION = "n3-practice-v1"

# version -> (directory, sha256 of all files in sorted order)
REGISTRY: dict[str, tuple[str, str]] = {
    "n3-practice-v1": (
        "n3_practice_v1",
        "d2645a46bccb68bca84f294909295cca26991feaf2bb6a21e4500353dd057bb0",
    ),
    "n3-explain-v1": (
        "n3_explain_v1",
        "429530b6df8ca2f472fe2100a203c6ea128e3faab42b6b656e50d174a53a6f52",
    ),
}
CATEGORIES: tuple[Category, ...] = ("grammar", "vocabulary", "kanji", "reading")


@dataclass(frozen=True)
class RenderedPrompt:
    version: str
    instructions: str  # system / developer message
    input: str  # user message carrying the data block


def directory_checksum(directory: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(directory.glob("*.md")):
        digest.update(path.name.encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()


@cache
def _read(version: str, name: str) -> str:
    folder, _ = REGISTRY[version]
    return (PROMPTS_DIR / folder / name).read_text(encoding="utf-8").strip()


def data_block(ctx: QuestionContext) -> str:
    data = {
        "question_id": str(ctx.question_id),
        "exam": {"title": ctx.exam_title, "source_url": ctx.source_url},
        "question_number": ctx.question_number,
        "question_type": ctx.question_type,
        "category": ctx.category,
        "passage": ctx.passage,
        "question_text": ctx.question_text,
        "options": [{"index": i, "text": t} for i, t in enumerate(ctx.options)],
        "verified_answer_index": ctx.correct_index,
        "learner_selected_index": ctx.selected_index,
    }
    # "</" is escaped so exam text can never close the data block early.
    encoded = json.dumps(data, ensure_ascii=False, indent=2).replace("</", "<\\/")
    return f"<exam_data>\n{encoded}\n</exam_data>"


def instructions_for(category: Category, version: str = CURRENT_VERSION) -> str:
    return _read(version, "system.md") + "\n\n" + _read(version, f"guidance_{category}.md")


def render(
    ctx: QuestionContext, *, feedback: list[str] | None = None, version: str = CURRENT_VERSION
) -> RenderedPrompt:
    parts = [data_block(ctx)]
    if feedback:
        parts.append(
            "Lần trả lời trước không hợp lệ vì:\n- "
            + "\n- ".join(feedback)
            + "\nHãy trả lời lại, sửa đúng các lỗi trên và giữ nguyên các quy tắc."
        )
    return RenderedPrompt(version, instructions_for(ctx.category, version), "\n\n".join(parts))


def render_manual(contexts: list[QuestionContext], version: str = CURRENT_VERSION) -> str:
    """One self-contained prompt for ChatGPT covering several questions."""
    categories = sorted({c.category for c in contexts})
    sections = [
        _read(version, "manual_wrapper.md").replace("{count}", str(len(contexts))),
        _read(version, "system.md"),
        *(_read(version, f"guidance_{cat}.md") for cat in categories),
        "DỮ LIỆU CÁC CÂU HỎI",
        *(data_block(c) for c in contexts),
        "JSON SCHEMA CỦA MỖI LỜI GIẢI",
        json.dumps(output_json_schema(), ensure_ascii=False, indent=2),
    ]
    return "\n\n".join(sections)


def practice_data_block(ctx: "PracticeContext") -> str:
    data = {
        "knowledge_id": str(ctx.knowledge_id),
        "knowledge": {
            "type": ctx.knowledge_type,
            "title": ctx.title,
            "summary": ctx.summary,
            "details": ctx.details,
        },
        "confusions": ctx.confusions,
        "approved_takeaways": ctx.approved_takeaways,
        "avoid_questions": ctx.avoid_questions[:30],
        "question_type": ctx.question_type,
        "count": ctx.count,
        "level": "N3",
    }
    encoded = json.dumps(data, ensure_ascii=False, indent=2).replace("</", "<\\/")
    return f"<practice_data>\n{encoded}\n</practice_data>"


def render_practice(ctx: "PracticeContext", *, feedback: list[str] | None = None) -> RenderedPrompt:
    parts = [practice_data_block(ctx)]
    if feedback:
        parts.append("Lần trước không hợp lệ vì:\n- " + "\n- ".join(feedback) + "\nHãy soạn lại.")
    return RenderedPrompt(
        PRACTICE_VERSION, _read(PRACTICE_VERSION, "system.md"), "\n\n".join(parts)
    )


def render_practice_manual(ctx: "PracticeContext") -> str:
    from app.practice.payload import PracticeSet

    return "\n\n".join(
        [
            _read(PRACTICE_VERSION, "manual_wrapper.md"),
            _read(PRACTICE_VERSION, "system.md"),
            practice_data_block(ctx),
            "JSON SCHEMA",
            json.dumps(PracticeSet.model_json_schema(), ensure_ascii=False, indent=2),
        ]
    )
