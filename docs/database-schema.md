# Database schema (PostgreSQL 17)

Nguồn sự thật: `backend/app/**/models.py` + các migration `backend/alembic/versions/0001`–`0007`.
Test `tests/test_migrations.py` kiểm tra migration và models khớp nhau (không drift), và
upgrade → downgrade → upgrade chạy được.

Quy ước chung:
- Khoá chính `UUID` (trừ `sync_changes.id` là BIGINT commit-ordered cursor).
- Thời gian: `timestamptz`, mặc định `now()`; session DB đặt `TIME ZONE 'UTC'`.
- Enum: `TEXT` + `CHECK`. Tên constraint theo naming convention (`ck_<table>_<name>`, `uq_...`, `fk_...`, `ix_...`).
- Database tạo với `ENCODING 'UTF8'`, `--locale=C.UTF-8`.

## Sơ đồ quan hệ

```
exam_sources 1─┐
               └─< exams 1─┬─< passages 1─┐
                           │              └─< questions (passage_id, cùng exam)
                           ├─< questions 1─┬─< attempt_answers >─┐
                           │               ├─< ai_explanations   │
                           │               ├─< question_knowledge >─ knowledge_items 1─< review_items 1─< review_events
                           │               └─< review_items.source_question_id (SET NULL)
                           └─< exam_attempts 1──────────────────┘
sync_changes (độc lập, append-only)
```

## Bảng đang được dùng trong PR1

### exam_sources
| Cột | Kiểu | Ghi chú |
|---|---|---|
| id | uuid PK | |
| name | text NOT NULL UNIQUE | không rỗng |
| base_url | text NOT NULL UNIQUE | `^https?://` |
| created_at | timestamptz | |

### exams
| Cột | Kiểu | Ghi chú |
|---|---|---|
| id | uuid PK | |
| source_id | uuid NULL → exam_sources ON DELETE SET NULL | |
| source_url | text NULL | `^https?://`; **unique khi NOT NULL** (partial index) — chống nhập trùng một trang nguồn |
| level | text | `N1..N5` (UI chỉ cho N3) |
| category | text | `vocabulary, kanji, grammar, reading` |
| title | text NOT NULL | không rỗng |
| description | text NULL | |
| status | text | `draft, ready, archived` |
| created_at, updated_at | timestamptz | |

Index: `(level, category)`, `status`, `created_at`, `source_id`.

### passages
| Cột | Kiểu | Ghi chú |
|---|---|---|
| id | uuid PK | |
| exam_id | uuid → exams ON DELETE CASCADE | |
| content | text NOT NULL | không rỗng |
| created_at | timestamptz | |

`UNIQUE (exam_id, id)` để câu hỏi tham chiếu passage **cùng đề** qua FK kép.

### questions
| Cột | Kiểu | Ghi chú |
|---|---|---|
| id | uuid PK | |
| exam_id | uuid → exams ON DELETE CASCADE | |
| passage_id | uuid NULL | FK kép `(exam_id, passage_id) → passages(exam_id, id)` |
| question_number | smallint | > 0, `UNIQUE (exam_id, question_number)` |
| question_type | text | 14 dạng 問題 N3 + `other` |
| question_text | text NOT NULL | không rỗng, giữ nguyên Unicode |
| options | jsonb | mảng 2–6 chuỗi |
| correct_answer | smallint NULL | 1-based, `1 ≤ x ≤ jsonb_array_length(options)` |
| answer_status | text | `missing, unverified, verified`; `(missing) ⇔ correct_answer IS NULL` |
| content_hash | text | sha256 của (passage, text, options) đã chuẩn hoá NFKC; `UNIQUE (exam_id, content_hash)` |
| created_at, updated_at | timestamptz | |

Thêm `UNIQUE (exam_id, id)` làm đích FK kép từ `attempt_answers`.

### exam_attempts
| Cột | Kiểu | Ghi chú |
|---|---|---|
| id | uuid PK | |
| exam_id | uuid → exams ON DELETE RESTRICT | không xoá đề đã có lịch sử |
| started_at | timestamptz NOT NULL | |
| completed_at | timestamptz NULL | `≥ started_at`; NULL dành cho bài đang làm (tương lai) |
| total_questions | int | |
| correct_count, incorrect_count, unanswered_count, ungraded_count | int ≥ 0 | tổng = `total_questions` (CHECK) |
| created_at | timestamptz | |

Index: `exam_id`, `started_at`. `UNIQUE (id, exam_id)` làm đích FK kép.

