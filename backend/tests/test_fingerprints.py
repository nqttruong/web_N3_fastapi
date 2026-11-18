"""NFKC is used only for duplicate-detection hashes. These tests pin what it folds and what
it must keep distinct for Japanese."""

import importlib.util
from pathlib import Path

import pytest

from app.exams.fingerprints import question_content_hash, question_fingerprint

OPTS = ["あ", "い", "う", "え"]


@pytest.mark.parametrize(
    ("a", "b"),
    [
        ("ＡＢＣ　です", "ABC です"),  # full-width ASCII + ideographic space
        ("１２３", "123"),
        ("ｶﾀｶﾅ", "カタカナ"),  # half-width katakana
        ("文 です ", "文 です"),  # trailing/duplicated whitespace
    ],
)
def test_folded_variants_collide(a: str, b: str) -> None:
    assert question_fingerprint(a, OPTS) == question_fingerprint(b, OPTS)


@pytest.mark.parametrize(
    ("a", "b"),
    [
        ("あいす", "アイス"),  # hiragana vs katakana
        ("コーヒー", "コ-ヒ-"),  # 長音符 vs hyphen
        ("コーヒー", "コヒ"),
        ("会う", "合う"),  # different kanji
        ("きって", "きつて"),  # small vs large kana
        ("かき", "がき"),  # voiced mark
        ("漢字（かんじ）", "漢字"),  # furigana is content
        ("広い", "廣い"),  # old/new kanji forms are not folded
    ],
)
def test_distinct_japanese_stays_distinct(a: str, b: str) -> None:
    assert question_fingerprint(a, OPTS) != question_fingerprint(b, OPTS)


def test_options_and_passage_matter() -> None:
    assert question_fingerprint("文", ["あ", "い"]) != question_fingerprint("文", ["い", "あ"])
    import uuid

    p1, p2 = uuid.uuid4(), uuid.uuid4()
    assert question_content_hash(p1, "文", OPTS) != question_content_hash(p2, "文", OPTS)
    assert question_fingerprint("文", OPTS) == question_fingerprint("文", OPTS)


def test_matches_migration_0002_frozen_copy() -> None:
    path = Path(__file__).resolve().parents[1] / "alembic" / "versions"
    module_path = next(path.glob("0002_*.py"))
    spec = importlib.util.spec_from_file_location("m0002", module_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    for text, opts in [("ＡＢＣ　です", OPTS), ("雨が降っている（　　）", ["ので", "のに"])]:
        assert module._fingerprint(text, opts) == question_fingerprint(text, opts)
