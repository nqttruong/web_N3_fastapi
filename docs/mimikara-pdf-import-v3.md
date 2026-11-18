# Mimikara PDF → Vocabulary (private Web import)

## Source and rights

The user supplied `[VTI Mirai share] 140 - 880 TỪ VỰNG MIMIKARA N3 MINATO.xlsx - TU VUNG MIMIKARA N3.pdf` in the Web repository root. Despite `.xlsx` inside its name, it is a 282,654-byte, single-page text PDF. SHA-256: `a943ffaf90149f7d98bff5fb4d4296195adc942796600a2aefe9ce8243ac5728`. It has 19 groups of STT/Kanji/Hiragana/Meaning columns (one group omits Hiragana), continuous STT 1–880, and no example column. The Web imported exactly these 880 rows, not an inferred complete book or the separately gated Android Mimikara examples.

The operator's private-use assertion for **this exact PDF hash** is recorded in `learning_source_rights` with `pack_id=mimikara-n3-pdf-private` and `source_id=vti-mirai-mimikara-n3-pdf`. Its scope is `private`, with provenance and approval timestamp. It does not approve other Mimikara sources or public redistribution. Replacing the PDF changes the hash; recheck content and explicitly approve the new hash before import.

## Extraction and mapping

`backend/app/learning_content/mimikara_pdf.py` calls `pdftotext -bbox` and maps text coordinates to table cells. It fails if page count, 19 header groups, required fields, duplicate STT or 880 contiguous STT differ. `pdf_import.py` maps each STT to a stable source item ID, source row/page, source hash and one of 12 source lessons whose boundaries were checked against Android N3 Sensei's source asset. It preserves raw Japanese term, supplied reading, Vietnamese meaning and Unicode. Exactly 41 readings are blank in PDF (40 Katakana rows 511–550 and row 627); no synthetic readings or translations are created. A PDF spelling difference from Android row 796 remains the PDF spelling.

The existing sync queue/worker validates the snapshot, upserts in a transaction, records audit changes and soft archives only rows belonging to its PDF namespace. Android JSON sync cannot archive PDF rows. Re-import with the same hash returns `no_changes` and does not duplicate records. Web user-created words are in different tables and untouched.

## Usage

1. Install `pdftotext` (Poppler), set `MIMIKARA_PDF_PATH` only if the file is elsewhere, and start PostgreSQL, FastAPI and the single learning-content worker.
2. In `/settings/rights`, inspect the PDF candidate's SHA-256, row count, source name, and the read-only first/middle/last row preview from `GET /api/v1/learning-content/rights/pdf-preview`. Enter the rights holder/assertion, basis, usage and attribution as applicable; approve **only that candidate**. This enqueues a `pdf` sync run.
3. Watch Settings learning sync status and worker logs. A successful run reports new/updated/archived item counts. Open `/learning` → Từ vựng or `GET /api/v1/learning-content/items?type=vocabulary`; the dev database currently returns 880 real vocabulary items.
4. To re-import unchanged bytes, resubmit the same rights declaration and let the worker process its queue. Expect `no_changes` and unchanged counts. If the PDF changes, inspect and reapprove the new hash; a failed validation leaves the old active content intact.

Before V3: 4 packs, 26 source lessons, 457 items (0 vocabulary), 1,271 examples. After approved PDF import: 5 packs, 38 source lessons, 1,337 items (880 vocabulary), 1,271 examples. Existing Web study events and saved items remain. The import is not a sync of Android private Room learning progress.
