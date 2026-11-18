"""Generic plain-text adapter (Mode A, also used for generic HTML and OCR output).

Recognised layout (full-width and half-width markers both work)::

    問題１ ＿＿＿のことばの読み方として…          ← section heading → question type
    1. ここは水が<u>浅い</u>ので…                  ← question  (1. / 1． / 問1 / 【19】)
    1) おそい   2) あさい …                        ← options   (1) １） A. ① …), also inline
    正解: 2   /   あなたの答え: 1                   ← site answer / user's own answer
    正解:　2) あさい  不正解:　1) おそい            ← dethitiengnhat result markers on options
    （１）  + paragraph(s)                          ← reading passage shared by next questions
    解答 / 1. 2 / 2. 4                             ← answer-key block at the end

Anything the parser is not sure about is attached as a ``parser_note`` so the user must
review it. Question text and options are kept exactly as written (only the leading marker is
removed); furigana in brackets is preserved.
"""

import re
from dataclasses import dataclass, field

from app.database.enums import QuestionType
from app.imports.adapters.base import ParseResult, new_key
from app.imports.schemas import (
    DraftContent,
    DraftExam,
    DraftPassage,
    DraftQuestion,
    Issue,
    ParserNote,
)
from app.imports.textutil import (
    category_for_types,
    clean_option,
    guess_question_type,
    label_to_index,
    to_int,
)

_D = "0-9０-９"
_L = "1-6１-６A-Fa-fＡ-Ｆ①-⑥"
HEADER_RE = re.compile(rf"^\s*(?:文字\s*[・･]?\s*語彙|語彙|文法|読解)?\s*問題\s*[{_D}]{{1,2}}")
QUESTION_RE = re.compile(
    rf"^\s*(?:問\s*(?P<num_q>[{_D}]{{1,3}})\s*[\.．。:：]?|(?P<num>[{_D}]{{1,3}})\s*[\.．。:：])"
    rf"\s*(?P<body>.*\S)?\s*$"
)
BRACKET_Q_RE = re.compile(rf"^\s*【\s*(?P<num>[{_D}]{{1,3}})\s*】")
OPTION_RE = re.compile(
    rf"^\s*(?P<mark>(?:不正解|正解)\s*[:：]\s*)?(?P<label>[{_L}])\s*"
    rf"(?P<delim>[\)）\.．:：、])\s*(?P<body>.*\S)\s*$"
)
CIRCLED_RE = re.compile(
    r"^\s*(?P<mark>(?:不正解|正解)\s*[:：]\s*)?(?P<label>[①-⑥])\s*(?P<body>.*\S)\s*$"
)
INLINE_MARK_RE = re.compile(r"(?:(?<=\s)|^)(?:(?P<label>[1-6１-６])\s*[\)）]|(?P<circ>[①-⑥]))\s*")
_KEY_WORDS = r"正解|正答|答え|答|解答|Đáp án đúng|Đáp án|Answer|Key"
ANSWER_RE = re.compile(
    rf"^\s*(?:{_KEY_WORDS})\s*[:：は]?\s*(?P<label>[{_L}])\s*[\)）\.．]?\s*$", re.IGNORECASE
)
_USER_WORDS = r"あなたの(?:答え|回答|解答)|選んだ答え|Bạn chọn|Đáp án của bạn|Your answer"
USER_RE = re.compile(
    rf"^\s*(?:{_USER_WORDS})\s*[:：]?\s*(?P<label>[{_L}])\s*[\)）\.．]?\s*$", re.IGNORECASE
)
KEY_HEADING_RE = re.compile(r"^\s*(?:解答|正解|答え|Đáp án|Answer key|Answers)\s*[:：]?\s*$", re.I)
KEY_LINE_RE = re.compile(
    rf"^\s*(?:問\s*)?(?P<num>[{_D}]{{1,3}})\s*[\.．:：\-－)）]?\s+(?P<label>[1-6１-６①-⑥])\s*$"
)
PASSAGE_LABEL_RE = re.compile(rf"^\s*[（(]\s*[{_D}]{{1,2}}\s*[)）]\s*$")
EXAMPLE_RE = re.compile(r"^\s*[（(]?\s*例\s*[)）]?")

READING_TYPES = {
    QuestionType.READING_SHORT,
    QuestionType.READING_MEDIUM,
    QuestionType.READING_LONG,
    QuestionType.INFORMATION_RETRIEVAL,
    QuestionType.TEXT_GRAMMAR,
}
PASSAGE_MIN_CHARS = 80
# UI labels that appear when copying page text from known sites (not exam content).
NOISE_LINES = {
    "Đọc tiếng Nhật",
    "Dừng đọc",
    "Tính Điểm",
    "Ngữ pháp,Đọc Hiểu >>",
    "Đọc Hiểu >>",
    "Từ Vựng >>",
}


@dataclass
class _Q:
    number: int | None
    text_lines: list[str]
    qtype: QuestionType
    passage_key: str | None
    options: list[str] = field(default_factory=list)
    marks: dict[int, str] = field(default_factory=dict)  # option index → "ok" | "ng"
    option_style: str | None = None  # "dot" | "paren" — style of the first option label
    site_answer: int | None = None
    user_answer: int | None = None
    notes: list[ParserNote] = field(default_factory=list)