### attempt_answers
| Cột | Kiểu | Ghi chú |
|---|---|---|
| id | uuid PK | |
| attempt_id, exam_id | uuid | FK kép → `exam_attempts(id, exam_id)` ON DELETE CASCADE |
| question_id | uuid | FK kép `(exam_id, question_id) → questions(exam_id, id)` RESTRICT — **câu hỏi phải thuộc đúng đề của bài làm** |
| question_number | smallint | snapshot |
| selected_answer | smallint NULL | ≥ 1; NULL = bỏ trống |
| correct_answer_snapshot | smallint NULL | đáp án verified dùng để chấm tại thời điểm nộp |
| is_correct | bool NULL | CHECK: NULL ⇔ (bỏ trống hoặc không có đáp án verified); nếu không NULL thì = (selected = snapshot) |
| created_at | timestamptz | |

`UNIQUE (attempt_id, question_id)`; index `question_id`.

## Bảng chỉ có schema (chưa có API trong PR1)

| Bảng | Cột chính | Ràng buộc |
|---|---|---|
| ai_explanations | question_id → questions CASCADE, provider, model, explanation_json jsonb, verification_status | json phải là object; status `unverified/verified/rejected`; index question_id |
| knowledge_items | knowledge_type, jlpt_level, title, content | type `vocabulary/kanji/grammar/reading_skill`; `UNIQUE (knowledge_type, jlpt_level, title)` |
| question_knowledge | PK (question_id, knowledge_id), relation_type | relation `tests/distractor/context`; index knowledge_id |
| review_items | knowledge_id → knowledge_items CASCADE, source_question_id → questions SET NULL, status, due_at | status `active/suspended/done`; unique knowledge_id; index (status, due_at) |
| review_events | review_item_id → review_items CASCADE, rating, reviewed_at | rating `again/hard/good/easy` (giống Android `ReviewRating`); index (review_item_id, reviewed_at) |
| sync_changes | id BIGINT commit-ordered, entity_type, entity_id uuid, operation, version, changed_at, schema_version, payload JSONB | operation `insert/update/delete`; version ≥ 1; `UNIQUE (entity_type, entity_id, version)`; index changed_at |

## Điều chỉnh so với đề xuất (và lý do)

1. **`exam_attempts` thêm `incorrect_count`, `unanswered_count`, `ungraded_count`** — "số câu sai" và
   "chưa chấm" phải phân biệt được; CHECK đảm bảo tổng bằng `total_questions`.
2. **`attempt_answers` thêm `exam_id`, `question_number`, `correct_answer_snapshot`** — `exam_id` cho
   FK kép chứng minh câu hỏi thuộc đúng đề; snapshot giữ lịch sử ổn định khi đáp án được sửa.
3. **`questions` thêm `content_hash`** — unique theo đề để chặn câu trùng nội dung (kể cả khác
   toàn/nửa độ rộng), ngoài unique `question_number`.
4. **`correct_answer` là `smallint` (vị trí 1-based)** thay vì text — khớp cách đánh số đáp án JLPT
   (1–4) và `answer_index` của Android; CHECK theo số lượng options.
5. **`answer_status` thêm giá trị `missing`** — phân biệt "chưa có đáp án" với "có nhưng chưa xác nhận".
6. **`question_knowledge` có `created_at`** và PK kép `(question_id, knowledge_id)`.
7. **`sync_changes.id` là BIGINT commit-ordered** thay vì UUID — row lock tuần tự hóa cấp cursor đến khi transaction commit.
8. **`knowledge_items.content` là `text`** — nội dung PR1 chưa có cấu trúc cố định; sẽ thêm cột
   JSONB `details` khi PR tri thức chốt format.

## Mở rộng `user_id` / `device_id` sau này

- Thêm cột `user_id uuid NULL` vào `exams`, `exam_attempts`, `knowledge_items`, `review_items`,
  backfill bằng user mặc định, rồi `SET NOT NULL`.
- Các unique hiện tại đổi thành có tiền tố `user_id` (ví dụ `(user_id, source_url)`,
  `(user_id, knowledge_id)` cho `review_items`).
- `device_id` + `client_updated_at` thêm vào bảng được đồng bộ (attempts, review_events) để
  idempotent khi thiết bị gửi lại.

---

## PR2 — migration `0002` (chỉ bổ sung, không xoá/tạo lại bảng PR1)

Đã chạy trên database phát triển có sẵn dữ liệu seed: 8/8 câu được backfill, không mất dữ liệu.
Test `test_0002_upgrades_existing_data_without_loss` kiểm tra upgrade từ 0001 có dữ liệu và downgrade.

### Cột mới trên bảng PR1

