"""Adapter tests on self-authored fixtures (no database)."""

from app.database.enums import ExamCategory, QuestionType
from app.imports.adapters.html import (
    DethitiengnhatHtmlAdapter,
    GenericHtmlAdapter,
    canonical_url,
    parse_html,
    sanitize,
)
from app.imports.adapters.text import GenericTextAdapter
from tests.conftest import fixture_text


def _codes(q) -> set[str]:  # type: ignore[no-untyped-def]
    return {n.code for n in q.parser_notes}


# ----------------------------------------------------------------- text (Mode A)
def test_text_multiple_questions_fullwidth_and_answers() -> None:
    r = GenericTextAdapter().parse(fixture_text("text_basic.txt"))
    c = r.content
    assert c.exam.title == "N3 模擬テスト（自作）第１回"
    assert [q.question_number for q in c.questions] == [1, 2, 3]
    q1, q2, q3 = c.questions
    # Full-width markers parsed; Japanese text and inline underline kept verbatim
    assert q1.question_text == "この川は<u>深い</u>ので、泳がないでください。"
    assert q1.options == ["ふかい", "ふるい", "ひくい", "あさい"]
    assert q1.question_type == QuestionType.KANJI_READING
    assert (q1.site_answer, q1.correct_answer, q1.answer_confirmed) == (1, 1, False)
    # Inline options + user's own answer kept apart from the key
    assert q2.options == ["ひろば", "こうじょう", "ひろじょう", "こうば"]
    assert (q2.site_answer, q2.user_answer, q2.correct_answer) == (None, 3, None)
    # Full-width letter labels Ａ–Ｄ, letter answer
    assert q3.question_type == QuestionType.ORTHOGRAPHY
    assert q3.options[0] == "飲みます"
    assert q3.site_answer == 1
    assert c.exam.category == ExamCategory.VOCABULARY
    assert not any(q.answer_confirmed for q in c.questions)


def test_text_reading_passage_shared_and_markers() -> None:
    c = GenericTextAdapter().parse(fixture_text("text_reading.txt")).content
    assert len(c.passages) == 1
    passage = c.passages[0]
    assert "散歩（さんぽ）" in passage.content  # furigana kept
    assert "\n" in passage.content  # line breaks kept
    q24, q25 = c.questions
    assert q24.passage_key == q25.passage_key == passage.key
    assert q24.question_type == QuestionType.READING_SHORT
    # dethitiengnhat result markers: 正解 → site key, 不正解 → the user's (wrong) choice
    assert (q24.site_answer, q24.user_answer) == (1, 2)
    assert "answer_from_markers" in _codes(q24)
    assert q24.options[0] == "木の色が季節で変わるから"  # marker stripped from option text
    assert (q25.site_answer, q25.user_answer) == (None, None)


def test_text_uncertain_input_is_flagged() -> None:
    raw = "1. 文がある\n1) ひとつ\n2) ふたつ\n3) みっつ\nこれは説明の文です。\n問2 番号の形が違う\nA. あ\nB. い"
    c = GenericTextAdapter().parse(raw).content
    assert "option_count" in _codes(c.questions[0])
    assert c.questions[1].question_number == 2


def test_text_answer_key_block() -> None:
    raw = "1. 問題一\n1) あ\n2) い\n3) う\n4) え\n2. 問題二\n1) か\n2) き\n3) く\n4) け\n解答\n1. 3\n2. 4"
    c = GenericTextAdapter().parse(raw).content
    assert [q.site_answer for q in c.questions] == [3, 4]


def test_text_no_questions_reports_error() -> None:
    r = GenericTextAdapter().parse("ただの文章です。\n問題はありません。")
    assert r.content.questions == []
    assert any(n.code == "no_questions" and n.severity == "error" for n in r.notes)


def test_text_does_not_change_kana_or_long_vowel() -> None:
    raw = "1. コーヒーとこーひー、ｶﾀｶﾅ\n1) アイス\n2) あいす\n3) ｱｲｽ\n4) アイスー"
    q = GenericTextAdapter().parse(raw).content.questions[0]
    assert q.question_text == "コーヒーとこーひー、ｶﾀｶﾅ"
    assert q.options == ["アイス", "あいす", "ｱｲｽ", "アイスー"]


def test_ocr_mode_flags_every_question() -> None:
    raw = "1. 文\n1) あ\n2) い\n3) う\n4) え"
    q = GenericTextAdapter(name="ocr_text", from_ocr=True).parse(raw).content.questions[0]
    assert "ocr_source" in _codes(q)


