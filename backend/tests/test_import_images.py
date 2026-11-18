"""Screenshot import (Mode C): file validation, storage safety, OCR engine handling, cleanup."""

import io
import os
import shutil
import subprocess
import uuid
from datetime import timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image, ImageDraw, ImageFont
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.imports import storage
from app.imports.cleanup import run_cleanup
from app.imports.models import ImportDraft
from app.imports.ocr import OcrAvailability, OcrError, TesseractEngine, set_engine_for_tests

OCR_TEXT = (
    "問題１ ＿＿＿のことばの読み方として最もよいものを、１・２・３・４から一つえらびなさい。\n"
    "1. この川は深いので、泳がないでください。\n1) ふかい\n2) ふるい\n3) ひくい\n4) あさい\n"
)


class FakeOcr:
    name = "fake"

    def __init__(self, text: str = OCR_TEXT, fail_on: set[int] | None = None) -> None:
        self.text = text
        self.fail_on = fail_on or set()
        self.calls: list[Path] = []

    def availability(self) -> OcrAvailability:
        return OcrAvailability(True, "fake", ["jpn"], None)

    def recognise(self, image_path: Path) -> str:
        self.calls.append(image_path)
        if len(self.calls) in self.fail_on:
            raise OcrError("boom")
        return self.text


class MissingOcr(FakeOcr):
    def availability(self) -> OcrAvailability:
        return OcrAvailability(False, "tesseract", [], "Không tìm thấy Tesseract.")


def png(width: int = 200, height: int = 100, fmt: str = "PNG", **save: object) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (width, height), "white").save(buf, format=fmt, **save)
    return buf.getvalue()


def upload(client: TestClient, files: list[tuple[str, bytes, str]], **form: str):  # type: ignore[no-untyped-def]
    return client.post(
        "/api/v1/imports/images",
        files=[("files", f) for f in files],
        data=form,
    )


def test_capabilities_reports_ocr_state(client: TestClient) -> None:
    set_engine_for_tests(MissingOcr())
    caps = client.get("/api/v1/imports/capabilities").json()["data"]
    assert caps["ocr"]["available"] is False
    assert "Tesseract" in caps["ocr"]["reason"]
    assert caps["limits"]["accepted_image_types"] == ["image/png", "image/jpeg", "image/webp"]


def test_ocr_unavailable_returns_503_and_stores_nothing(client: TestClient, test_settings) -> None:  # type: ignore[no-untyped-def]
    set_engine_for_tests(MissingOcr())
    r = upload(client, [("a.png", png(), "image/png")])
    assert r.status_code == 503
    assert r.json()["error"]["code"] == "ocr_unavailable"
    assert client.get("/api/v1/imports").json()["meta"]["total"] == 0
    root = Path(test_settings.import_storage_dir)
    assert not root.exists() or not any(root.iterdir())


def test_upload_png_jpeg_webp_in_order(client: TestClient, test_settings) -> None:  # type: ignore[no-untyped-def]
    fake = FakeOcr()
    set_engine_for_tests(fake)
    files = [
        ("1.png", png(), "image/png"),
        ("2.jpg", png(fmt="JPEG"), "image/jpeg"),
        ("3.webp", png(fmt="WEBP"), "image/webp"),
    ]
    r = upload(
        client, files, source_url="https://example.com/s", category="vocabulary", title="スクショ"
    )
    assert r.status_code == 201, r.text
    draft = r.json()["data"]
    assert draft["method"] == "images"
    assert draft["adapter"] == "ocr_text"
    assert [a["detected_type"] for a in draft["assets"]] == [
        "image/png",
        "image/jpeg",
        "image/webp",
    ]
    assert [a["position"] for a in draft["assets"]] == [0, 1, 2]
    assert all(a["ocr_status"] == "done" for a in draft["assets"])
    assert len(fake.calls) == 3
    # OCR output: every question needs review, answers never confirmed
    q = draft["content"]["questions"][0]
    assert any(n["code"] == "ocr_source" for n in q["parser_notes"])
    assert draft["status"] == "needs_review"
    # Stored files are normalised PNGs inside the storage root
    for a in draft["assets"]:
        resp = client.get(f"/api/v1/imports/{draft['id']}/assets/{a['id']}")
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "image/png"
        assert resp.headers["x-content-type-options"] == "nosniff"
        assert resp.content.startswith(b"\x89PNG")


