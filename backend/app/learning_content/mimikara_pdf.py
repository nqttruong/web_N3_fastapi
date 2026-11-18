"""Read a user supplied, text based Mimikara PDF without touching Android assets.

The source is a single landscape-like spreadsheet printed into 19 very narrow
column groups on one A4 page.  Parse coordinates, rather than pdftotext's
reading order, which interleaves unrelated rows from those groups.
"""

import hashlib
import subprocess
import xml.etree.ElementTree as ET
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

from app.learning_content.source import SourceValidationError

PACK_ID = "mimikara-n3-pdf-private"
SOURCE_ID = "vti-mirai-mimikara-n3-pdf"
PDF_FILENAME = (
    "[VTI Mirai share] 140 - 880 TỪ VỰNG MIMIKARA N3 MINATO.xlsx - TU VUNG MIMIKARA N3.pdf"
)
# Original source lesson boundaries verified against the N3 Sensei content asset.
LESSON_ENDS = (120, 220, 298, 410, 510, 550, 590, 635, 715, 795, 845, 880)
MAX_PDF_BYTES = 10 * 1024 * 1024


@dataclass(frozen=True, slots=True)
class PdfWord:
    number: int
    expression: str
    reading: str | None
    meaning_vi: str
    lesson_number: int
    page: int = 1


def pdf_digest(path: Path) -> str:
    if not path.is_file() or path.stat().st_size > MAX_PDF_BYTES:
        raise SourceValidationError("PDF không tồn tại hoặc vượt giới hạn 10 MiB")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def extract_words(path: Path) -> tuple[str, tuple[PdfWord, ...]]:
    """Fail closed on changed layout, missing rows, or ambiguous coordinates."""
    digest = pdf_digest(path)
    try:
        output = subprocess.run(
            ["pdftotext", "-bbox", str(path), "-"],
            capture_output=True,
            check=True,
            timeout=20,
        ).stdout
        root = ET.fromstring(output)
    except (OSError, subprocess.SubprocessError, ET.ParseError) as exc:
        raise SourceValidationError(f"Không trích xuất được PDF text: {exc}") from exc
    pages = [element for element in root.iter() if element.tag.endswith("page")]
    if len(pages) != 1:
        raise SourceValidationError("Parser hiện chỉ hỗ trợ bố cục PDF một trang đã xác minh")
    words = [
        (float(node.attrib["xMin"]), float(node.attrib["yMin"]), node.text or "")
        for node in pages[0].iter()
        if node.tag.endswith("word")
    ]
    starts = sorted(x for x, y, value in words if 57.3 < y < 58.4 and value == "STT")
    if len(starts) != 19:
        raise SourceValidationError("Bố cục bảng PDF thay đổi: cần 19 nhóm cột STT")
    headers: list[list[tuple[float, str]]] = []
    for index, start in enumerate(starts):
        end = starts[index + 1] if index + 1 < len(starts) else 595.0
        names = [(x, value) for x, y, value in words if 57.3 < y < 58.4 and start <= x < end]
        expected = (
            ["STT", "Kanji", "Meaning"] if index == 10 else ["STT", "Kanji", "Hiragana", "Meaning"]
        )
        if [value for _, value in names] != expected:
            raise SourceValidationError(f"Cột PDF không đúng bố cục tại nhóm {index + 1}")
        headers.append(names)

    cells: dict[tuple[int, int, int], list[str]] = defaultdict(list)
    for x, y, value in words:
        if not 58.45 <= y <= 130.6:
            continue
        group = max((i for i, start in enumerate(starts) if x >= start - 0.5), default=None)
        if group is None:
            continue
        row = round((y - 58.629932) / 1.204107)
        field = max(
            (i for i, (position, _) in enumerate(headers[group]) if x >= position - 0.15), default=0
        )
        if not 0 <= row < 60:
            raise SourceValidationError("Dòng PDF nằm ngoài vùng dữ liệu dự kiến")
        cells[group, row, field].append(value)

    result: dict[int, PdfWord] = {}
    for group, names in enumerate(headers):
        for row in range(60):
            values = [" ".join(cells[group, row, field]).strip() for field in range(len(names))]
            if not values[0]:
                if any(values[1:]):
                    raise SourceValidationError("Dòng PDF thiếu STT")
                continue
            if not values[0].isdigit():
                raise SourceValidationError(f"STT không hợp lệ: {values[0]}")
            number = int(values[0])
            if number in result:
                raise SourceValidationError(f"STT trùng: {number}")
            fields = dict(zip((name for _, name in names), values, strict=True))
            if not fields["Kanji"] or not fields["Meaning"]:
                raise SourceValidationError(f"Thiếu từ hoặc nghĩa tại STT {number}")
            lesson_number = next((i for i, end in enumerate(LESSON_ENDS, 1) if number <= end), 0)
            if not lesson_number:
                raise SourceValidationError(f"STT vượt phạm vi nguồn: {number}")
            result[number] = PdfWord(
                number,
                fields["Kanji"],
                fields.get("Hiragana") or None,
                fields["Meaning"],
                lesson_number,
            )
    if set(result) != set(range(1, 881)):
        raise SourceValidationError("PDF không còn đủ 880 STT liên tục; dừng để tránh nhập thiếu")
    return digest, tuple(result[number] for number in sorted(result))