# ----------------------------------------------------------------- HTML (Mode B)
def test_dethitiengnhat_layout_scored_page() -> None:
    raw = fixture_text("dethitiengnhat_like_scored.html")
    r = parse_html(raw, None)
    assert r.adapter == "dethitiengnhat_html"
    c = r.content
    assert c.exam.title == "Dethitiengnhat — Đề Thi Thử JLPT N3 /99"
    assert [q.question_number for q in c.questions] == [1, 2, 3, 4, 5, 6]
    ex, q2, q3, q4, q5, q6 = c.questions
    # Example question (0 points) excluded by default
    assert ex.is_example and not ex.include
    # Number prefix removed, underline + ruby preserved as safe inline markup
    assert q2.question_text == "雨が降っている（　　）、試合は<u>中止</u>になった。"
    assert q3.question_text == "彼は<ruby>約束<rt>やくそく</rt></ruby>を守る（　　）人だ。"
    assert q2.options == ["のに", "ので", "ながら", "ばかりか"]
    # Three distinct answers
    assert (q2.site_answer, q2.user_answer, q2.correct_answer) == (2, 1, 2)
    assert (q3.site_answer, q3.user_answer) == (1, 1)  # only 正解 shown → user was right
    assert (q4.site_answer, q4.user_answer) == (1, None)  # unanswered on the site
    assert not any(q.answer_confirmed for q in c.questions)
    # Passage with <br><br> → paragraph break, shared by both reading questions
    assert len(c.passages) == 1
    assert c.passages[0].content == (
        "私の町の図書館は、去年から夜九時まで開くようになった。\n\n"
        "仕事が終わってから本を借りに行けるので、とても便利（べんり）になった。"
    )
    assert q5.passage_key == q6.passage_key == c.passages[0].key
    assert q5.question_type == QuestionType.READING_SHORT
    assert q2.question_type == QuestionType.GRAMMAR_FORM
    assert c.exam.category == ExamCategory.GRAMMAR
    assert not any(n.code == "not_scored" for n in r.notes)


def test_malicious_html_is_neutralised() -> None:
    raw = fixture_text("dethitiengnhat_like_scored.html")
    soup = sanitize(raw)
    html = str(soup)
    for needle in ("<script", "alert(", "onload", "onclick", "onerror", "onmouseover",
                   "javascript:", "<iframe", "<style", "document.cookie"):  # fmt: skip
        assert needle not in html, needle
    content = DethitiengnhatHtmlAdapter().parse(raw).content
    dump = content.model_dump_json()
    assert "document.cookie" not in dump
    assert "alert" not in dump


def test_canonical_url_is_read_not_fetched() -> None:
    raw = fixture_text("dethitiengnhat_like_scored.html")
    assert canonical_url(raw) == "https://dethitiengnhat.com/jlpt/N3/99/3"
    assert canonical_url('<link rel="canonical" href="javascript:alert(1)">') is None


def test_unscored_page_reports_missing_user_answers() -> None:
    raw = fixture_text("dethitiengnhat_like_scored.html")
    for mark in ("不正解:　", "正解:　"):
        raw = raw.replace(mark, "")
    r = DethitiengnhatHtmlAdapter().parse(raw)
    assert any(n.code == "not_scored" for n in r.notes)
    assert all(q.user_answer is None for q in r.content.questions)
    assert r.content.questions[1].site_answer == 2  # hidden key still read


def test_generic_html_flags_everything() -> None:
    r = parse_html(fixture_text("generic.html"), "https://example.com/q")
    assert r.adapter == "generic_html"
    assert r.notes[0].code == "generic_html"
    qs = r.content.questions
    assert len(qs) == 2
    assert qs[0].question_text == "来週の会議は<u>延期</u>になりました。"
    assert qs[0].site_answer == 1
    assert qs[1].options == ["あいています", "あけています", "ひらいでいます", "しまっています"]
    assert all("unverified_layout" in _codes(q) for q in qs)
    assert "evil.example" not in r.content.model_dump_json()


def test_dethitiengnhat_url_with_unknown_layout_warns() -> None:
    r = parse_html(fixture_text("generic.html"), "https://dethitiengnhat.com/jlpt/N3/1/1")
    assert r.notes[0].code == "dethitiengnhat_layout_mismatch"
    assert GenericHtmlAdapter.name == r.adapter


def test_text_unrecognised_lines_are_reported_not_dropped_silently() -> None:
    raw = (
        "1. 文がある\n1) ひとつ\n2) ふたつ\n3) みっつ\n4) よっつ\nこれは説明の文です。\n問2 次の文"
    )
    r = GenericTextAdapter().parse(raw)
    ignored = [n for n in r.notes if n.code == "ignored_lines"]
    assert ignored and "これは説明の文です。" in ignored[0].data["lines"]  # type: ignore[index]
