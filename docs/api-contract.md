# API contract — `/api/v1`

OpenAPI tự sinh: <http://127.0.0.1:8000/api/v1/docs> (Swagger UI), `/api/v1/redoc`,
`/api/v1/openapi.json`.

## Quy ước

**Thành công**

```json
{ "data": { ... } }                                   // một đối tượng
{ "data": [ ... ], "meta": { "page": 1, "page_size": 20, "total": 42, "total_pages": 3 } }
```

**Lỗi** — không bao giờ trả 2xx cho lỗi:

```json
{ "error": { "code": "validation_error", "message": "Dữ liệu gửi lên không hợp lệ.",
             "details": [ { "loc": ["body", "title"], "msg": "...", "type": "string_too_short" } ] } }
```

| HTTP | code | Khi nào |
|---|---|---|
| 404 | `not_found` | Tài nguyên trong URL không tồn tại, route không tồn tại |
| 405 | `method_not_allowed` | |
| 409 | `conflict` | Trùng `source_url`, trùng số câu / nội dung câu trong đề, xoá câu đã có trong bài làm, vi phạm unique còn sót |
| 422 | `validation_error` | Sai kiểu/định dạng, field lạ (`extra=forbid`), vi phạm quy tắc nghiệp vụ (đề tham chiếu không tồn tại, lựa chọn ngoài phạm vi, thời gian ở tương lai…) |
| 500 | `internal_error` | Lỗi không lường trước (đã log, không lộ chi tiết) |
| 503 | — | `/health` khi DB không kết nối được (`data.status = "degraded"`) |

- Phân trang: `page` ≥ 1 (mặc định 1), `page_size` 1–100 (mặc định 20).
- Thời gian: ISO 8601. Input **bắt buộc** có offset (`Z` hoặc `+09:00`), được chuẩn hoá về UTC.
  Output luôn là UTC.
- Chuỗi được trim; Unicode giữ nguyên.
- Đáp án là vị trí **1-based** trong `options`.

## Endpoint

### Health
| Method | Path | Mô tả |
|---|---|---|
| GET | `/health` | `{"status","database","environment","version"}`; 503 nếu DB lỗi |

### Exam sources *(bổ sung)*
| Method | Path | Mô tả |
|---|---|---|
| GET | `/exam-sources` | Danh sách nguồn đề |
| POST | `/exam-sources` | `{name, base_url}` — chỉ lưu metadata, không tải gì từ URL. 409 nếu trùng |

### Exams
| Method | Path | Mô tả |
|---|---|---|
| GET | `/exams` | Query: `page`, `page_size`, `q` (tìm trong title/description, không phân biệt hoa thường, ký tự `%`/`_` được escape), `category`, `status`, `level`. Sắp xếp mới nhất trước; item gồm số attempts, lần gần nhất và số lời giải approved hiện hành |
| POST | `/exams` | Tạo đề → 201 |
| GET | `/exams/{exam_id}` | Chi tiết đề |
| PATCH | `/exams/{exam_id}` | Cập nhật một phần; field bỏ qua giữ nguyên; `description`/`source_url`/`source_id` nhận `null`; `title/level/category/status` không nhận `null`; body rỗng → 422 |

`ExamCreate`:
```json
{ "title": "N3 文法 1", "category": "grammar", "level": "N3", "status": "draft",
  "description": null, "source_url": "https://...", "source_id": null }
```
`ExamRead` thêm: `id, source_name, question_count, verified_answer_count, attempt_count,
latest_attempt_started_at, latest_attempt_accuracy, approved_explanation_count, created_at, updated_at`.
`approved_explanation_count` chỉ tính lời giải approved khớp hash nội dung câu hỏi hiện tại; lời giải stale
không được tính. `latest_attempt_accuracy` là đúng / (đúng + sai), `null` nếu lần gần nhất chưa chấm được.

### Passages *(bổ sung — cần cho câu đọc hiểu)*
| Method | Path | Mô tả |
|---|---|---|
| GET | `/exams/{exam_id}/passages` | Danh sách đoạn văn |
| POST | `/exams/{exam_id}/passages` | `{content}` → 201 |

### Questions
| Method | Path | Mô tả |
|---|---|---|
| GET | `/exams/{exam_id}/questions` | Sắp theo `question_number`. Query `include_answers=false` ẩn `correct_answer` (chế độ làm bài) |
| POST | `/exams/{exam_id}/questions` | Thêm câu → 201 |
| PATCH | `/questions/{question_id}` *(bổ sung)* | Sửa câu / xác nhận đáp án |
| DELETE | `/questions/{question_id}` *(bổ sung)* | 204; 409 nếu câu đã xuất hiện trong bài làm |

