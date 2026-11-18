"""Screenshot validation and normalisation.

* The type is detected from the file *content* (magic bytes + Pillow), never the extension.
* Pixel count is capped before decoding (decompression bombs) and Pillow's own guard is on.
* EXIF orientation is applied, then the image is re-encoded as lossless PNG at full
  resolution. Re-encoding drops metadata and any trailing payload: nothing in the original
  file is ever executed or served back.
"""

import hashlib
import io
from dataclasses import dataclass

from PIL import Image, ImageOps, UnidentifiedImageError

from app.core.errors import DomainValidationError

_MAGIC: list[tuple[bytes, int, str]] = [
    (b"\x89PNG\r\n\x1a\n", 0, "image/png"),
    (b"\xff\xd8\xff", 0, "image/jpeg"),
]
_PIL_TYPES = {"PNG": "image/png", "JPEG": "image/jpeg", "WEBP": "image/webp"}


@dataclass(frozen=True)
class NormalisedImage:
    detected_type: str
    png_bytes: bytes
    width: int
    height: int
    sha256: str  # of the original upload


def sniff(data: bytes) -> str | None:
    for magic, offset, mime in _MAGIC:
        if data[offset : offset + len(magic)] == magic:
            return mime
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return None


def normalise(data: bytes, *, filename: str, max_pixels: int) -> NormalisedImage:
    detected = sniff(data)
    if detected is None:
        raise DomainValidationError(
            f"“{filename}” không phải ảnh PNG, JPEG hoặc WEBP hợp lệ.",
            details={"file": filename, "reason": "unsupported_type"},
        )
    Image.MAX_IMAGE_PIXELS = max_pixels
    try:
        with Image.open(io.BytesIO(data)) as probe:
            fmt = probe.format or ""
            width, height = probe.size
            if _PIL_TYPES.get(fmt) != detected:
                raise DomainValidationError(
                    f"Nội dung “{filename}” không khớp định dạng ảnh.",
                    details={"file": filename, "reason": "type_mismatch"},
                )
            if width * height > max_pixels:
                raise DomainValidationError(
                    f"“{filename}” quá lớn ({width}×{height} px).",
                    details={"file": filename, "reason": "too_many_pixels"},
                )
            probe.verify()
        with Image.open(io.BytesIO(data)) as img:
            img.load()
            upright = ImageOps.exif_transpose(img)
            if upright.mode not in {"RGB", "L"}:
                # Flatten transparency onto white so text stays readable for OCR.
                rgba = upright.convert("RGBA")
                canvas = Image.new("RGB", rgba.size, (255, 255, 255))
                canvas.paste(rgba, mask=rgba.split()[-1])
                upright = canvas
            out = io.BytesIO()
            upright.save(out, format="PNG", optimize=False)
            w, h = upright.size
    except DomainValidationError:
        raise
    except (
        UnidentifiedImageError,
        OSError,
        SyntaxError,
        ValueError,
        Image.DecompressionBombError,
    ) as exc:
        raise DomainValidationError(
            f"Không đọc được ảnh “{filename}” (tệp hỏng hoặc không hỗ trợ).",
            details={"file": filename, "reason": "corrupt"},
        ) from exc
    return NormalisedImage(
        detected_type=detected,
        png_bytes=out.getvalue(),
        width=w,
        height=h,
        sha256=hashlib.sha256(data).hexdigest(),
    )