def test_extension_is_not_trusted(client: TestClient) -> None:
    set_engine_for_tests(FakeOcr())
    r = upload(client, [("evil.png", b"<?php system($_GET['c']); ?>", "image/png")])
    assert r.status_code == 422
    assert r.json()["error"]["details"]["reason"] == "unsupported_type"
    gif = io.BytesIO()
    Image.new("RGB", (10, 10)).save(gif, format="GIF")
    assert upload(client, [("x.png", gif.getvalue(), "image/png")]).status_code == 422


def test_corrupt_image_rejected(client: TestClient) -> None:
    set_engine_for_tests(FakeOcr())
    data = png()[:60]  # valid magic, truncated body
    r = upload(client, [("broken.png", data, "image/png")])
    assert r.status_code == 422
    assert r.json()["error"]["details"]["reason"] in {"corrupt", "type_mismatch"}


def test_size_and_count_limits(client: TestClient, test_settings) -> None:  # type: ignore[no-untyped-def]
    set_engine_for_tests(FakeOcr())
    test_settings.import_max_image_bytes = 2_000
    big = png(800, 800, fmt="PNG", compress_level=0)
    r = upload(client, [("big.png", big, "image/png")])
    assert r.status_code == 413
    assert r.json()["error"]["code"] == "payload_too_large"

    test_settings.import_max_image_bytes = 10 * 1024 * 1024
    test_settings.import_max_images = 2
    r = upload(client, [(f"{i}.png", png(), "image/png") for i in range(3)])
    assert r.status_code == 422

    test_settings.import_max_images = 10
    test_settings.import_max_image_pixels = 100 * 100
    assert upload(client, [("huge.png", png(300, 300), "image/png")]).status_code == 422


def test_exif_orientation_is_applied(client: TestClient) -> None:
    set_engine_for_tests(FakeOcr())
    img = Image.new("RGB", (300, 100), "white")
    exif = img.getexif()
    exif[0x0112] = 6  # rotate 90° CW on display
    buf = io.BytesIO()
    img.save(buf, format="JPEG", exif=exif)
    draft = upload(client, [("rot.jpg", buf.getvalue(), "image/jpeg")]).json()["data"]
    asset = draft["assets"][0]
    assert (asset["width"], asset["height"]) == (100, 300)


def test_long_screenshot_keeps_resolution(client: TestClient) -> None:
    set_engine_for_tests(FakeOcr())
    draft = upload(client, [("long.png", png(1080, 12000), "image/png")]).json()["data"]
    assert (draft["assets"][0]["width"], draft["assets"][0]["height"]) == (1080, 12000)


def test_partial_and_total_ocr_failure(client: TestClient) -> None:
    set_engine_for_tests(FakeOcr(fail_on={2}))
    draft = upload(client, [("1.png", png(), "image/png"), ("2.png", png(), "image/png")]).json()[
        "data"
    ]
    assert [a["ocr_status"] for a in draft["assets"]] == ["done", "failed"]
    assert any(i["code"] == "ocr_partial" for i in draft["issues"])

    set_engine_for_tests(FakeOcr(fail_on={1}))
    failed = upload(client, [("1.png", png(), "image/png")]).json()["data"]
    assert failed["status"] == "failed"
    assert failed["error_code"] == "ocr_failed"


def test_reorder_assets_and_reparse(client: TestClient) -> None:
    fake = FakeOcr()
    set_engine_for_tests(fake)
    draft = upload(client, [("1.png", png(), "image/png"), ("2.png", png(), "image/png")]).json()[
        "data"
    ]
    ids = [a["id"] for a in draft["assets"]]
    r = client.patch(
        f"/api/v1/imports/{draft['id']}",
        json={"version": draft["version"], "asset_order": list(reversed(ids))},
    )
    assert r.status_code == 200, r.text
    assert [a["id"] for a in r.json()["data"]["assets"]] == list(reversed(ids))
    bad = client.patch(
        f"/api/v1/imports/{draft['id']}",
        json={"version": r.json()["data"]["version"], "asset_order": [ids[0]]},
    )
    assert bad.status_code == 422
    calls_before = len(fake.calls)
    reparsed = client.post(f"/api/v1/imports/{draft['id']}/parse", json={})
    assert reparsed.status_code == 200
    assert len(fake.calls) == calls_before  # cached OCR text reused, not re-run


