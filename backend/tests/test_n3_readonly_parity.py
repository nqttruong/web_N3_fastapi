"""Read-only parity checks against the configured Android source repository.

These tests scan source files only and intentionally do not request the DB
fixtures, so they neither write to Android nor recreate PostgreSQL databases.
"""

import csv
import json
import re
from collections import Counter
from pathlib import Path

import pytest

from app.core.config import get_settings
from app.learning_content.source import scan_source


def android_root() -> Path:
    root = get_settings().android_learning_source_dir
    if root is None or not root.is_dir():
        pytest.skip("Configured Android source is unavailable; parity scan is read-only")
    return root


def read_pack(root: Path, name: str) -> dict[str, object]:
    path = root / "app/src/main/assets/content" / name
    return json.loads(path.read_text(encoding="utf-8"))


def flatten(pack: dict[str, object], entity: str) -> list[dict[str, object]]:
    return [
        row
        for lesson in pack["lessons"]  # type: ignore[index,union-attr]
        for row in lesson[entity]  # type: ignore[index]
    ]


def test_kanji_fields_and_furigana_match_android_source_tsv() -> None:
    root = android_root()
    pack = read_pack(root, "n3-kanji.json")
    kanji = flatten(pack, "kanji")
    with (root / "docs/data/n3-kanji-meanings.tsv").open(encoding="utf-8", newline="") as stream:
        source_rows = list(csv.DictReader(stream, delimiter="\t"))
    by_character = {row["kanji"]: row for row in source_rows}
    assert len(kanji) == len(source_rows) == 393
    assert len({row["id"] for row in kanji}) == 393

    def readings(value: str) -> list[str]:
        return [part.strip() for part in re.split(r"[、,，;；\s]+", value.strip()) if part.strip()]

    for row in kanji:
        source = by_character[row["character"]]
        assert row["hanViet"].casefold() == source["han_viet"].casefold()
        assert readings("、".join(row["onReadings"])) == readings(source["on"])
        assert readings("、".join(row["kunReadings"])) == readings(source["kun"])
        assert row["origin"]["pages"]

    empty_kun = [row for row in kanji if not row["kunReadings"]]
    assert len(empty_kun) == 52
    assert all(not by_character[row["character"]]["kun"] for row in empty_kun)
    examples = {row["id"]: row for row in pack["examples"]}  # type: ignore[index]
    assert all(example["furigana"] for example in examples.values())


def test_all_pdf_grammar_cards_are_classified_against_android_candidates() -> None:
    root = android_root()
    pack = read_pack(root, "n3-grammar.json")
    items = {row["id"]: row for row in flatten(pack, "grammar")}
    sources = {row["id"]: row for row in pack["sources"]}  # type: ignore[index]
    with (root / "docs/data/n3-grammar-pdf-mapping.tsv").open(
        encoding="utf-8", newline=""
    ) as stream:
        mappings = list(csv.DictReader(stream, delimiter="\t"))

    assert len(mappings) == 156
    by_card = {row["pdf_card"]: row for row in mappings}
    verified_new = [
        row
        for row in mappings
        if row["decision"] in {"mục riêng → mục mới", "liên quan, khác cách dùng → mục mới"}
    ]
    unresolved = [
        row
        for row in mappings
        if row["decision"]
        in {"trùng hoàn toàn", "trùng mẫu, khác giải thích/biến thể", "thẻ so sánh, không phải mẫu"}
    ]
    assert len(verified_new) == 64
    assert len(unresolved) == 92
    assert Counter(row["decision"] for row in unresolved) == {
        "trùng hoàn toàn": 57,
        "trùng mẫu, khác giải thích/biến thể": 24,
        "thẻ so sánh, không phải mẫu": 11,
    }
    gap_queue = Path(__file__).resolve().parents[2] / "docs/v3-1-grammar-gap-review-queue.md"
    assert (
        sum(
            bool(re.match(r"^\| \d{2}\.\d{2} ·", line))
            for line in gap_queue.read_text(encoding="utf-8").splitlines()
        )
        == 92
    )

    for row in verified_new:
        candidate = items[row["grammar_ids"]]
        assert candidate["sourceId"].startswith("n3pdf-g-")
        assert sources[candidate["sourceId"]]["licenseVerified"] is True

    for row in unresolved:
        refs = row["grammar_ids"].split()
        if row["decision"] == "thẻ so sánh, không phải mẫu":
            assert refs and all(ref in by_card for ref in refs)
            continue
        assert refs and all(ref in items for ref in refs)
        assert all(sources[items[ref]["sourceId"]]["licenseVerified"] is False for ref in refs)