| Bảng.cột | Kiểu | Ghi chú |
|---|---|---|
| `questions.answer_source` | text NULL | `manual / site_key / user_entered / ocr`; CHECK `(answer_source IS NULL) = (correct_answer IS NULL)`. Backfill: `manual` cho mọi câu đã có đáp án. |
| `questions.fingerprint` | text NOT NULL, index | sha256(NFKC(text) + options) **không** gồm passage — phát hiện câu trùng giữa các đề. Backfill bằng bản sao "đóng băng" của hàm hash trong migration (test kiểm tra trùng khớp với code). |
| `exam_attempts.source` | text NOT NULL default `practice` | `practice / import` |
| `exam_attempts.import_draft_id` | uuid NULL → import_drafts ON DELETE SET NULL | **unique khi NOT NULL** — một bài làm cho mỗi draft (commit idempotent). CHECK: có draft ⇒ `source='import'`. |

### import_drafts
| Cột | Kiểu | Ghi chú |
|---|---|---|
| id | uuid PK | |
| status | text | `uploaded, parsing, needs_review, ready, committed, failed` |
| method | text | `text, html, images` |
| adapter | text NULL | adapter đã tạo `content` |
| source_url | text NULL, index | `^https?://`; không bao giờ được tải |
| raw_input | text NULL | văn bản/HTML gốc nguyên văn; CHECK `(method='images') = (raw_input IS NULL)` |
| raw_sha256 | text, index | phát hiện nhập lại cùng nội dung |
| content | jsonb (object) | bản xem trước có thể sửa (exam meta, passages, questions, attempt, parse_notes) |
| issues | jsonb (array) | kết quả kiểm tra gần nhất |
| error_code, error_message | text NULL | khi `failed` |
| version | int | optimistic locking |
| exam_id | uuid NULL → exams SET NULL, index | đề đã lưu |
| committed_at | timestamptz NULL | CHECK: `committed` ⇒ có thời điểm |
| created_at, updated_at | timestamptz | |

### import_assets
| Cột | Kiểu | Ghi chú |
|---|---|---|
| id | uuid PK | |
| draft_id | uuid → import_drafts CASCADE | |
| position | smallint ≥ 0 | `UNIQUE (draft_id, position) DEFERRABLE INITIALLY DEFERRED` (đổi thứ tự trong một transaction) |
| storage_path | text UNIQUE | đường dẫn tương đối do server sinh; CHECK không bắt đầu bằng `/`, không chứa `..` |
| original_filename | text NULL | chỉ để hiển thị |
| detected_type | text | `image/png, image/jpeg, image/webp` (theo nội dung file) |
| stored_type | text | luôn `image/png` (đã mã hoá lại) |
| byte_size, width, height | > 0 | |
| sha256 | text | của file gốc |
| ocr_status | text | `pending, done, failed` |
| ocr_engine, ocr_text | text NULL | kết quả OCR theo từng ảnh (dùng lại khi phân tích lại) |

Lý do chọn JSONB cho `content`: bản nháp là dữ liệu tạm, được sửa và kiểm tra nguyên khối, cấu trúc
có thể đổi theo adapter. Dữ liệu lâu dài chỉ đi vào bảng quan hệ (`exams/passages/questions/
exam_attempts`) khi commit, qua đầy đủ constraint của PR1.

---

## PR3 — migration `0003`

Chỉ bổ sung. Bảng `ai_explanations` (có từ PR1, chưa dùng) được mở rộng; thêm 3 bảng. Test
`test_0003_keeps_existing_explanations_and_data` chạy trên DB có dữ liệu PR1/PR2 và lời giải cũ.

### ai_explanations — cột mới

| Cột | Kiểu | Ghi chú |
|---|---|---|
| `verification_status` | text | Giá trị đổi thành `generated, needs_review, approved, rejected` (dữ liệu cũ: `unverified`→`needs_review`, `verified`→`approved`; downgrade đảo lại) |
| `origin` | text | `api` / `manual` |
| `prompt_version`, `schema_version` | text | |
| `content_hash` | text, index (với question_id) | hash nội dung câu + lựa chọn + passage + loại + đáp án verified lúc tạo; khác hiện tại ⇒ **stale** |
| `cache_key` | text, index | content_hash + provider + model + prompt + schema |
| `verified_answer_snapshot` | smallint NULL | đáp án (1-based) dùng khi tạo |
| `validation_issues` | jsonb (array) | kết quả kiểm định |
| `flagged_answer_concern` | bool | AI nghi ngờ đáp án nguồn |
| `usage` | jsonb NULL | token, chi phí ước tính |
| `reviewed_at`, `review_note` | | CHECK: approved/rejected ⇒ có `reviewed_at` |

Bản ghi trước PR3 nhận `content_hash='legacy'` ⇒ luôn hiển thị là "đã cũ".