def test_storage_rejects_path_traversal(test_settings) -> None:  # type: ignore[no-untyped-def]
    for bad in ("../etc/passwd", "/etc/passwd", "a/../../x.png"):
        with pytest.raises(storage.StorageError):
            storage.resolve(test_settings, bad)
    ok = storage.resolve(test_settings, f"{uuid.uuid4()}/{uuid.uuid4()}.png")
    assert ok.is_relative_to(Path(test_settings.import_storage_dir).resolve())


def test_delete_removes_files(client: TestClient, test_settings) -> None:  # type: ignore[no-untyped-def]
    set_engine_for_tests(FakeOcr())
    draft = upload(client, [("1.png", png(), "image/png")]).json()["data"]
    folder = Path(test_settings.import_storage_dir) / draft["id"]
    assert folder.is_dir()
    assert client.delete(f"/api/v1/imports/{draft['id']}").status_code == 204
    assert not folder.exists()


def test_cleanup_stale_drafts_and_orphans(
    client: TestClient,
    db_session: Session,
    test_settings,  # type: ignore[no-untyped-def]
) -> None:
    set_engine_for_tests(FakeOcr())
    old = upload(client, [("1.png", png(), "image/png")]).json()["data"]
    fresh = upload(client, [("2.png", png(), "image/png")]).json()["data"]
    orphan = Path(test_settings.import_storage_dir) / str(uuid.uuid4())
    orphan.mkdir(parents=True)
    keep = Path(test_settings.import_storage_dir) / "not-a-uuid"
    keep.mkdir()
    db_session.execute(
        update(ImportDraft)
        .where(ImportDraft.id == uuid.UUID(old["id"]))
        .values(updated_at=ImportDraft.updated_at - timedelta(days=30))
    )
    db_session.commit()

    dry = run_cleanup(db_session, test_settings, dry_run=True)
    assert dry.deleted_drafts == [old["id"]]
    assert db_session.scalar(select(ImportDraft.id).where(ImportDraft.id == uuid.UUID(old["id"])))

    report = run_cleanup(db_session, test_settings)
    assert report.deleted_drafts == [old["id"]]
    assert orphan.name in report.orphan_dirs
    assert not orphan.exists() and keep.exists()
    assert client.get(f"/api/v1/imports/{old['id']}").status_code == 404
    assert client.get(f"/api/v1/imports/{fresh['id']}").status_code == 200


# ----------------------------------------------------------------- real Tesseract (optional)
def _tesseract_cmd() -> str | None:
    cmd = os.environ.get("OCR_TESSERACT_CMD") or get_settings().ocr_tesseract_cmd
    found = shutil.which(cmd)
    if not found:
        return None
    return found if TesseractEngine(found, "jpn", 6, 60).availability().available else None


@pytest.mark.skipif(_tesseract_cmd() is None, reason="Tesseract with jpn data not installed")
def test_real_tesseract_reads_japanese_screenshot(client: TestClient) -> None:
    cmd = _tesseract_cmd()
    assert cmd
    set_engine_for_tests(TesseractEngine(cmd, "jpn", 6, 60))
    font_file = subprocess.run(
        ["fc-match", "-f", "%{file}", "Noto Sans CJK JP"],
        capture_output=True,
        text=True,
        check=False,
    ).stdout
    font = ImageFont.truetype(font_file, 28)
    lines = [
        "1. この川は深いので、泳がないでください。",
        "1) ふかい", "2) ふるい", "3) ひくい", "4) あさい",
    ]  # fmt: skip
    img = Image.new("RGB", (1200, 60 + 52 * len(lines)), "white")
    draw = ImageDraw.Draw(img)
    for i, line in enumerate(lines):
        draw.text((30, 30 + i * 52), line, fill="black", font=font)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    draft = upload(client, [("shot.png", buf.getvalue(), "image/png")]).json()["data"]
    q = draft["content"]["questions"][0]
    assert q["question_text"] == "この川は深いので、泳がないでください。"
    assert q["options"] == ["ふかい", "ふるい", "ひくい", "あさい"]
    assert q["answer_confirmed"] is False
