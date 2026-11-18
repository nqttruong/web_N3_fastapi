"""HTML adapters (Mode B).

HTML pasted by the user is parsed with lxml via BeautifulSoup — no JavaScript is executed and
the HTML is never rendered. Before extraction the tree is sanitised: scripts, styles, embedded
objects, comments, event-handler/style attributes and ``javascript:`` URLs are removed.

Only text is extracted. A tiny inline subset is preserved as text markup because it carries
meaning in JLPT questions: ``<u>…</u>`` (the underlined word in 漢字読み questions) and
``<ruby>…<rt>…</rt></ruby>`` (furigana). The frontend renders exactly these tags as elements and
everything else as plain text.
"""

import re
from urllib.parse import urlparse

from bs4 import BeautifulSoup, Tag
from bs4.element import Comment, NavigableString

from app.database.enums import ExamCategory, QuestionType
from app.imports.adapters.base import ParseResult, UnsupportedInputError, new_key
from app.imports.adapters.text import EXAMPLE_RE, GenericTextAdapter
from app.imports.schemas import (
    DraftContent,
    DraftExam,
    DraftPassage,
    DraftQuestion,
    Issue,
    ParserNote,
)
from app.imports.textutil import category_for_types, clean_option, guess_question_type

DANGEROUS_TAGS = (
    "script", "style", "noscript", "iframe", "frame", "frameset", "object", "embed", "applet",
    "link", "meta", "base", "template", "svg", "math", "canvas", "video", "audio", "source",
    "track", "picture", "img", "button", "select", "textarea", "dialog",
)  # fmt: skip
BLOCK_TAGS = {
    "p", "div", "li", "ul", "ol", "tr", "table", "section", "article", "header", "footer",
    "h1", "h2", "h3", "h4", "h5", "h6", "label", "form", "blockquote", "pre", "dd", "dt",
}  # fmt: skip
_WS = re.compile(r"[ \t\r\n\f\v]+")  # NOT 　: ideographic spaces are content (（　　）)


# ----------------------------------------------------------------- sanitising
def sanitize(raw: str) -> BeautifulSoup:
    soup = BeautifulSoup(raw, "lxml")
    for comment in soup.find_all(string=lambda s: isinstance(s, Comment)):
        comment.extract()
    for tag in soup.find_all(DANGEROUS_TAGS):
        tag.decompose()
    for tag in soup.find_all(True):
        for attr in list(tag.attrs):
            value = tag.attrs[attr]
            text = " ".join(value) if isinstance(value, list) else str(value)
            if (
                attr.lower().startswith("on")
                or attr.lower() in {"style", "srcdoc", "formaction"}
                or re.match(r"\s*(javascript|vbscript|data):", text, re.IGNORECASE)
            ):
                del tag.attrs[attr]
    return soup


def canonical_url(raw: str) -> str | None:
    """Read <link rel=canonical> / og:url from the *original* HTML (never fetched)."""
    soup = BeautifulSoup(raw, "lxml")
    candidates: list[str] = []
    link = soup.find("link", rel="canonical")
    if isinstance(link, Tag) and link.get("href"):
        candidates.append(str(link["href"]))
    og = soup.find("meta", property="og:url")
    if isinstance(og, Tag) and og.get("content"):
        candidates.append(str(og["content"]))
    for url in candidates:
        if urlparse(url).scheme in {"http", "https"} and len(url) <= 2048:
            return url
    return None


# ----------------------------------------------------------------- text extraction
def inline_text(node: Tag) -> str:
    parts: list[str] = []
    for child in node.children:
        if isinstance(child, Comment):
            continue
        if isinstance(child, NavigableString):
            parts.append(_WS.sub(" ", str(child)))
            continue
        if not isinstance(child, Tag):
            continue
        name = child.name
        if name == "br":
            parts.append("\n")
        elif name == "u":
            inner = inline_text(child).strip(" ")
            parts.append(f"<u>{inner}</u>" if inner else "")
        elif name == "ruby":
            rt = " ".join(r.get_text(strip=True) for r in child.find_all("rt"))
            for extra in child.find_all(["rt", "rp"]):
                extra.extract()
            base = inline_text(child).strip(" ")
            parts.append(f"<ruby>{base}<rt>{rt}</rt></ruby>" if rt else base)
        elif name in BLOCK_TAGS:
            parts.append("\n" + inline_text(child) + "\n")
        else:
            parts.append(inline_text(child))
    return "".join(parts)