class GenericTextAdapter:
    name = "generic_text"

    def __init__(self, *, name: str | None = None, from_ocr: bool = False) -> None:
        if name:
            self.name = name
        self.from_ocr = from_ocr

    # ------------------------------------------------------------------ public
    def parse(self, raw: str) -> ParseResult:
        state = _State()
        for line in raw.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
            state.feed(line.rstrip())
        state.finish()
        return self._build(state)

    # ------------------------------------------------------------------ build
    def _build(self, state: "_State") -> ParseResult:
        questions: list[DraftQuestion] = []
        numbers = [q.number for q in state.questions if q.number is not None]
        duplicated = {n for n in numbers if numbers.count(n) > 1}
        for q in state.questions:
            notes = list(q.notes)
            text = "\n".join(q.text_lines).strip()
            if q.number is None:
                notes.append(ParserNote(code="missing_number", message="Không thấy số câu."))
            elif q.number in duplicated:
                notes.append(ParserNote(code="duplicate_number", message="Số câu bị lặp."))
            if len(q.options) != 4:
                notes.append(
                    ParserNote(
                        code="option_count",
                        message=f"Nhận diện được {len(q.options)} lựa chọn (thường là 4).",
                    )
                )
            if q.marks:
                self._apply_marks(q, notes)
            is_example = bool(EXAMPLE_RE.match(text))
            if is_example:
                notes.append(ParserNote(code="example", message="Có vẻ là câu ví dụ (例)."))
            if self.from_ocr:
                notes.append(
                    ParserNote(code="ocr_source", message="Dữ liệu từ OCR — hãy đối chiếu với ảnh.")
                )
            questions.append(
                DraftQuestion(
                    key=new_key(),
                    include=not is_example,
                    question_number=q.number,
                    question_type=q.qtype,
                    question_text=text,
                    options=q.options[:6],
                    passage_key=q.passage_key,
                    site_answer=q.site_answer,
                    user_answer=q.user_answer,
                    # Pre-filled as a *candidate* only; never confirmed by the parser.
                    correct_answer=q.site_answer,
                    parser_notes=notes,
                    is_example=is_example,
                )
            )

        draft_notes: list[Issue] = []
        if state.ignored:
            preview = " / ".join(s[:40] for s in state.ignored[:3])
            draft_notes.append(
                Issue(
                    severity="warning",
                    code="ignored_lines",
                    message=f"Bỏ qua {len(state.ignored)} dòng không nhận diện được: {preview}",
                    data={"lines": state.ignored[:50]},
                )
            )
        if not questions:
            draft_notes.append(
                Issue(
                    severity="error",
                    code="no_questions",
                    message=(
                        "Không nhận diện được câu hỏi nào. Kiểm tra định dạng hoặc nhập thủ công."
                    ),
                )
            )
        content = DraftContent(
            exam=DraftExam(
                title=state.title or "",
                category=category_for_types([q.question_type for q in questions]),
            ),
            passages=state.passages,
            questions=questions,
        )
        return ParseResult(adapter=self.name, content=content, notes=draft_notes)

    @staticmethod
    def _apply_marks(q: _Q, notes: list[ParserNote]) -> None:
        ok = [i for i, m in q.marks.items() if m == "ok"]
        ng = [i for i, m in q.marks.items() if m == "ng"]
        if len(ok) == 1 and len(ng) <= 1:
            q.site_answer = q.site_answer or ok[0]
            # On dethitiengnhat result pages the chosen option is marked 不正解 when wrong;
            # when only 正解 is shown, the user picked the correct one.
            q.user_answer = q.user_answer or (ng[0] if ng else ok[0])
            notes.append(
                ParserNote(
                    code="answer_from_markers",
                    message="Đáp án và lựa chọn của bạn được suy ra từ ký hiệu 正解/不正解.",
                )
            )
        else:
            notes.append(
                ParserNote(code="ambiguous_markers", message="Ký hiệu 正解/不正解 không rõ ràng.")
            )


