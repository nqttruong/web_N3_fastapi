# Import pipeline (PR2)

Nhập đề N3 mà người dùng đã làm, từ nội dung **do chính người dùng cung cấp** (dán văn bản, dán HTML,
ảnh chụp). Máy chủ không bao giờ tự tải URL.

```
 Input (text | HTML | images)
   │  size / type validation  ── 413 / 422 (ảnh: kiểm tra theo nội dung file, không theo đuôi)
   ▼
 Source adapter  ── generic_text | dethitiengnhat_html | generic_html | ocr_text (Tesseract → text)
   │  parse → DraftContent + parse_notes
   ▼
 Normalisation  ── provenance đáp án (site_key / user_entered / ocr), không đổi văn bản hiển thị
   ▼
 Structural validation  ── lỗi (chặn lưu) / cảnh báo / thông tin, theo từng câu
   ▼
 Duplicate detection  ── cùng URL, cùng bộ câu hỏi, câu đã có ở đề khác, nhập lại cùng nội dung
   ▼
 Preview (import_drafts)  ── người dùng sửa, đánh dấu "đã kiểm tra", xác nhận đáp án
   ▼
 Commit  ── một transaction, idempotent → exams / passages / questions (+ exam_attempts)
```

Code: `backend/app/imports/` — `adapters/` (parse), `validation.py`, `duplicates.py`, `service.py`
(điều phối), `router.py` (HTTP mỏng), `ocr.py`, `images.py`, `storage.py`, `cleanup.py`.

## Vòng đời draft

| Trạng thái | Ý nghĩa | Chuyển tiếp |
|---|---|---|
| `uploaded` | Đã nhận dữ liệu (thoáng qua) | → `parsing` |
| `parsing` | Đang chạy adapter/OCR (ảnh: được lưu ngay để thấy nếu tiến trình bị dừng) | → `needs_review` / `ready` / `failed` |
| `needs_review` | Còn lỗi chặn (thiếu tên, thiếu loại, câu chưa kiểm tra, trùng số câu…) | sửa → `ready` |
| `ready` | Không còn lỗi; cảnh báo vẫn có thể còn | → `committed` |
| `committed` | Đã lưu thành đề — chỉ đọc | (cuối) |
| `failed` | Adapter từ chối (`unsupported_layout`) hoặc OCR không đọc được ảnh nào (`ocr_failed`) | sửa/phân tích lại |

Mỗi lần PATCH/parse/validate đều chạy lại kiểm tra và cập nhật trạng thái. `version` tăng mỗi lần
ghi; PATCH với version cũ → 409 (tránh ghi đè giữa hai tab).

## Ba loại đáp án

| Trường | Ý nghĩa | Ai đặt |
|---|---|---|
| `site_answer` | Đáp án trang nguồn hiển thị (khoá ẩn `AS{n}`, ký hiệu 正解, dòng "正解: 2", OCR) | Parser |
| `user_answer` | Lựa chọn của người dùng khi làm bài trên trang (不正解, "あなたの答え") | Parser / người dùng |
| `correct_answer` | Đáp án người dùng chỉ định là chuẩn (mặc định điền sẵn bằng `site_answer` như **gợi ý**) | Người dùng |
| `answer_confirmed` | Người dùng đã bấm "Xác nhận đáp án" | **Chỉ người dùng** |

Khi lưu: `confirmed` → `verified`; có đáp án nhưng chưa xác nhận → `unverified`; không có → `missing`.
Chỉ `verified` được dùng để chấm (quy tắc PR1). Đổi `correct_answer` của câu đã xác nhận → tự bỏ xác
nhận. `user_answer` không bao giờ được coi là đáp án đúng. OCR/parser không bao giờ đặt
`answer_confirmed`.

Provenance lưu vào `questions.answer_source` (`manual`, `site_key`, `user_entered`, `ocr`) — server
tự suy ra, client không đặt được.

## Commit

`POST /imports/{id}/commit {target: "new" | "existing", existing_exam_id?}`

1. Khoá dòng draft (`SELECT … FOR UPDATE`) — bấm nhiều lần sẽ tuần tự; lần sau thấy `committed` và
   trả **cùng kết quả** (`200`, `already_committed: true`). Unique index
   `exam_attempts.import_draft_id` chặn tạo bài làm hai lần.
2. Chạy lại toàn bộ kiểm tra; còn lỗi → 422 kèm danh sách.
3. `new`: nếu đã có đề cùng `source_url` → 409 `duplicate_exam` (gợi ý dùng đề đã có). Tạo exam
   (`status=ready`), passage (chỉ những đoạn được dùng, theo thứ tự), question.
4. `existing`: câu **giống hệt** (text + options nguyên văn) được dùng lại; câu mới được thêm nếu số
   câu và nội dung chưa có; trùng số câu hoặc gần giống (cùng hash NFKC) → 409 `question_conflict`,
   rollback toàn bộ. Đáp án của câu dùng lại chỉ được **bổ sung** (đề cũ chưa verified mà bản nhập đã
   xác nhận, hoặc đề cũ chưa có đáp án); đề cũ đã verified mà khác → giữ nguyên + cảnh báo
   `answer_conflict`.
5. `attempt.create`: cần `started_at`, `completed_at` do người dùng nhập và ít nhất một
   `user_answer`. Chấm bằng hàm `build_graded_attempt` dùng chung với PR1 (`source = import`).
6. Draft → `committed`, lưu `exam_id`. Tất cả trong một transaction.

## Trùng lặp (chỉ báo, không gộp)

| Mã | Mức | Khi nào |
|---|---|---|
| `duplicate_source_url` | warning | Đã có đề cùng URL nguồn |
| `duplicate_exam` | warning | Mọi câu đưa vào đều đã thuộc một đề (fingerprint) |
| `questions_in_other_exam` | info | Một phần câu đã có ở đề khác |
| `question_exists_elsewhere` | info (theo câu) | Câu này có ở đề khác |
| `existing_attempts` | info | Đề trùng đã có lần làm — bài làm mới được thêm, lịch sử giữ nguyên |
| `duplicate_draft` | info | Cùng nội dung gốc đã được nhập ở draft khác |

Fingerprint = sha256(NFKC + gộp khoảng trắng của text và options), **không** chứa passage. NFKC chỉ
dùng trong hash; xem `backend/app/exams/fingerprints.py` và `tests/test_fingerprints.py` (những gì
được gộp / giữ khác biệt).

## Dọn dẹp

`uv run python -m app.imports.cleanup [--dry-run]`:
- xoá draft chưa commit cũ hơn `IMPORT_DRAFT_TTL_DAYS` (mặc định 14) cùng file ảnh;
- xoá file ảnh của draft đã commit cũ hơn TTL (giữ dòng draft làm lịch sử);
- xoá thư mục mồ côi (tên UUID, không có draft) trong thư mục lưu trữ.

Xoá draft (`DELETE /imports/{id}`) xoá luôn file; đề và bài làm đã lưu **không** bị xoá
(`exam_attempts.import_draft_id` → NULL).