def tidy(text: str) -> str:
    lines = [line.strip(" ") for line in text.split("\n")]
    out: list[str] = []
    for line in lines:
        if line or (out and out[-1]):
            out.append(line)
    return "\n".join(out).strip("\n")


# ----------------------------------------------------------------- dethitiengnhat
_QS_ID = re.compile(r"^QS(?P<n>\d+)(?P<k>[1-6])$")
_AS_ID = re.compile(r"^AS(?P<n>\d+)$")
_TYPE_ID = re.compile(r"^type(?P<n>\d+)$")
_POINTS_ID = re.compile(r"^diemso(?P<n>\d+)$")
_OPTION_PREFIX = re.compile(r"^\s*(?P<mark>(?:不正解|正解)\s*[:：]\s*)?(?:[1-6１-６]\s*[\)）]\s*)?")
_NUMBER_PREFIX = re.compile(r"^\s*(?P<n>[0-9０-９]{1,3})\s*[\.．]\s*")
TYPE_CODES = {"1": "vocabulary", "2": "grammar", "3": "reading", "4": "listening"}


class DethitiengnhatHtmlAdapter:
    """Parses the exam page layout of dethitiengnhat.com as observed on 2026-11-10
    (``/jlpt/N3/{n}/1`` and ``/jlpt/N3/{n}/3``):

    * ``div.big_item``        問題 heading
    * ``div.question_content`` reading passage, shared by the following questions
    * ``div.question_list``   question text (``.japanese-reader-content``)
    * ``div.answers#QS{n}{k}`` option *k* of question *n*; after the site's "Tính Điểm" the
      chosen option text is prefixed with ``正解:`` (right) or ``不正解:`` (wrong) and the
      correct option with ``正解:``
    * ``div#AS{n}`` hidden answer key, ``div#type{n}`` 1 vocab / 2 grammar / 3 reading /
      4 listening, ``div#diemso{n}`` points (0 = example)
    """

    name = "dethitiengnhat_html"

    @staticmethod
    def detect(soup: BeautifulSoup) -> bool:
        return bool(
            soup.select("div.question_list")
            and soup.find("div", id=_AS_ID)
            and soup.find("div", id=_QS_ID)
        )

    def parse(self, raw: str) -> ParseResult:
        soup = sanitize(raw)
        if not self.detect(soup):
            raise UnsupportedInputError(
                "unsupported_layout",
                "HTML không khớp cấu trúc trang Dethitiengnhat đã kiểm chứng.",
            )
        notes: list[Issue] = []
        level = soup.find(id="trinhdothi")
        if isinstance(level, Tag) and level.get_text(strip=True) not in {"", "N3"}:
            notes.append(
                Issue(
                    severity="warning",
                    code="level_mismatch",
                    message=(
                        f"Trang ghi cấp độ {level.get_text(strip=True)}; ứng dụng chỉ hỗ trợ N3."
                    ),
                )
            )

        passages: list[DraftPassage] = []
        questions: list[dict[str, object]] = []
        current: dict[str, object] | None = None
        section_type: QuestionType | None = None
        passage_key: str | None = None
        any_marks = False

        for el in soup.find_all("div"):
            classes: list[str] = list(el.get("class") or [])
            el_id = str(el.get("id") or "")
            if "big_item" in classes:
                section_type = guess_question_type(el.get_text(" ", strip=True))
                passage_key = None
            elif "question_content" in classes:
                reader = el.select_one(".japanese-reader-content") or el
                passage_text = tidy(inline_text(reader))
                if passage_text:
                    passage_key = f"p{len(passages) + 1}"
                    passages.append(DraftPassage(key=passage_key, content=passage_text))
            elif "question_list" in classes:
                reader = el.select_one(".japanese-reader-content") or el
                current = {
                    "text": tidy(inline_text(reader)),
                    "section_type": section_type,
                    "passage_key": passage_key,
                    "options": {},
                    "marks": {},
                    "checked": None,
                    "number": None,
                    "key": None,
                    "type_code": None,
                    "points": None,
                }
                questions.append(current)
            elif current is not None and (m := _QS_ID.match(el_id)) and "answers" in classes:
                text = tidy(inline_text(el))
                pm = _OPTION_PREFIX.match(text)
                body = text[pm.end() :] if pm else text
                k = int(m["k"])
                current["number"] = current["number"] or int(m["n"])
                current["options"][k] = clean_option(body)  # type: ignore[index]
                if pm and pm["mark"]:
                    any_marks = True
                    current["marks"][k] = "ng" if pm["mark"].startswith("不") else "ok"  # type: ignore[index]
                label = el.find_parent("label")
                radio = label.find("input", attrs={"type": "radio"}) if label else None
                if isinstance(radio, Tag) and radio.has_attr("checked"):
                    current["checked"] = k
            elif current is not None and (m := _AS_ID.match(el_id)):
                current["number"] = int(m["n"])
                key = el.get_text(strip=True)
                current["key"] = int(key) if key.isdigit() else None
            elif current is not None and (m := _TYPE_ID.match(el_id)):
                current["type_code"] = el.get_text(strip=True)
            elif current is not None and (m := _POINTS_ID.match(el_id)):
                try:
                    current["points"] = float(el.get_text(strip=True))
                except ValueError:
                    current["points"] = None

        drafts = [self._to_draft(q, any_marks) for q in questions]
        if not drafts:
            notes.append(
                Issue(severity="error", code="no_questions", message="Không tìm thấy câu hỏi.")
            )
        if drafts and not any_marks:
            notes.append(
                Issue(
                    severity="info",
                    code="not_scored",
                    message=(
                        "Trang chưa được chấm (chưa bấm “Tính Điểm”) nên không có lựa chọn của "
                        "bạn. Muốn tạo bài làm, hãy chấm điểm trên trang rồi sao chép lại HTML."
                    ),
                )
            )
        heading = soup.find("h3")
        title = _WS.sub(" ", heading.get_text(" ", strip=True)) if isinstance(heading, Tag) else ""
        types = [d.question_type for d in drafts if d.include]
        content = DraftContent(
            exam=DraftExam(title=f"Dethitiengnhat — {title}" if title else "", category=None),
            passages=passages,
            questions=drafts,
        )
        content.exam.category = _category(drafts) or category_for_types(types)
        return ParseResult(adapter=self.name, content=content, notes=notes)

    @staticmethod
    def _to_draft(q: dict[str, object], any_marks: bool) -> DraftQuestion:
        notes: list[ParserNote] = []
        options_map: dict[int, str] = q["options"]  # type: ignore[assignment]
        options = [options_map[k] for k in sorted(options_map)]
        if sorted(options_map) != list(range(1, len(options_map) + 1)):
            notes.append(
                ParserNote(code="option_order", message="Thiếu hoặc lệch thứ tự lựa chọn.")
            )
        if len(options) != 4:
            notes.append(
                ParserNote(
                    code="option_count", message=f"Có {len(options)} lựa chọn (thường là 4)."
                )
            )
        number = q["number"] if isinstance(q["number"], int) else None
        text = str(q["text"])
        nm = _NUMBER_PREFIX.match(text)
        if nm and number is not None and int(nm["n"].translate(_FW)) == number:
            text = text[nm.end() :]
        site_key = q["key"] if isinstance(q["key"], int) else None
        if site_key is not None and not 1 <= site_key <= max(len(options), 1):
            notes.append(
                ParserNote(code="invalid_key", message="Đáp án của trang nằm ngoài lựa chọn.")
            )
            site_key = None

        marks: dict[int, str] = q["marks"]  # type: ignore[assignment]
        user_answer: int | None = q["checked"] if isinstance(q["checked"], int) else None
        ok = [k for k, v in marks.items() if v == "ok"]
        ng = [k for k, v in marks.items() if v == "ng"]
        if marks:
            if len(ok) == 1 and len(ng) <= 1:
                user_answer = user_answer or (ng[0] if ng else ok[0])
                if site_key is not None and ok[0] != site_key:
                    notes.append(
                        ParserNote(
                            code="key_conflict", message="Đáp án ẩn và ký hiệu 正解 khác nhau."
                        )
                    )
            else:
                notes.append(
                    ParserNote(code="ambiguous_markers", message="Ký hiệu 正解/不正解 không rõ.")
                )

        type_code = TYPE_CODES.get(str(q["type_code"] or ""))
        section_type = q["section_type"]
        qtype = (
            section_type
            if isinstance(section_type, QuestionType)
            else {"grammar": QuestionType.GRAMMAR_FORM, "reading": QuestionType.READING_SHORT}.get(
                type_code or "", QuestionType.OTHER
            )
        )
        points = q["points"] if isinstance(q["points"], float) else None
        is_example = points == 0 or bool(EXAMPLE_RE.match(text))
        include = not is_example and type_code != "listening"
        if is_example:
            notes.append(
                ParserNote(code="example", message="Câu ví dụ (0 điểm) — mặc định bỏ qua.")
            )
        if type_code == "listening":
            notes.append(
                ParserNote(
                    code="listening_unsupported", message="Câu nghe chưa được hỗ trợ (cần audio)."
                )
            )
        if not text:
            notes.append(ParserNote(code="empty_text", message="Không đọc được nội dung câu hỏi."))
        return DraftQuestion(
            key=new_key(),
            include=include,
            question_number=number if number and number <= 999 else None,
            question_type=qtype,
            question_text=text,
            options=options[:6],
            passage_key=q["passage_key"] if isinstance(q["passage_key"], str) else None,
            site_answer=site_key,
            user_answer=user_answer if any_marks or user_answer else None,
            correct_answer=site_key,
            parser_notes=notes,
            # Layout verified against the real page → no blanket review flag; the user still
            # confirms every answer before it becomes verified.
            points=points,
            is_example=is_example,
        )


