# Kế hoạch tích hợp Android N3 Sensei

> **Cập nhật PR6.1:** Phần kế hoạch phác thảo bên dưới là tư liệu ban đầu và một số mô tả đã
> lỗi thời. Triển khai hiện tại dùng migration backend `0007`, Room schema 15 và các bảng mirror
> `synced_*`; không ánh xạ sang `exam_sets`, nội dung pack, `learning_progress` hoặc `review_records`.
> Cursor được cấp phát theo thứ tự transaction commit bằng singleton row lock; nội dung feed là
> snapshot; Android áp dụng từng trang cùng checkpoint trong transaction Room. Xem
> [sync architecture](sync-architecture.md), [protocol](sync-protocol.md),
> [entity mapping](android-entity-mapping.md), [offline/testing](android-offline-sync.md).

> PR6 bổ sung pairing, change feed và đồng bộ lịch sử ôn Android → server. Android Room vẫn là
> nguồn sự thật cho `learning_progress`; tải nội dung từ feed hiện được cung cấp bởi API nhưng app
> Android chưa tự áp dụng các thay đổi nội dung/lời giải vào Room.

## 1. Khảo sát ứng dụng Android (đọc mã, không sao chép)

Repo: <https://github.com/nqttruong/N3-sensei> — Kotlin, Room (`N3Database`, schema version 14),
offline-first, Hilt/ViewModel. Các nhóm entity liên quan:

| Nhóm | Bảng Room | Ghi chú quan trọng cho đồng bộ |
|---|---|---|
| Nội dung học | `content_sources`, `content_packs`, `lessons`, `vocabulary`, `kanji`, `grammar`, `grammar_exercises`, `example_sentences`, tags | ID là **chuỗi** (nội dung đóng gói dùng slug, ví dụ `"keizoku"`; nội dung người dùng tạo dùng `UUID` có tiền tố). Có `license`/`license_verified`. |
| Đề thi | `exam_sets`, `exam_sections`, `exam_passages`, `exam_questions`, `exam_question_items` | `answer_index` **0-based**, `options: List<String>`, `answer_format` (choice/text), có `accepted_answers`, `audio_path`. |
| Làm bài | `exam_attempts`, `exam_attempt_items`, `exam_answers`, `exam_flags` | Thời gian là **epoch millis (Long)**; `exam_answers` lưu `question_snapshot`, `time_spent_ms`, `confidence`, `change_count`. |
| Lỗi sai | `error_records` | Một bản ghi / câu hỏi, có `error_type`, `mastery_level`, `status`. |
| SRS | `learning_progress`, `review_records`, `review_sessions`, `item_marks` | Key `(item_type, item_id)` với `ItemType = VOCABULARY/KANJI/GRAMMAR`; `ReviewRating = AGAIN/HARD/GOOD/EASY`; `review_records.request_id` để idempotent. |

## 2. Nguyên tắc

1. **Tách bốn loại dữ liệu**: câu hỏi gốc (`exams/passages/questions`), lần làm bài
   (`exam_attempts/attempt_answers`), kiến thức cần ôn (`knowledge_items/question_knowledge`) và
   lịch sử ôn (`review_items/review_events`). Mỗi loại có vòng đời và chiều đồng bộ riêng.
2. **Android là nguồn sự thật cho tiến độ SRS** (`learning_progress`). Web **không bao giờ** tự ghi
   đè tiến độ đó. Android upload lịch sử review events; Web không gửi SRS projection/đề xuất xuống
   các bảng tiến độ Android.
3. **Append-only cho sự kiện**: review events được upload theo UUID và idempotent. Android-created
   attempts chưa được upload; Web attempts chỉ được mirror xuống Android.
4. Web là nguồn authoritative cho entity nội dung Web đã publish. Android mirror áp dụng version từ
   `sync_changes`; không dùng last-writer-wins giữa thiết bị và Web.
5. API theo phiên bản `/api/v1`; thay đổi phá vỡ contract → `/api/v2`.

## 3. Ánh xạ entity

