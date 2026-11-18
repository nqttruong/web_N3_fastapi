"""String enums shared by models and API schemas.

Stored as TEXT + CHECK constraint (not native PG ENUM) so adding a value is a cheap migration
and the values map 1:1 to JSON and to Android/Kotlin enum names.
"""

from enum import StrEnum


class JlptLevel(StrEnum):
    N1 = "N1"
    N2 = "N2"
    N3 = "N3"
    N4 = "N4"
    N5 = "N5"


class ExamCategory(StrEnum):
    VOCABULARY = "vocabulary"
    KANJI = "kanji"
    GRAMMAR = "grammar"
    READING = "reading"


class ExamStatus(StrEnum):
    DRAFT = "draft"
    READY = "ready"
    ARCHIVED = "archived"


class QuestionType(StrEnum):
    """JLPT N3 問題 types (mondai), plus ``other`` for anything not yet classified."""

    KANJI_READING = "kanji_reading"  # 漢字読み
    ORTHOGRAPHY = "orthography"  # 表記
    WORD_FORMATION = "word_formation"  # 語形成
    CONTEXTUAL_DEFINITION = "contextual_definition"  # 文脈規定
    PARAPHRASE = "paraphrase"  # 言い換え類義
    USAGE = "usage"  # 用法
    GRAMMAR_FORM = "grammar_form"  # 文法形式の判断
    SENTENCE_COMPOSITION = "sentence_composition"  # 文の組み立て
    TEXT_GRAMMAR = "text_grammar"  # 文章の文法
    READING_SHORT = "reading_short"  # 内容理解（短文）
    READING_MEDIUM = "reading_medium"  # 内容理解（中文）
    READING_LONG = "reading_long"  # 内容理解（長文）
    INFORMATION_RETRIEVAL = "information_retrieval"  # 情報検索
    OTHER = "other"


class AnswerStatus(StrEnum):
    """Trust level of ``questions.correct_answer``.

    Only ``verified`` answers are used for grading or shown as the official answer.
    AI-inferred answers never land in ``correct_answer``; they live in ``ai_explanations``.
    """

    MISSING = "missing"  # no answer recorded
    UNVERIFIED = "unverified"  # recorded but not confirmed (e.g. typed from memory)
    VERIFIED = "verified"  # confirmed against the official key by the user


class AnswerSource(StrEnum):
    """Where ``questions.correct_answer`` came from (provenance, PR2).

    Provenance never implies trust: trust is ``answer_status``. Only a user action sets
    ``verified``.
    """

    MANUAL = "manual"  # typed in the manual question form / PATCH
    SITE_KEY = "site_key"  # shown by the source website (HTML key or 正解 marker in pasted text)
    USER_ENTERED = "user_entered"  # chosen or changed by the user in the import preview
    OCR = "ocr"  # read from a screenshot by OCR


class AttemptSource(StrEnum):
    PRACTICE = "practice"  # taken in this app
    IMPORT = "import"  # reconstructed from the user's own answers in an imported result page


class ImportMethod(StrEnum):
    TEXT = "text"
    HTML = "html"
    IMAGES = "images"
    BROWSER_CAPTURE = "browser_capture"


class ImportStatus(StrEnum):
    UPLOADED = "uploaded"  # input stored, not parsed yet
    PARSING = "parsing"  # adapter/OCR running
    NEEDS_REVIEW = "needs_review"  # parsed, has blocking issues or uncertain items
    READY = "ready"  # validated, no blocking issues
    COMMITTED = "committed"  # saved into exams/questions (terminal)
    FAILED = "failed"  # parsing/OCR failed; see error_code


class OcrStatus(StrEnum):
    PENDING = "pending"
    DONE = "done"
    FAILED = "failed"


class VerificationStatus(StrEnum):
    """Review state of an AI explanation (PR3; PR1 values unverified/verified were renamed)."""

    GENERATED = "generated"  # passed all automatic checks, waiting for the user
    NEEDS_REVIEW = "needs_review"  # automatic checks raised warnings, or imported manually
    APPROVED = "approved"  # confirmed by the user — never set automatically
    REJECTED = "rejected"  # marked inaccurate by the user


class ExplanationOrigin(StrEnum):
    API = "api"
    MANUAL = "manual"  # pasted back from ChatGPT


class JobStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    PARTIAL_FAILED = "partial_failed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class JobItemStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    CACHED = "cached"  # a current explanation already existed
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    SKIPPED = "skipped"  # not eligible (e.g. answer not verified, passage missing)
    CANCELLED = "cancelled"


class AIRequestStatus(StrEnum):
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class KnowledgeType(StrEnum):
    # Mirrors Android ItemType (VOCABULARY, KANJI, GRAMMAR) plus reading skills.
    VOCABULARY = "vocabulary"
    KANJI = "kanji"
    GRAMMAR = "grammar"
    READING_SKILL = "reading_skill"


class KnowledgeRelation(StrEnum):
    TESTS = "tests"  # the question directly tests this item
    DISTRACTOR = "distractor"  # appears in a wrong option
    CONTEXT = "context"  # appears in the stem/passage


class KnowledgeLink(StrEnum):
    """Relation between two knowledge items (PR4)."""

    CONFUSED_WITH = "confused_with"  # symmetric; stored with source_id < target_id
    PREREQUISITE = "prerequisite"  # source is needed before target
    RELATED_TO = "related_to"  # symmetric


class KnowledgeStatus(StrEnum):
    ACTIVE = "active"
    ARCHIVED = "archived"  # hidden from review, history kept
    MERGED = "merged"  # merged into another item (merged_into_id)


class ReviewItemStatus(StrEnum):
    ACTIVE = "active"
    SUSPENDED = "suspended"
    DONE = "done"  # archived / no longer reviewed (history kept)


class ReviewType(StrEnum):
    ORIGINAL_QUESTION = "original_question"  # Type A: re-answer the question you got wrong
    KNOWLEDGE_RECALL = "knowledge_recall"  # Type B: recall a grammar/vocab/kanji item
    CONTRAST = "contrast"  # Type C: tell two confusable items apart


class SrsState(StrEnum):
    # Same states as Android ProgressState, plus NEW (never answered).
    NEW = "new"
    LEARNING = "learning"
    REVIEW = "review"
    MASTERED = "mastered"


class PracticeStatus(StrEnum):
    NEEDS_REVIEW = "needs_review"  # AI/manual output, waiting for the user
    APPROVED = "approved"  # user checked question + answer; usable in reviews
    REJECTED = "rejected"


class PracticeGenerationStatus(StrEnum):
    COMPLETED = "completed"
    PARTIAL = "partial"  # some generated questions were invalid and dropped
    FAILED = "failed"


class ReviewRating(StrEnum):
    # Same four values as Android ReviewRating.
    AGAIN = "again"
    HARD = "hard"
    GOOD = "good"
    EASY = "easy"


class SyncOperation(StrEnum):
    INSERT = "insert"
    UPDATE = "update"
    DELETE = "delete"


def check_in(column: str, enum: type[StrEnum]) -> str:
    values = ", ".join(f"'{member.value}'" for member in enum)
    return f"{column} IN ({values})"
