"""Read-only scanner and validator for Git-tracked N3 Sensei content-pack assets."""

import hashlib
import json
import subprocess
import uuid
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

CONTENT_FORMAT = "n3sensei-content-pack"
CONTENT_FORMAT_VERSION = 1
ITEM_TYPES = ("vocabulary", "kanji", "grammar")
ITEM_NAMESPACE = uuid.UUID("661620c4-e96a-419e-9e08-4779e11ed88c")
MAX_PACK_BYTES = 20 * 1024 * 1024

# The source row and PDF page place one verified example under an existing
# stable Kanji item, while the Android asset leaves it unreferenced. Keep this
# narrowly scoped Web-side mapping and its evidence here; never edit Android.
VERIFIED_EXAMPLE_LINK_OVERRIDES: tuple[dict[str, Any], ...] = (
    {
        "pack_id": "n3-kanji",
        "item_type": "kanji",
        "item_source_ref": "n3k-k04f38",
        "example_source_ref": "n3k-x-10-002",
        "example_source_id": "n3pdf-kanji",
        # Validate the source record without embedding its private-use learning text
        # in this publicly hosted Web repository.
        "expected_payload_hash": "7f9d06e1273869ea63e7065e7cb2d28ff2e031f5c84d4b56b710dc9ca05ca690",
        "evidence": {
            "source_file": "N3.pdf",
            "source_page": 197,
            "mapping_file": "docs/data/n3-kanji-words.tsv",
            "mapping_row": "n3k-l10 / 第10 / card 2 / example n3k-x-10-002",
            "mapping_note": "regrouped-from:伸",
        },
    },
)


class SourceValidationError(ValueError):
    """A source snapshot is malformed or violates stable-ID/foreign-key rules."""


@dataclass(frozen=True, slots=True)
class SourceRecord:
    source_ref: str
    entity_type: str
    order_index: int
    source_id: str
    source_name: str
    source_license: str
    payload: dict[str, Any]
    content_hash: str
    example_refs: tuple[str, ...]

    @property
    def stable_id(self) -> uuid.UUID:
        return uuid.uuid5(ITEM_NAMESPACE, f"{self.pack_id}:{self.entity_type}:{self.source_ref}")

    pack_id: str


@dataclass(frozen=True, slots=True)
class SourceLesson:
    source_id: str
    number: int
    order_index: int
    title: str
    description: str | None
    content_items: tuple[SourceRecord, ...]

    @property
    def stable_id(self) -> uuid.UUID:
        return uuid.uuid5(ITEM_NAMESPACE, f"lesson:{self.pack_id}:{self.source_id}")

    pack_id: str


@dataclass(frozen=True, slots=True)
class SourceExample:
    source_ref: str
    source_id: str
    payload: dict[str, Any]
    content_hash: str

    @property
    def stable_id(self) -> uuid.UUID:
        return uuid.uuid5(ITEM_NAMESPACE, f"example:{self.pack_id}:{self.source_ref}")

    pack_id: str


@dataclass(frozen=True, slots=True)
class SourcePack:
    pack_id: str
    title: str
    jlpt_level: str
    version: int
    relative_path: str
    source_hash: str
    source_commit_sha: str
    source_manifest_hash: str
    blocked_count: int
    lessons: tuple[SourceLesson, ...]
    examples: tuple[SourceExample, ...]


@dataclass(frozen=True, slots=True)
class SourceSnapshot:
    commit_sha: str
    manifest_hash: str
    packs: tuple[SourcePack, ...]