| Web (PostgreSQL) | Android (Room) | Chiều | Chuyển đổi |
|---|---|---|---|
| `exams` | `exam_sets` | Web → Android | `category` → `exam_type`; `level` → `jlpt_level`. |
| `passages` | `exam_passages` | Web → Android | `content` → `text`. |
| `questions` | `exam_questions` | Web → Android | `correct_answer` (1-based) = `answer_index` + 1. **Chỉ gửi đáp án `verified`**; câu chưa xác nhận gửi `answer_index = null`. `question_type` ánh xạ sang section/`question_type` Android qua bảng tra. |
| `exam_attempts` | Android local attempts / `SyncedExamAttemptEntity` | Web → Android mirror | Web attempt UUID và UTC timestamps; Android local attempts không được upload. |
| `attempt_answers` | Android local exam answers / `SyncedAttemptAnswerEntity` | Web → Android mirror | Web snapshot answers; Android local answers không được upload. |
| `knowledge_items` | `vocabulary` / `kanji` / `grammar` | Liên kết, không sao chép | Cần thêm `external_ref` (`"<ITEM_TYPE>:<item_id>"`) — xem mục 5. |
| `review_items` / `review_events` | `SyncedReviewItemEntity` / local review outbox | Metadata Web → Android; review events Android → Web | Event UUID idempotency; upload không cập nhật `learning_progress` hoặc `WordsReciteRecord`. |
| `sync_changes` | (chưa có) | — | Cursor tăng dần cho pull. |
| `ai_explanations` (PR3) | (chưa có) | Web → Android | Chỉ đồng bộ lời giải `approved`, không stale. `explanation_json` đã dùng chỉ số 0-based như `answer_index` của Android, có `schema_version`; khoá theo `question_id`. Phân tích lỗi người học được suy ra trên thiết bị từ `options_analysis[selected]` — không cần đồng bộ dữ liệu cá nhân. |

## 4. Giao thức đồng bộ PR6

```
POST /api/v1/sync/pair    X-Pairing-Key: <one-time pairing code> {device_name}
GET  /api/v1/sync/changes?cursor=<bigint>&limit=200    → {data: {data: [ChangeRecord], next_cursor, has_more}}
POST /api/v1/sync/push    Authorization: Bearer <device token> {events: [...]} → accepted / duplicates
```

- Operator tạo pairing code dùng một lần tại `/sync/admin/pairing-codes`; code mặc định hết hạn sau
  10 phút, DB chỉ giữ SHA-256. Pair tạo token ngẫu nhiên một lần; DB chỉ giữ SHA-256 của token.
  Android giữ token mã hóa bằng Android Keystore. Cơ chế hiện hành và giới hạn entity ở
  `android-sync-capability-matrix.md`.
- Server ghi `sync_changes` trong transaction cho các entity được hỗ trợ. Cursor allocation được
  tuần tự hóa theo commit order; client xử lý theo thứ tự và chỉ lưu cursor sau khi đã lưu xong trang.
- Thiết bị lưu `last_cursor`; pull theo trang cho tới khi hết.
- Push nhận review events của N3 Sensei, idempotent theo `request_id`, kèm snapshot khoảng ôn để
  phân tích lịch sử. Không ghi vào `learning_progress`, không tạo hoặc reschedule `review_items`.
- App Android hiện ghép nối và push event theo ID Room tăng dần; event chỉ được checkpoint sau khi
  server xác nhận đủ accepted/duplicate. Room schema không đổi và không có thao tác replace/clear.
- Change feed xuất đáp án 0-based chỉ khi `answer_status=verified`; đáp án chưa xác nhận trả null.
  Chỉ giải thích `approved` và không stale được xuất; bản ghi khác trả `data: null` để client bỏ qua/
  vô hiệu hóa bản cache tương ứng.
- Chỉ dùng trên loopback/LAN riêng hoặc HTTPS có kiểm soát. Pairing key không phải đăng nhập người
  dùng và tất cả thiết bị đã ghép nối thuộc cùng một instance cá nhân.

## 5. Thay đổi schema dự kiến khi bắt đầu đồng bộ

- `user_id` (và unique có tiền tố `user_id`) cho dữ liệu cá nhân.
- `device_id`, `client_created_at` cho `exam_attempts`, `review_events`.
- `knowledge_items.external_ref text NULL UNIQUE` để liên kết với ID chuỗi của Android
  (`VOCABULARY:<id>`), vì ID Android không phải UUID.
- Sync API chưa áp dụng pull data vào Room; cần adapter cho Room content entities và kiểm thử merge
  trên dữ liệu thật trước khi bật tính năng đó.

## 6. Rủi ro đã biết

| Rủi ro | Giảm thiểu |
|---|---|
| Lệch chỉ số đáp án (0-based vs 1-based) | Hàm chuyển đổi tập trung + test ở cả hai phía. |
| Đáp án chưa xác nhận lan sang thiết bị | Chỉ xuất `verified`; Android coi `null` là "chưa có đáp án". |
| Ghi đè SRS | Web không có API ghi `learning_progress`; chỉ gửi đề xuất. |
| Bản quyền nội dung đề (dethitiengnhat.com) | Chỉ đồng bộ đề người dùng tự nhập cho mục đích cá nhân; giữ `source_url` để truy nguồn; không phân phối lại. |
| Đồng hồ thiết bị lệch | Server từ chối thời gian tương lai > 5 phút; lưu thêm `server received_at` khi đồng bộ. |
| Room data/SRS bị ghi đè | Android chỉ đọc `review_records` để push; endpoint không nhận tiến độ hiện tại và không cập nhật Room. |