class _State:
    def __init__(self) -> None:
        self.questions: list[_Q] = []
        self.passages: list[DraftPassage] = []
        self.ignored: list[str] = []
        self.title: str | None = None
        self.section_type: QuestionType | None = None
        self.current: _Q | None = None
        self.pending: list[str] = []
        self.pending_is_passage = False
        self.passage_key: str | None = None
        self.key_mode = False
        self._seen_content = False

    # ------------------------------------------------------------- dispatch
    def feed(self, line: str) -> None:
        if line.strip() in NOISE_LINES:
            return
        if not line.strip():
            if self.pending:
                self.pending.append("")
            return

        if self.key_mode:
            km = KEY_LINE_RE.match(line)
            if km:
                self._apply_key(to_int(km["num"]), label_to_index(km["label"]))
                return
            self.key_mode = False

        if HEADER_RE.match(line):
            self._close_question()
            self._drop_pending()
            self.section_type = guess_question_type(line)
            self.passage_key = None
            self._seen_content = True
            return

        if KEY_HEADING_RE.match(line):
            self._close_question()
            self._drop_pending()
            self.key_mode = True
            return

        if self.current is not None:
            am = ANSWER_RE.match(line)
            if am:
                self.current.site_answer = label_to_index(am["label"])
                return
            um = USER_RE.match(line)
            if um:
                self.current.user_answer = label_to_index(um["label"])
                return

        if PASSAGE_LABEL_RE.match(line):
            self._close_question()
            self._drop_pending()
            self.pending = [line.strip()]
            self.pending_is_passage = True
            return

        if self.current is not None and not self.current.options and self._try_inline(line):
            return

        if self._try_option(line):
            return

        bm = BRACKET_Q_RE.match(line)
        qm = QUESTION_RE.match(line)
        if bm or qm:
            self._close_question()
            self._flush_pending_before_question()
            if bm:
                number, body = to_int(bm["num"]), line.strip()
            else:
                assert qm is not None
                number, body = to_int(qm["num"] or qm["num_q"]), (qm["body"] or "").strip()
            self.current = _Q(
                number=number,
                text_lines=[body] if body else [],
                qtype=self.section_type or QuestionType.OTHER,
                passage_key=self.passage_key,
            )
            self._seen_content = True
            return

        # Plain text
        if self.current is not None and not self.current.options:
            self.current.text_lines.append(line.strip())
            return
        if (
            not self._seen_content
            and self.title is None
            and not self.questions
            and len(line.strip()) <= 80
        ):
            self.title = line.strip()[:300]
            return
        self._close_question()
        self.pending.append(line.rstrip())

    # ------------------------------------------------------------- options
    def _try_option(self, line: str) -> bool:
        m = OPTION_RE.match(line) or CIRCLED_RE.match(line)
        if not m or self.current is None:
            return False
        idx = label_to_index(m["label"])
        if idx is None:
            return False
        delim = m.groupdict().get("delim")
        expected = len(self.current.options) + 1
        # "1." could also start the next question; only treat it as an option when the
        # numbering continues the current option list.
        style = "dot" if delim in {".", "．", ":", "：", "、"} else "paren"
        if style == "dot" and (
            idx != expected
            or not self.current.text_lines
            or len(self.current.options) >= 4
            or self.current.option_style not in {None, "dot"}
        ):
            return False
        if self.current.option_style is None:
            self.current.option_style = style
        if idx != expected:
            self.current.notes.append(
                ParserNote(code="option_order", message=f"Lựa chọn {idx} không đúng thứ tự.")
            )
        self.current.options.append(clean_option(m["body"]))
        if m["mark"]:
            self.current.marks[len(self.current.options)] = (
                "ng" if m["mark"].startswith("不") else "ok"
            )
        return True

    def _try_inline(self, line: str) -> bool:
        marks = list(INLINE_MARK_RE.finditer(line))
        if len(marks) < 2 or self.current is None:
            return False
        labels = [label_to_index(m["label"] or m["circ"]) for m in marks]
        if labels != list(range(1, len(marks) + 1)):
            return False
        for i, m in enumerate(marks):
            end = marks[i + 1].start() if i + 1 < len(marks) else len(line)
            self.current.options.append(clean_option(line[m.end() : end]))
        return True

    # ------------------------------------------------------------- blocks
    def _apply_key(self, number: int | None, answer: int | None) -> None:
        for q in self.questions:
            if q.number == number and answer is not None:
                q.site_answer = answer
                return

    def _close_question(self) -> None:
        if self.current is not None:
            self.questions.append(self.current)
            self.current = None

    def _drop_pending(self) -> None:
        text = [s for s in self.pending if s.strip()]
        if text and not self.pending_is_passage:
            self.ignored.extend(s.strip() for s in text)
        elif text:
            self._make_passage()
        self.pending = []
        self.pending_is_passage = False

    def _flush_pending_before_question(self) -> None:
        text = "\n".join(self.pending).strip("\n")
        if not text.strip():
            self.pending = []
            self.pending_is_passage = False
            return
        if (
            self.pending_is_passage
            or self.section_type in READING_TYPES
            or len(text.replace("\n", "")) >= PASSAGE_MIN_CHARS
        ):
            self._make_passage()
        else:
            self.ignored.extend(s.strip() for s in self.pending if s.strip())
        self.pending = []
        self.pending_is_passage = False

    def _make_passage(self) -> None:
        # Collapse 3+ blank lines into a paragraph break; keep the text otherwise untouched.
        content = re.sub(r"\n{3,}", "\n\n", "\n".join(self.pending).strip("\n"))
        key = f"p{len(self.passages) + 1}"
        self.passages.append(DraftPassage(key=key, content=content))
        self.passage_key = key

    def finish(self) -> None:
        self._close_question()
        if any(s.strip() for s in self.pending):
            self.ignored.extend(s.strip() for s in self.pending if s.strip())
        self.pending = []