`QuestionCreate`:
```json
{ "question_number": 1, "question_type": "grammar_form",
  "question_text": "雨が降っている（　　）、試合は中止になった。",
  "options": ["ので", "のに", "ながら", "ばかりか"],
  "correct_answer": 1, "answer_status": "verified", "passage_id": null }
```
Quy tắc:
- `options`: 2–6 chuỗi không rỗng, không trùng.
- `correct_answer` (tuỳ chọn) trong `1..len(options)`.
- `answer_status` mặc định: `unverified` nếu có đáp án, `missing` nếu không. `verified` mà không
  có đáp án → 422; `missing` kèm đáp án → 422.
- PATCH đổi `correct_answer` mà không gửi `answer_status` ⇒ trạng thái về `unverified`.
- `passage_id` phải thuộc cùng đề (422).
- Trùng `question_number` hoặc trùng nội dung (sau chuẩn hoá NFKC + khoảng trắng) trong cùng
  đề → 409, `details.field` cho biết trường.

### Attempts
| Method | Path | Mô tả |
|---|---|---|
| GET | `/attempts` | Query: `page`, `page_size`, `exam_id`. Mới nhất trước (`started_at`); mỗi item gồm số lời giải approved/pending còn hiện hành trên các câu sai |
| GET | `/attempts/mistakes` | Query: `page`, `page_size`, `exam_id`, `skill`, `q`. Một dòng/question; chỉ nhóm answers `is_correct=false`, có lần sai gần nhất, số lần và answer snapshot |
| POST | `/attempts` | Nộp một lần làm bài đã hoàn thành; server chấm điểm → 201 |
| GET | `/attempts/{attempt_id}` | Chi tiết + từng câu |

`AttemptCreate`:
```json
{ "exam_id": "…", "started_at": "2026-11-08T01:00:00Z", "completed_at": "2026-11-08T01:30:00Z",
  "answers": [ { "question_id": "…", "selected_answer": 2 }, { "question_id": "…", "selected_answer": null } ] }
```
- `completed_at` mặc định = thời điểm server nhận.
- Câu của đề không có trong `answers` ⇒ bỏ trống.
- 422 nếu: đề không tồn tại / đã lưu trữ / không có câu hỏi; câu hỏi không thuộc đề; trả lời
  trùng câu; lựa chọn ngoài `1..len(options)` (lỗi có `loc` theo chỉ số); `completed_at < started_at`;
  thời gian lệch tương lai > 5 phút; datetime thiếu múi giờ.

`AttemptDetail`:
```json
{ "id": "…", "exam_id": "…", "exam_title": "…", "exam_category": "grammar", "exam_source_url": null,
  "started_at": "…", "completed_at": "…", "total_questions": 4,
  "correct_count": 1, "incorrect_count": 1, "unanswered_count": 1, "ungraded_count": 1,
  "accuracy": 0.5, "created_at": "…",
  "answers": [ { "question_id": "…", "question_number": 1, "question_type": "grammar_form",
                 "question_text": "…", "options": ["…"], "passage_id": null,
                 "selected_answer": 1, "correct_answer": 1, "is_correct": true,
                 "current_answer_status": "verified" } ] }
```
`answers[].correct_answer` là đáp án verified **tại thời điểm nộp** (snapshot), `null` nếu khi đó
chưa có đáp án verified.

### Analytics *(bổ sung — nguồn số liệu Dashboard)*
| Method | Path | Mô tả |
|---|---|---|
| GET | `/analytics/summary` | `total_exams, total_questions, total_attempts, total_correct, total_incorrect, total_unanswered, total_ungraded, accuracy, recent_exams[5], recent_attempts[5]` |
| GET | `/analytics/jlpt` | Aggregate Web attempts: outcome counts, accuracy trên câu đã chấm, correct/total, 4 skill groups, trend, repeated exams, duration và source counts. Không chứa Android attempts chưa upload và không ước tính điểm JLPT chính thức |

### Imports *(PR2)*