_FW = str.maketrans("０１２３４５６７８９", "0123456789")


def _category(drafts: list[DraftQuestion]) -> ExamCategory | None:
    return category_for_types([d.question_type for d in drafts if d.include])


# ----------------------------------------------------------------- generic
class GenericHtmlAdapter:
    """Unknown layout: sanitise, convert to text, run the text parser, flag everything."""

    name = "generic_html"

    def parse(self, raw: str) -> ParseResult:
        soup = sanitize(raw)
        root = soup.body or soup
        text = tidy(inline_text(root)) if isinstance(root, Tag) else ""
        result = GenericTextAdapter(name=self.name).parse(text)
        for q in result.content.questions:
            q.parser_notes.append(
                ParserNote(
                    code="unverified_layout",
                    message="Cấu trúc HTML chưa được kiểm chứng — hãy kiểm tra câu này.",
                )
            )
        result.notes.insert(
            0,
            Issue(
                severity="warning",
                code="generic_html",
                message=(
                    "Không nhận ra cấu trúc trang; dữ liệu được tách theo văn bản và cần kiểm tra."
                ),
            ),
        )
        return result


def parse_html(raw: str, source_url: str | None) -> ParseResult:
    soup = sanitize(raw)
    if DethitiengnhatHtmlAdapter.detect(soup):
        return DethitiengnhatHtmlAdapter().parse(raw)
    result = GenericHtmlAdapter().parse(raw)
    host = urlparse(source_url).hostname if source_url else None
    if host and host.endswith("dethitiengnhat.com"):
        result.notes.insert(
            0,
            Issue(
                severity="warning",
                code="dethitiengnhat_layout_mismatch",
                message=(
                    "URL là Dethitiengnhat nhưng HTML không khớp cấu trúc đã kiểm chứng "
                    "(có thể bạn chỉ sao chép một phần). Đang dùng bộ tách chung."
                ),
            ),
        )
    return result