def test_verified_kanji_example_link_override_has_exact_source_evidence() -> None:
    root = android_root()
    snapshot = scan_source(root)
    pack = next(row for row in snapshot.packs if row.pack_id == "n3-kanji")
    target = next(
        record
        for lesson in pack.lessons
        for record in lesson.content_items
        if record.source_ref == "n3k-k04f38"
    )
    assert "n3k-x-10-002" in target.example_refs
    assert target.payload["examples"] == list(target.example_refs)
    assert target.payload["origin"]["webVerifiedMappings"] == [
        {
            "source_file": "N3.pdf",
            "source_page": 197,
            "mapping_file": "docs/data/n3-kanji-words.tsv",
            "mapping_row": "n3k-l10 / 第10 / card 2 / example n3k-x-10-002",
            "mapping_note": "regrouped-from:伸",
        }
    ]
    assert next(
        example for example in pack.examples if example.source_ref == "n3k-x-10-002"
    ).content_hash == "7f9d06e1273869ea63e7065e7cb2d28ff2e031f5c84d4b56b710dc9ca05ca690"


def test_n3_grammar_source_scoped_private_rights_restore_original_110_without_widening() -> None:
    root = android_root()
    source_data = read_pack(root, "n3-grammar.json")
    all_items = flatten(source_data, "grammar")
    original_items = [
        row for row in all_items if re.fullmatch(r"vnjp-np-\d{3}", str(row["sourceId"]))
    ]
    original_source_ids = {str(row["sourceId"]) for row in original_items}
    expected_original_refs = {f"n3g-g{index:03d}" for index in range(1, 111)}
    expected_all_refs = {f"n3g-g{index:03d}" for index in range(1, 175)}
    linked_source_examples = [
        row
        for row in source_data["examples"]  # type: ignore[index]
        if row["sourceId"] in original_source_ids
    ]

    # The default scan remains fail-closed for the historical Android license flag.
    no_rights_snapshot = scan_source(root)
    no_rights_pack = next(row for row in no_rights_snapshot.packs if row.pack_id == "n3-grammar")
    no_rights_items = [
        record for lesson in no_rights_pack.lessons for record in lesson.content_items
    ]
    assert {record.source_ref for record in no_rights_items} == {
        f"n3g-g{index:03d}" for index in range(111, 175)
    }
    assert no_rights_pack.blocked_count == 470

    # An explicit grant is scoped to the 110 source declarations only. It does not
    # approve the separate n3-grammar-examples source (140 examples).
    allowed = {("n3-grammar", source_id) for source_id in original_source_ids}
    snapshot = scan_source(root, allowed)
    pack = next(row for row in snapshot.packs if row.pack_id == "n3-grammar")
    grammar = [record for lesson in pack.lessons for record in lesson.content_items]
    assert len(original_items) == len(original_source_ids) == 110
    assert {record.source_ref for record in grammar} == expected_all_refs
    original = [record for record in grammar if record.source_ref in expected_original_refs]
    pdf_items = [record for record in grammar if record.source_ref not in expected_original_refs]
    assert len(original) == 110
    assert len(pdf_items) == 64
    assert {record.source_id for record in original} == original_source_ids
    assert all(
        record.payload.get("pattern") and record.payload.get("structure") for record in grammar
    )
    assert all(
        record.payload.get("pattern") and record.payload.get("meaningVi") for record in original
    )
    assert all(len(record.example_refs) == 2 for record in original)
    assert len(pack.examples) == len(linked_source_examples) == 220
    assert {example.source_ref for example in pack.examples} == {
        str(row["id"]) for row in linked_source_examples
    }
    assert all(example.payload["furigana"] is None for example in pack.examples)
    assert pack.blocked_count == 140
    assert all(record.source_id.startswith("n3pdf-g-") for record in pdf_items)


def test_unverified_grammar_examples_are_individually_queued_not_published() -> None:
    root = android_root()
    pack = read_pack(root, "n3-grammar.json")
    source = next(row for row in pack["sources"] if row["id"] == "n3-grammar-examples")  # type: ignore[index]
    examples = [row for row in pack["examples"] if row.get("sourceId") == source["id"]]  # type: ignore[index,union-attr]
    queue = Path(__file__).resolve().parents[2] / "docs/v3-1-grammar-example-review-queue.md"
    queue_text = queue.read_text(encoding="utf-8")

    assert source["licenseVerified"] is False
    assert len(examples) == 140
    assert sum(line.startswith("| n3g-g") for line in queue_text.splitlines()) == 140
    for example in examples:
        assert example["id"] in queue_text
        assert example["japanese"] in queue_text
        assert "PENDING" in queue_text

    snapshot = scan_source(root)
    grammar_pack = next(row for row in snapshot.packs if row.pack_id == "n3-grammar")
    assert not grammar_pack.examples
