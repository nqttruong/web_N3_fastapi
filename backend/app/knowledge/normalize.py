"""Canonical keys and similarity for knowledge deduplication.

Keys per type (never raw string equality):

* grammar        ``grammar:<core pattern>`` — placeholders (〜, V, N, Vた／Nの＋ …) removed
* vocabulary     ``vocab:<surface>|<reading in hiragana>`` — homographs with another reading
                 get another key; same surface+reading with a different meaning is flagged
* kanji (word)   ``kanji:<word>|<reading in hiragana>`` — a kanji word *in the reading tested*;
                 the same characters read differently are different items
* reading skill  ``reading:<skill code>`` from a fixed taxonomy

A key match is only a *suggestion*: when the meanings differ (possible homograph / other
function) the candidate is marked ``needs_decision`` and the user chooses. A deliberate
second sense gets a ``#n`` suffix.
"""

import re
import unicodedata
from difflib import SequenceMatcher

from app.imports.textutil import INLINE_TAG_RE

_WS = re.compile(r"\s+")
_PLACEHOLDER = re.compile(r"[A-Za-zＡ-Ｚａ-ｚ]+")
_STRIP = "〜～~・･…‥（）()「」『』[]【】"
_BRACKETED = re.compile(r"[（(][^）)]*[）)]")
_VI_WORD = re.compile(r"[\w]+", re.UNICODE)

READING_SKILLS: dict[str, str] = {
    "connectives": "Từ nối / mạch văn",
    "reference": "Từ chỉ thị (それ・この…)",
    "cause_reason": "Nguyên nhân / lý do",
    "author_view": "Ý kiến / chủ đích của tác giả",
    "main_idea": "Ý chính",
    "detail_match": "Chi tiết đúng với nội dung",
    "negation_exception": "Câu hỏi phủ định / ngoại lệ",
    "paraphrase_inference": "Suy luận / diễn đạt lại",
    "info_retrieval": "Tìm thông tin (情報検索)",
}


def clean(text: str) -> str:
    return _WS.sub("", unicodedata.normalize("NFKC", INLINE_TAG_RE.sub("", text))).strip()


def to_hiragana(text: str) -> str:
    out = []
    for ch in unicodedata.normalize("NFKC", text):
        code = ord(ch)
        out.append(chr(code - 0x60) if 0x30A1 <= code <= 0x30F6 else ch)
    return "".join(out)


def grammar_core(pattern: str) -> str:
    text = _BRACKETED.sub("", clean(pattern))  # sense notes like （目的） are not part of the key
    for sep in ("+", "＋"):
        if sep in text:
            text = text.rsplit(sep, 1)[1]
    if "/" in text:
        text = text.rsplit("/", 1)[1]
    text = text.strip(_STRIP + "/")
    starts_with_placeholder = bool(_PLACEHOLDER.match(text))
    text = _PLACEHOLDER.sub("", text).strip(_STRIP + "-/")
    if starts_with_placeholder and len(text) > 1 and text[0] in "のな":
        text = text[1:]  # "Nのおかげで" / "Naなのに" → connector belongs to the placeholder
    return text


def grammar_key(pattern: str) -> str:
    return f"grammar:{grammar_core(pattern)}"


def vocab_key(surface: str, reading: str) -> str:
    return f"vocab:{clean(surface)}|{to_hiragana(clean(reading))}"


def kanji_key(word: str, reading: str) -> str:
    return f"kanji:{clean(word)}|{to_hiragana(clean(reading))}"


def reading_key(skill: str) -> str:
    return f"reading:{skill}"


def base_key(key: str) -> str:
    return key.split("#", 1)[0]


def title_similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, clean(a), clean(b)).ratio()


def meaning_similarity(a: str, b: str) -> float:
    """Word-overlap of two Vietnamese glosses (0..1). Rough on purpose: only used to decide
    whether to *ask* the user before linking two items with the same key."""
    wa = {w.lower() for w in _VI_WORD.findall(unicodedata.normalize("NFC", a or ""))}
    wb = {w.lower() for w in _VI_WORD.findall(unicodedata.normalize("NFC", b or ""))}
    if not wa or not wb:
        return 1.0  # nothing to compare: do not block on missing glosses
    return len(wa & wb) / len(wa | wb)


def contains(haystack: str, needle: str) -> bool:
    n = clean(needle)
    return bool(n) and n in clean(haystack)


def guess_reading_skill(question_text: str, question_type: str) -> str | None:
    t = clean(question_text)
    if question_type == "information_retrieval":
        return "info_retrieval"
    if question_type == "text_grammar":
        return "connectives"
    rules: list[tuple[tuple[str, ...], str]] = [
        (("ないもの", "違うもの", "合わないもの", "ではないもの"), "negation_exception"),
        (("筆者",), "author_view"),
        (("指す", "何を指", "指しているもの"), "reference"),
        (("なぜ", "理由"), "cause_reason"),
        (("どういうこと", "どういう意味"), "paraphrase_inference"),
        (("言いたいこと", "テーマ", "主張"), "main_idea"),
        (("正しいもの", "合っているもの", "内容と合う"), "detail_match"),
    ]
    for needles, skill in rules:
        if any(n in t for n in needles):
            return skill
    return None