| Method | Path | Mô tả |
|---|---|---|
| GET | `/imports/capabilities` | OCR khả dụng hay không (+ lý do), giới hạn upload, danh sách adapter |
| GET | `/imports` | Danh sách draft (`page`, `page_size`, `status`), gồm số câu, issues và lỗi parsing gần nhất |
| POST | `/imports/text` | `{text, source_url?, title?, category?}` → 201 draft đã phân tích |
| POST | `/imports/html` | `{html, source_url?, title?, category?}` → 201. `source_url` mặc định lấy từ `<link rel=canonical>` nếu có |
| POST | `/imports/images` | multipart: `files[]` (theo thứ tự đọc), `source_url?`, `title?`, `category?` → 201. **503 `ocr_unavailable`** nếu chưa có OCR (không lưu gì) |
| POST | `/imports/browser-capture` | Capture schema `1.0` từ extension local → 201 draft mới / 200 draft đã nhận trước đó; yêu cầu Bearer secret extension và kết nối từ loopback |
| GET | `/imports/{id}` | Draft đầy đủ: `content`, `issues`, `summary`, `assets`, `raw_input`, `version`, `exam_id`, `attempt_id` |
| PATCH | `/imports/{id}` | `{version, content?, source_url?, asset_order?}`; version cũ → 409; draft đã commit → 409 |
| POST | `/imports/{id}/parse` | Phân tích lại (tuỳ chọn `raw_input` mới cho text/HTML; ảnh dùng lại kết quả OCR, chỉ OCR lại ảnh lỗi). Thay các chỉnh sửa câu hỏi, giữ tên/loại đề và thông tin bài làm |
| POST | `/imports/{id}/validate` | Chạy lại kiểm tra + phát hiện trùng |
| POST | `/imports/{id}/commit` | `{target: "new"\|"existing", existing_exam_id?}` → 201 `CommitResult`; gọi lại → 200 `already_committed: true` (cùng `exam_id`) |
| DELETE | `/imports/{id}` | 204; xoá file ảnh; đề/bài làm đã lưu giữ nguyên |
| GET | `/imports/{id}/assets/{asset_id}` | Ảnh PNG đã chuẩn hoá (`nosniff`, inline) |

Thiết kế so với đề xuất: giữ nguyên các endpoint đề xuất; bổ sung `capabilities` (UI cần biết OCR có
sẵn trước khi cho upload), `parse` (sửa lỗi parser bằng cách sửa dữ liệu gốc) và `assets/{id}`
(đối chiếu ảnh khi kiểm tra OCR). Thay đổi dùng PATCH (sửa một phần tài nguyên draft); validate/
parse/commit là action POST vì có tác dụng phụ ngoài việc ghi trường.

Mã lỗi riêng: `payload_too_large` (413), `rate_limited` (429), `ocr_unavailable` (503),
`conflict` với `details.code` = `version_conflict | duplicate_exam | question_conflict` (409),
`validation_error` (422; khi commit, `details` là danh sách issue lỗi).

`DraftContent.questions[]`:
```json
{ "key": "a1b2c3d4e5f6", "include": true, "question_number": 2, "question_type": "grammar_form",
  "question_text": "雨が降っている（　　）、試合は<u>中止</u>になった。",
  "options": ["のに", "ので", "ながら", "ばかりか"], "passage_key": null,
  "site_answer": 2, "user_answer": 1, "correct_answer": 2, "answer_source": "site_key",
  "answer_confirmed": false, "parser_notes": [], "reviewed": false, "points": 1.0, "is_example": false }
```
`answer_source` do server suy ra. `answer_confirmed` chỉ thành `true` khi client gửi lên sau thao
tác của người dùng; đổi `correct_answer` của câu đã xác nhận → server đặt lại `false`.

#### Browser capture (PR5)

Extension gửi `schema_version`, `capture_id`, `source=dethitiengnhat`, URL N3 `/1` hoặc `/3`, level,
tiêu đề, category, `capture_state`, `captured_at`, và câu hỏi. Các answer index trong payload là
0-based; PR2 preview dùng 1-based. `selected_answer_index`, `source_correct_answer_index` và passage
được phép `null`/vắng nếu không nhận diện được. Source answer luôn trở thành candidate chưa xác nhận;
endpoint không tạo exam hoặc lời giải verified.

Route chỉ hoạt động nếu backend có `EXTENSION_IMPORT_TOKEN` dài ít nhất 32 ký tự. Caller phải có
peer IP loopback và gửi `Authorization: Bearer …`. Origin và URL nguồn không phải bằng chứng xác thực.
Payload bị giới hạn bởi `IMPORT_MAX_HTML_BYTES`; partial unique index theo fingerprint khiến retry
giống hệt trả về cùng draft. Xem `docs/chrome-extension-architecture.md` và
`docs/extension-security.md`.