def canonical_hash(value: Any) -> str:
    body = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def _git(root: Path, *args: str) -> str:
    try:
        result = subprocess.run(
            ["git", "-C", str(root), *args],
            check=True,
            capture_output=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise SourceValidationError(f"Không đọc được Git metadata chỉ đọc: {exc}") from exc
    return result.stdout.decode("utf-8", errors="strict").strip()


def scan_source(
    source_dir: Path, approved_private_sources: set[tuple[str, str]] | None = None
) -> SourceSnapshot:
    root = source_dir.resolve(strict=True)
    if not root.is_dir():
        raise SourceValidationError(
            "ANDROID_LEARNING_SOURCE_DIR phải là thư mục repository Android"
        )
    git_root = Path(_git(root, "rev-parse", "--show-toplevel")).resolve(strict=True)
    if git_root != root:
        raise SourceValidationError("Nguồn phải trỏ đúng Git root của N3 Sensei")
    commit = _git(root, "rev-parse", "HEAD")
    tracked = _git(root, "ls-files", "-z", "--", "app/src/main/assets/content/*.json")
    paths = sorted(path for path in tracked.split("\x00") if path)
    if not paths:
        raise SourceValidationError("Git không có JSON content asset nào được track")

    parsed: list[tuple[str, bytes, dict[str, Any]]] = []
    manifest_lines: list[str] = []
    for relative in paths:
        candidate = (root / relative).resolve(strict=True)
        if not candidate.is_relative_to(root) or not candidate.is_file():
            raise SourceValidationError(f"Đường dẫn asset không an toàn: {relative}")
        raw = candidate.read_bytes()
        if len(raw) > MAX_PACK_BYTES:
            raise SourceValidationError(f"Content asset vượt giới hạn 20 MiB: {relative}")
        try:
            text = raw.decode("utf-8")
            decoded = json.loads(text)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise SourceValidationError(f"JSON/UTF-8 không hợp lệ trong {relative}: {exc}") from exc
        if not isinstance(decoded, dict):
            raise SourceValidationError(f"Root JSON phải là object: {relative}")
        digest = hashlib.sha256(raw).hexdigest()
        manifest_lines.append(f"{relative}\0{digest}")
        parsed.append((relative, raw, decoded))

    manifest_hash = hashlib.sha256("\n".join(manifest_lines).encode("utf-8")).hexdigest()
    packs: list[SourcePack] = []
    seen_pack_ids: set[str] = set()
    for relative, raw, payload in parsed:
        if payload.get("format") != CONTENT_FORMAT:
            if Path(relative).name != "proverbs.json":
                raise SourceValidationError(
                    f"Asset JSON không có format content pack đã biết: {relative}"
                )
            continue
        pack = _project_pack(
            relative, raw, payload, commit, manifest_hash, approved_private_sources or set()
        )
        if pack.pack_id in seen_pack_ids:
            raise SourceValidationError(f"pack.id bị trùng trong source manifest: {pack.pack_id}")
        seen_pack_ids.add(pack.pack_id)
        packs.append(_apply_verified_example_link_overrides(pack))
    if not packs:
        raise SourceValidationError("Không tìm thấy asset đúng định dạng n3sensei-content-pack")
    return SourceSnapshot(commit, manifest_hash, tuple(packs))


def _apply_verified_example_link_overrides(pack: SourcePack) -> SourcePack:
    overrides = [row for row in VERIFIED_EXAMPLE_LINK_OVERRIDES if row["pack_id"] == pack.pack_id]
    if not overrides:
        return pack

    examples = {row.source_ref: row for row in pack.examples}
    lessons: list[SourceLesson] = []
    matched: set[str] = set()
    for lesson in pack.lessons:
        records: list[SourceRecord] = []
        for record in lesson.content_items:
            current = record
            for override in overrides:
                if record.source_ref != override["item_source_ref"]:
                    continue
                example = examples.get(override["example_source_ref"])
                if (
                    record.entity_type != override["item_type"]
                    or example is None
                    or example.source_id != override["example_source_id"]
                    or example.content_hash != override["expected_payload_hash"]
                ):
                    raise SourceValidationError(
                        "Verified example mapping no longer matches its source evidence: "
                        f"{pack.pack_id}/{record.source_ref}"
                    )
                refs = list(current.example_refs)
                if example.source_ref not in refs:
                    refs.append(example.source_ref)
                payload = dict(current.payload)
                payload["examples"] = refs
                origin = payload.get("origin")
                origin = dict(origin) if isinstance(origin, dict) else {}
                evidence = dict(override["evidence"])
                mappings = list(origin.get("webVerifiedMappings", []))
                if evidence not in mappings:
                    mappings.append(evidence)
                origin["webVerifiedMappings"] = mappings
                payload["origin"] = origin
                current = replace(
                    current,
                    payload=payload,
                    content_hash=canonical_hash(payload),
                    example_refs=tuple(refs),
                )
                matched.add(record.source_ref)
            records.append(current)
        lessons.append(replace(lesson, content_items=tuple(records)))

    expected_items = {row["item_source_ref"] for row in overrides}
    if matched != expected_items:
        raise SourceValidationError(
            f"Verified example mapping target missing: {pack.pack_id}/{expected_items - matched}"
        )
    return replace(pack, lessons=tuple(lessons))


def _clean(value: Any, location: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise SourceValidationError(f"Thiếu chuỗi bắt buộc: {location}")
    return value.strip()


def source_inventory(source_dir: Path) -> list[dict[str, Any]]:
    """Show declared source metadata from tracked assets without importing their content."""
    root = source_dir.resolve(strict=True)
    if Path(_git(root, "rev-parse", "--show-toplevel")).resolve(strict=True) != root:
        raise SourceValidationError("Nguồn phải trỏ đúng Git root")
    paths = _git(root, "ls-files", "-z", "--", "app/src/main/assets/content/*.json")
    result: list[dict[str, Any]] = []
    for relative in sorted(p for p in paths.split("\x00") if p):
        candidate = (root / relative).resolve(strict=True)
        if not candidate.is_relative_to(root) or candidate.stat().st_size > MAX_PACK_BYTES:
            raise SourceValidationError(f"Asset không an toàn: {relative}")
        data = json.loads(candidate.read_text(encoding="utf-8"))
        if data.get("format") != CONTENT_FORMAT:
            continue
        pack_id = _clean(data.get("pack", {}).get("id"), f"{relative}:pack.id")
        for row in data.get("sources", []):
            source_id = _clean(row.get("id"), f"{relative}:source.id")
            result.append(
                {
                    "pack_id": pack_id,
                    "source_id": source_id,
                    "source_name": _clean(row.get("name"), f"{relative}:source.name"),
                    "source_license": str(row.get("license") or ""),
                    "license_verified": row.get("licenseVerified") is True,
                }
            )
    return result


def _resolve_source(
    raw_id: Any, default_id: str, sources: dict[str, dict[str, Any]], location: str
) -> tuple[str, dict[str, Any]]:
    source_id = _clean(raw_id, location) if raw_id is not None else default_id
    source = sources.get(source_id)
    if source is None:
        raise SourceValidationError(f"sourceId không tồn tại: {location} → {source_id}")
    return source_id, source


def _project_pack(
    relative: str,
    raw: bytes,
    data: dict[str, Any],
    commit: str,
    manifest_hash: str,
    approved_private_sources: set[tuple[str, str]] | None = None,
) -> SourcePack:
    if data.get("formatVersion") != CONTENT_FORMAT_VERSION:
        raise SourceValidationError(f"formatVersion không hỗ trợ: {relative}")
    pack = data.get("pack")
    if not isinstance(pack, dict):
        raise SourceValidationError(f"Thiếu pack metadata: {relative}")
    pack_id = _clean(pack.get("id"), f"{relative}:pack.id")
    title = _clean(pack.get("title"), f"{relative}:pack.title")
    level = _clean(pack.get("jlptLevel") or "N3", f"{relative}:pack.jlptLevel")
    if level not in {"N1", "N2", "N3", "N4", "N5"}:
        raise SourceValidationError(f"JLPT level không hợp lệ: {relative}: {level}")
    version = pack.get("version")
    if not isinstance(version, int) or isinstance(version, bool) or version < 1:
        raise SourceValidationError(f"pack.version phải là số nguyên dương: {relative}")

    approved_private_sources = approved_private_sources or set()
    raw_sources = data.get("sources")
    if not isinstance(raw_sources, list) or not raw_sources:
        raise SourceValidationError(f"Pack không khai báo sources: {relative}")
    sources: dict[str, dict[str, Any]] = {}
    for index, row in enumerate(raw_sources):
        if not isinstance(row, dict):
            raise SourceValidationError(f"Source phải là object: {relative}:sources[{index}]")
        source_id = _clean(row.get("id"), f"{relative}:sources[{index}].id")
        if source_id in sources:
            raise SourceValidationError(f"source.id bị trùng: {relative}: {source_id}")
        sources[source_id] = row
    default_id = pack.get("defaultSourceId")
    if default_id is None:
        if len(sources) != 1:
            raise SourceValidationError(f"Pack cần defaultSourceId: {relative}")
        default_id = next(iter(sources))
    default_id = _clean(default_id, f"{relative}:pack.defaultSourceId")
    if default_id not in sources:
        raise SourceValidationError(f"defaultSourceId không tồn tại: {relative}: {default_id}")

    raw_examples = data.get("examples", [])
    if not isinstance(raw_examples, list):
        raise SourceValidationError(f"examples phải là array: {relative}")
    examples_by_ref: dict[str, dict[str, Any]] = {}
    verified_examples: list[SourceExample] = []
    blocked_count = 0
    for index, example in enumerate(raw_examples):
        if not isinstance(example, dict):
            raise SourceValidationError(f"Example phải là object: {relative}:examples[{index}]")
        ref = _clean(example.get("id"), f"{relative}:examples[{index}].id")
        if ref in examples_by_ref:
            raise SourceValidationError(f"example.id bị trùng: {relative}: {ref}")
        source_id, source = _resolve_source(
            example.get("sourceId"), default_id, sources, f"{relative}:examples[{index}].sourceId"
        )
        japanese = _clean(example.get("japanese"), f"{relative}:examples[{index}].japanese")
        examples_by_ref[ref] = example
        if (
            source.get("licenseVerified") is True
            or (pack_id, source_id) in approved_private_sources
        ):
            example_payload = {
                "japanese": japanese,
                "furigana": example.get("furigana"),
                "translationVi": example.get("translationVi"),
            }
            verified_examples.append(
                SourceExample(
                    ref, source_id, example_payload, canonical_hash(example_payload), pack_id
                )
            )
        else:
            blocked_count += 1
    safe_example_ids = {example.source_ref for example in verified_examples}

    raw_lessons = data.get("lessons")
    if not isinstance(raw_lessons, list) or not raw_lessons:
        raise SourceValidationError(f"Pack không có lessons: {relative}")
    lesson_ids: set[str] = set()
    lesson_numbers: set[int] = set()
    safe_lessons: list[SourceLesson] = []
    safe_item_ids: set[tuple[str, str]] = set()
    for lesson_index, lesson in enumerate(raw_lessons):
        if not isinstance(lesson, dict):
            raise SourceValidationError(
                f"Lesson phải là object: {relative}:lessons[{lesson_index}]"
            )
        lesson_id = _clean(lesson.get("id"), f"{relative}:lessons[{lesson_index}].id")
        lesson_title = _clean(lesson.get("title"), f"{relative}:lessons[{lesson_index}].title")
        number = lesson.get("number")
        if not isinstance(number, int) or isinstance(number, bool) or number < 1:
            raise SourceValidationError(f"Lesson number không hợp lệ: {relative}: {lesson_id}")
        if lesson_id in lesson_ids or number in lesson_numbers:
            raise SourceValidationError(
                f"Lesson id/number bị trùng: {relative}: {lesson_id}/{number}"
            )
        lesson_ids.add(lesson_id)
        lesson_numbers.add(number)
        records: list[SourceRecord] = []
        local_order = 0
        for item_type in ITEM_TYPES:
            rows = lesson.get(item_type, [])
            if not isinstance(rows, list):
                raise SourceValidationError(f"{item_type} phải là array: {relative}: {lesson_id}")
            for item_index, item in enumerate(rows):
                location = f"{relative}:lessons[{lesson_index}].{item_type}[{item_index}]"
                if not isinstance(item, dict):
                    raise SourceValidationError(f"Item phải là object: {location}")
                item_ref = _clean(item.get("id"), f"{location}.id")
                key = (item_type, item_ref)
                if key in safe_item_ids:
                    raise SourceValidationError(
                        f"Stable content ID bị trùng: {pack_id}/{item_type}/{item_ref}"
                    )
                safe_item_ids.add(key)
                source_id, source = _resolve_source(
                    item.get("sourceId"), default_id, sources, location
                )
                if item_type == "vocabulary":
                    for required in ("expression", "reading", "meaningVi"):
                        _clean(item.get(required), f"{location}.{required}")
                elif item_type == "kanji":
                    character = _clean(item.get("character"), f"{location}.character")
                    if len(character) != 1:
                        raise SourceValidationError(f"Kanji phải là một ký tự: {location}")
                else:
                    _clean(item.get("pattern"), f"{location}.pattern")
                    _clean(item.get("meaningVi"), f"{location}.meaningVi")
                    exercises = item.get("exercises", [])
                    if not isinstance(exercises, list):
                        raise SourceValidationError(f"exercises phải là array: {location}")
                    exercise_ids: set[str] = set()
                    for exercise_index, exercise in enumerate(exercises):
                        exloc = f"{location}.exercises[{exercise_index}]"
                        if not isinstance(exercise, dict):
                            raise SourceValidationError(f"Exercise phải là object: {exloc}")
                        exercise_id = _clean(exercise.get("id"), f"{exloc}.id")
                        if exercise_id in exercise_ids:
                            raise SourceValidationError(f"Exercise ID bị trùng: {exloc}")
                        exercise_ids.add(exercise_id)
                        _clean(exercise.get("prompt"), f"{exloc}.prompt")
                        options = exercise.get("options")
                        answer = exercise.get("answerIndex")
                        if not isinstance(options, list) or len(options) < 2:
                            raise SourceValidationError(f"Exercise cần ít nhất 2 options: {exloc}")
                        if any(
                            not isinstance(option, str) or not option.strip() for option in options
                        ):
                            raise SourceValidationError(
                                f"Exercise option trống/không hợp lệ: {exloc}"
                            )
                        if (
                            not isinstance(answer, int)
                            or isinstance(answer, bool)
                            or not 0 <= answer < len(options)
                        ):
                            raise SourceValidationError(f"answerIndex ngoài phạm vi: {exloc}")
                refs = item.get("examples", [])
                if not isinstance(refs, list) or any(not isinstance(ref, str) for ref in refs):
                    raise SourceValidationError(f"examples phải là danh sách ID: {location}")
                if len(set(refs)) != len(refs):
                    raise SourceValidationError(f"Item lặp example ID: {location}")
                unknown_refs = set(refs) - examples_by_ref.keys()
                if unknown_refs:
                    raise SourceValidationError(
                        f"Example FK không tồn tại tại {location}: {sorted(unknown_refs)}"
                    )
                if (
                    source.get("licenseVerified") is not True
                    and (pack_id, source_id) not in approved_private_sources
                ):
                    blocked_count += 1
                    continue
                safe_payload = dict(item)
                safe_payload["examples"] = [ref for ref in refs if ref in safe_example_ids]
                source_name = _clean(source.get("name"), f"{location}:source.name")
                source_license = _clean(source.get("license"), f"{location}:source.license")
                records.append(
                    SourceRecord(
                        source_ref=item_ref,
                        entity_type=item_type,
                        order_index=local_order,
                        source_id=source_id,
                        source_name=source_name,
                        source_license=source_license,
                        payload=safe_payload,
                        content_hash=canonical_hash(safe_payload),
                        example_refs=tuple(safe_payload["examples"]),
                        pack_id=pack_id,
                    )
                )
                local_order += 1
        if records:
            safe_lessons.append(
                SourceLesson(
                    source_id=lesson_id,
                    number=number,
                    order_index=lesson_index,
                    title=lesson_title,
                    description=lesson.get("description")
                    if isinstance(lesson.get("description"), str)
                    else None,
                    content_items=tuple(records),
                    pack_id=pack_id,
                )
            )

    return SourcePack(
        pack_id=pack_id,
        title=title,
        jlpt_level=level,
        version=version,
        relative_path=relative,
        source_hash=hashlib.sha256(raw).hexdigest(),
        source_commit_sha=commit,
        source_manifest_hash=manifest_hash,
        blocked_count=blocked_count,
        lessons=tuple(safe_lessons),
        examples=tuple(verified_examples),
    )