### explanation_jobs
`id`, `attempt_id` → exam_attempts CASCADE (NULL được), `status` (`pending, running, completed,
partial_failed, failed, cancelled`), `force`, `idempotency_key` UNIQUE, `started_at`, `finished_at`,
timestamps.

### explanation_job_items
`id`, `job_id` → CASCADE, `question_id` → questions CASCADE, `attempt_answer_id` → SET NULL,
`position`, `status` (`pending, running, cached, succeeded, failed, skipped, cancelled`), `tries`,
`lease_expires_at` (khôi phục khi worker chết), `error_code`, `error_message`, `explanation_id` → SET
NULL. `UNIQUE (job_id, question_id)`, index `(status, lease_expires_at)`.

### ai_requests
Một dòng mỗi lần gọi provider: `id` BIGINT IDENTITY, `provider`, `model`, `question_id` (SET NULL),
`status` (`succeeded/failed`), `error_code`, `input_tokens`, `output_tokens`, `cost_usd`
numeric(12,6), `duration_ms`, `created_at` (index). Không lưu nội dung prompt/kết quả. Dùng cho ngân
sách và thống kê.

---

## PR4 — migration `0004`

Migration bổ sung cho knowledge/reviews/practice, không reset database:

- `knowledge_items`: thêm `canonical_key`, `details`, `merged_into_id`, `source_explanation_id`,
  `android_ref`, versioning/status metadata; unique normalized key để chống trùng.
- `question_knowledge`: liên kết câu với knowledge theo role (`tests`, `distractor`, `context`).
- `knowledge_evidence`: provenance của nội dung trích xuất, liên kết lời giải/câu hỏi và thời điểm
  người dùng xác nhận.
- `knowledge_relations`: graph quan hệ `confused_with`, `prerequisite`, `related_to`; cặp symmetric
  được chuẩn hoá và unique.
- `review_items`: `dedup_key` unique để tạo task idempotent; lưu kind, nguồn, status, SRS state,
  step/interval, due time, số lần ôn/lapse, ladder và algorithm version.
- `review_events`: lịch sử có rating, request id idempotent, session/card kind, answer result,
  before/after snapshot, due date, timezone và algorithm version.
- `review_sessions`: thẻ phiên ôn dạng JSONB; đáp án chưa trả lời không được gửi ra client.
- `practice_generations` và `generated_practice_questions`: nguồn tạo API/manual, validation, provenance,
  dedup fingerprint và trạng thái duyệt. Câu hỏi chỉ vào SRS sau khi user approve.

Knowledge extraction chỉ dùng lời giải `approved` còn hiện hành, và chỉ persist sau thao tác xác nhận
của user. Trả lời thẻ chưa thay đổi lịch; chỉ review event cập nhật SRS state và due time.

---

## PR6 — migration `0006`

Migration chỉ thêm bảng/index/trigger và check constraint sync; không đổi hoặc xóa bản ghi PR1–PR5.

- `sync_devices`: UUID, tên, `token_hash` unique, `revoked_at`, `last_seen_at`, `created_at`. Bearer
  token thô chỉ trả một lần lúc pair.
- `android_review_events`: append-only event từ Room với `request_id` UUID UNIQUE, device, `item_type`
  (`VOCABULARY/KANJI/GRAMMAR`), item ID chuỗi, rating, thời gian ôn, interval trước/sau, due time và
  `received_at`. Không lưu bản sao `learning_progress`.
- `sync_changes`: bổ sung `ai_explanation` và `android_review_event` vào check constraint hiện hữu.
  Trigger transactionally ghi insert/update/delete cho `exams`, `passages`, `questions` và
  `ai_explanations`; migration thêm cursor ban đầu cho dữ liệu đã có.
- Downgrade xóa sync cursor của hai entity type mới trước khi khôi phục check cũ; không chạm dữ liệu
  nghiệp vụ. Không dùng downgrade trong vận hành PR6.

## PR6.1 — migration `0007`

- `sync_changes.id` dùng sequence có default `next_sync_cursor()`. Singleton `sync_cursor_lock`
  được giữ row lock tới transaction commit để cursor tuân theo commit order; payload snapshot,
  schema version và changed_at được giữ trên từng change.
- Trigger mở rộng cho exam/passages/questions/attempts/attempt answers/AI explanations/knowledge/review
  items/Android events. Quan hệ question↔knowledge phát snapshot knowledge có linked question IDs.
- Khi câu hỏi đổi, các lời giải liên quan được phát lại để API biến lời giải approved nhưng stale
  thành tombstone. Dữ liệu lịch sử được backfill, không xóa bản ghi nghiệp vụ.
- Migration được kiểm tra upgrade/downgrade/schema drift và test thứ tự commit trên PostgreSQL test DB;
  chưa được áp dụng lên dev DB trong PR6.1.