Thay đổi tương thích ngược ở API PR1: `QuestionRead.answer_source` (mới, `null` khi
`include_answers=false`), `AttemptSummary.source` (mới). Không đổi hay bỏ trường nào.

### Explanations *(PR3)*

| Method | Path | Mô tả |
|---|---|---|
| GET | `/explanations/capabilities` | API có khả dụng không (+ lý do), provider/model, phiên bản prompt/schema, ngân sách đã dùng. Không trả secret. |
| POST | `/explanations/generate` | `{question_id, attempt_answer_id?, force?}` → `201 {outcome:"generated"}` hoặc `200 {outcome:"cached"}` |
| POST | `/explanations/batch` | `{attempt_id, question_ids?, force?}` + header `Idempotency-Key` tuỳ chọn → `201` job mới / `200` job đang chạy hoặc cùng key |
| GET | `/explanations/jobs/{id}` | Tiến độ: `status`, `counts` theo trạng thái item, `items[]` (lỗi từng câu) |
| POST | `/explanations/jobs/{id}/retry` | Đưa câu lỗi/huỷ (và câu bỏ qua nay đã đủ điều kiện) vào hàng đợi lại |
| POST | `/explanations/jobs/{id}/cancel` | Huỷ các câu chưa chạy |
| GET | `/attempts/{id}/explanations` | Tổng quan theo từng câu của bài làm + job gần nhất (frontend dùng để phục hồi sau reload) |
| GET | `/questions/{id}` | Một câu hỏi (bổ sung cho trang lời giải) |
| GET | `/questions/{id}/explanations` | Mọi phiên bản (`stale`, `is_current`) + `current_id` + điều kiện chữa (`?attempt_answer_id=` để có phân tích lỗi) |
| GET | `/explanations/{id}` | Một lời giải (`?attempt_answer_id=`) |
| POST | `/explanations/{id}/approve` | `{note?}` — người dùng xác nhận; lời giải đã cũ/đã từ chối → 409 |
| POST | `/explanations/{id}/reject` | `{note?}` — đánh dấu chưa chính xác |
| POST | `/explanations/export-prompt` | `{question_ids (1–20), attempt_id?}` → prompt (kèm lựa chọn thật nếu có attempt), câu bị loại + lý do, JSON schema |
| POST | `/explanations/manual-import` | `{question_ids, raw_json (≤1MB), save, model_label?}` — `save=false` xem trước, `save=true` lưu các lời giải hợp lệ (`needs_review`) |

Lỗi riêng: `422 question_not_eligible` (`details.reason`: `answer_not_verified`, `missing_passage`,
`too_few_options`), `503 ai_unavailable` (`details.fallback: "manual"`), `502 ai_provider_error`
(`details.provider_code`: `provider_auth`, `provider_quota`, `provider_timeout`,
`provider_unavailable`, `provider_bad_request`), `429` khi provider giới hạn tốc độ hoặc
`ai_budget_exceeded`, `502 ai_output_invalid` (`details.errors[{code,message}]`), `409
generation_in_progress`.

Ghi chú thiết kế: endpoint đề xuất được giữ nguyên; bổ sung `capabilities`, `jobs/{id}/retry|cancel`,
`attempts/{id}/explanations`, `GET /questions/{id}`. Job item có trạng thái riêng `cached` / `succeeded`
/ `failed` / `skipped` để phân biệt kết quả; job chỉ `completed` khi không còn câu lỗi.

### Knowledge, reviews và analytics (PR4)

