"""Small text helpers for parsing. None of these change stored question text except where a
caller explicitly strips a *marker* (question number, option label, 正解 prefix)."""

import re
import unicodedata

from app.database.enums import ExamCategory, QuestionType

# Characters accepted as option labels, mapped to a 1-based index.
_LABELS: dict[str, int] = {}
for i, chars in enumerate(["1１①Aaａ", "2２②Bbｂ", "3３③Ccｃ", "4４④Ddｄ", "5５⑤Eeｅ", "6６⑥Ffｆ"]):
    for ch in chars:
        _LABELS[ch] = i + 1
for i, ch in enumerate("ＡＢＣＤＥＦ"):
    _LABELS[ch] = i + 1

OPTION_LABEL_CHARS = "".join(_LABELS)

# Safe inline markup kept in question text (rendered by the frontend as elements, never as HTML).
INLINE_TAG_RE = re.compile(r"</?(?:u|ruby|rt)>")

_CJK = r"぀-ヿ㐀-䶿一-鿿豈-﫿ｦ-ﾟ　-〿！-｠"
_SPACE_BETWEEN_CJK = re.compile(rf"(?<=[{_CJK}])[ \t]+(?=[{_CJK}])")


def label_to_index(label: str) -> int | None:
    return _LABELS.get(label.strip())


def to_int(digits: str) -> int | None:
    """'１２' → 12. Only used for markers (numbers), never for content."""
    folded = unicodedata.normalize("NFKC", digits).strip()
    return int(folded) if folded.isdigit() else None


def clean_option(value: str) -> str:
    # Trailing ideographic spaces are layout artefacts on many pages.
    return value.strip().strip("　").strip()


def collapse_ocr_spacing(value: str) -> str:
    """Tesseract inserts spaces between Japanese characters; remove only those."""
    return _SPACE_BETWEEN_CJK.sub("", value)


def guess_question_type(heading: str) -> QuestionType | None:
    """Map a 問題 heading (instructions) to a JLPT N3 question type."""
    h = unicodedata.normalize("NFKC", heading)
    rules: list[tuple[tuple[str, ...], QuestionType]] = [
        (("読み方",), QuestionType.KANJI_READING),
        (("漢字で書く", "どう書く", "書き方"), QuestionType.ORTHOGRAPHY),
        (("意味が最も近い", "意味がもっとも近い", "意味が一番近い"), QuestionType.PARAPHRASE),
        (("使い方",), QuestionType.USAGE),
        (("★",), QuestionType.SENTENCE_COMPOSITION),
        (("文章全体の内容", "全体の内容を考えて", "の中に入る"), QuestionType.TEXT_GRAMMAR),
        (("情報", "右のページ", "案内", "お知らせ"), QuestionType.INFORMATION_RETRIEVAL),
        (("文章を読んで",), QuestionType.READING_SHORT),
        (("文法",), QuestionType.GRAMMAR_FORM),
        (("( )に入れる", "()に入れる", "に入れるのに"), QuestionType.CONTEXTUAL_DEFINITION),
    ]
    for needles, qtype in rules:
        if any(n in h for n in needles):
            return qtype
    return None


def category_for_types(types: list[QuestionType]) -> ExamCategory | None:
    if not types:
        return None
    buckets: dict[ExamCategory, int] = {}
    for t in types:
        if t in {QuestionType.KANJI_READING, QuestionType.ORTHOGRAPHY}:
            cat = ExamCategory.VOCABULARY
        elif t in {
            QuestionType.GRAMMAR_FORM,
            QuestionType.SENTENCE_COMPOSITION,
            QuestionType.TEXT_GRAMMAR,
        }:
            cat = ExamCategory.GRAMMAR
        elif t in {
            QuestionType.READING_SHORT,
            QuestionType.READING_MEDIUM,
            QuestionType.READING_LONG,
            QuestionType.INFORMATION_RETRIEVAL,
        }:
            cat = ExamCategory.READING
        elif t == QuestionType.OTHER:
            continue
        else:
            cat = ExamCategory.VOCABULARY
        buckets[cat] = buckets.get(cat, 0) + 1
    return max(buckets, key=lambda c: buckets[c]) if buckets else None