| Method | Path | Mô tả |
|---|---|---|
| GET | `/knowledge` | Danh sách tri thức, lọc theo `type`, `status`, `q`, `priority`; có thống kê từ bài làm và review events |
| POST | `/knowledge/extract` | `{attempt_id}` hoặc `{question_ids}` → ứng viên từ lời giải đã duyệt, gợi ý liên kết/dedup; không gọi AI |
| POST | `/knowledge/confirm` | Lưu ứng viên đã được người dùng duyệt, liên kết/quan hệ và tạo review items idempotent |
| GET/PATCH | `/knowledge/{id}` | Chi tiết/evidence/questions/relations/review items; cập nhật metadata có optimistic version |
| POST | `/knowledge/merge`, `/knowledge/{id}/split`, `/knowledge/{id}/relations` | Gộp, tách sense và quản lý quan hệ tri thức |
| GET | `/analytics/weaknesses?window=7d\|30d\|all` | Sai số theo nhóm và tri thức, độ tin cậy, ưu tiên, timeline và thay đổi sau ôn |
| GET | `/analytics/knowledge/{id}` | Thống kê một tri thức |
| GET | `/analytics/review-progress?days=30` | Số lượt, đánh giá, độ chính xác, due count và tiến độ theo ngày |
| GET | `/reviews?bucket=due\|upcoming\|completed\|insufficient\|suspended` | Hàng đợi và số lượng theo trạng thái |
| POST | `/reviews/sessions` | `{limit}` → phiên ôn, đáp án được giữ kín tới khi trả lời |
| GET | `/reviews/sessions/{id}` | Tiếp tục phiên hiện tại; đáp án chưa trả lời vẫn được giữ kín |
| POST | `/reviews/sessions/{id}/answer` | `{card_id, selected_index}` → chấm và mở gợi ý; chưa cập nhật lịch SRS |
| POST | `/reviews/events` | `{request_id, review_item_id, rating, timezone, session_id?, card_id?}` → lưu event idempotent và lên lịch lại |
| GET | `/reviews/history` | Lịch sử event, có thể lọc theo item hoặc tri thức |
| PATCH | `/reviews/{id}` | Tạm dừng, hoàn tất hoặc kích hoạt lại với `version` |
| POST | `/practice/generate`, `/practice/export-prompt`, `/practice/manual-import` | Tạo/xuất/nhập bài luyện có kiểm định; generated question phải được duyệt trước khi vào SRS |

Luồng PR4: lời giải được người dùng duyệt → extraction preview → người dùng xác nhận → knowledge/evidence/relations
và review items → phiên trả lời → rating event → SRS state + history + analytics. Extraction và review
thông thường không gọi OpenAI API.

## Chưa triển khai (cố ý)

Tải nội dung từ URL phía server, scraping, xoá đề và xác thực người dùng chưa triển khai.

### Android sync (single-user pairing)

- Operator gọi `POST /sync/admin/pairing-codes` với `X-Sync-Admin-Key` (ít nhất 32 ký tự ngoài
  loopback development/test), body `{ "expires_in_minutes": 10 }`. Response chỉ hiển thị mã ngẫu nhiên
  một lần; mặc định hết hạn sau 10 phút, tối đa 15 phút. Database chỉ lưu hash. Mã cũ chưa dùng bị
  thu hồi khi tạo mã mới; năm lần sai trong 15 phút gây lockout 15 phút.
- Android gọi `POST /sync/pair` với `X-Pairing-Key` chứa pairing code và body `{ "device_name": "..." }`.
  Response trả `device_id` và bearer token một lần; database chỉ lưu hash token.
- `GET /sync/admin/devices` với admin key liệt kê thiết bị và lần request/pull/push gần nhất.
  `DELETE /sync/admin/devices/{device_id}` revoke device credential. Đây là activity quan sát được,
  không phải bằng chứng client hoàn tất mọi trang sync.
- `GET /sync/changes?cursor=0&limit=200` yêu cầu `Authorization: Bearer <device token>`. Trả dữ liệu
  theo cursor commit-ordered (migration 0007), snapshot payload, `next_cursor` và `has_more`. Mỗi change gồm `cursor/entity_type/entity_id/
  operation/version/changed_at/data`. `data=null` nghĩa là bản ghi đã bị xoá hoặc không còn đủ điều
  kiện đồng bộ (ví dụ lời giải bị bỏ duyệt hoặc stale); trường hợp lời giải stale được phát operation
  tombstone để client ẩn cache cũ.
- `question.answer_index` luôn 0-based và chỉ có giá trị khi đáp án đã verified. Lời giải chỉ xuất
  khi approved và `content_hash` khớp nội dung câu hiện tại.
- `POST /sync/push` nhận tối đa 500 Android review events. `request_id` UUID gửi lại cùng payload
  trên cùng thiết bị trả `duplicates`; tái sử dụng UUID với payload khác bị HTTP 409. Server append
  lịch sử vào `android_review_events` và không thay đổi tiến độ SRS Android hoặc lịch Web.
- `POST /sync/disconnect` revoke bearer token cho thiết bị hiện tại.
- PR6.1 Android lưu pull content trong bảng Room `synced_*` riêng (schema 15), checkpoint cùng
  transaction với mỗi trang, và outbox append-only cho event. Không ghi/replace
  `learning_progress`, `review_records` hay nội dung từ vựng cũ. Emulator fake-transport integration
  tests đạt; live HTTPS API pairing chưa được xác minh. Xem `android-sync-capability-matrix.md` để biết
  entity nào Android thực sự push/pull; exam history Android không được upload.
