# Kiến trúc — JLPT AI Review (PR1–PR4)

PR1 dựng **nền tảng**: lưu đề, câu hỏi, đáp án và chấm bài làm. PR2 thêm **luồng nhập đề** từ nội
dung người dùng cung cấp (văn bản, HTML, ảnh + OCR local) qua bản nháp có xem trước và xác nhận.
PR3 thêm **chữa bài bằng AI** (OpenAI Structured Outputs hoặc ChatGPT thủ công) — xem
`ai-explanation-architecture.md`. PR4 thêm knowledge extraction, weakness analytics và SRS. Tích hợp
ChatGPT Web Chat dùng prompt/JSON thủ công; app không truy cập credential hoặc điều khiển ChatGPT. Không có Chrome Extension, scraping phía
server hay chỉnh sửa ứng dụng Android.

## 1. Tổng quan

```
┌──────────────────────────┐   HTTP/JSON (CORS allowlist)   ┌───────────────────────────┐
│ Frontend — Next.js 16    │ ─────────────────────────────▶ │ Backend — FastAPI          │
│ 127.0.0.1:3000           │      /api/v1/...               │ 127.0.0.1:8000             │
│ React Query, RHF + Zod   │ ◀───────────────────────────── │ Pydantic v2, SQLAlchemy 2  │
└──────────────────────────┘   {data, meta} | {error}       └─────────────┬─────────────┘
                                                                          │ psycopg 3
          (tương lai) Android N3 Sensei ── /api/v1/sync ──▶ (PR sau)      ▼
                                                           ┌───────────────────────────┐
                                                           │ PostgreSQL 17 (Docker)     │
                                                           │ 127.0.0.1:5433, UTF-8, UTC │
                                                           │ schema quản lý bằng Alembic│
                                                           └───────────────────────────┘
```

- Frontend **không** truy cập database; mọi dữ liệu đi qua API phiên bản `/api/v1`.
- Logic nghiệp vụ (chấm điểm, chống trùng, ràng buộc đáp án) nằm ở backend (`service.py`)
  và được củng cố lần nữa bằng constraint trong database. Giao diện chỉ hiển thị.
- Hai tiến trình chạy độc lập; có thể deploy riêng (ví dụ: frontend tĩnh/Node, backend container,
  PostgreSQL managed).

## 2. Backend

```
backend/app/
  core/          config (pydantic-settings), errors (envelope lỗi), responses (envelope + phân trang),
                 security (điểm cắm auth), health, schemas dùng chung, time
  database/      Base + naming convention, mixins UUID/timestamp, session, enums
  exams/         ExamSource, Exam, Passage, Question — models/schemas/service/router
  attempts/      ExamAttempt, AttemptAnswer — chấm điểm khi nộp
  analytics/     Tổng hợp Dashboard, điểm yếu và tiến độ ôn
  imports/       (PR2) Bản nháp nhập đề: adapters/ (text, dethitiengnhat HTML, generic HTML), OCR,
                 kiểm tra ảnh, lưu file, validation, phát hiện trùng, commit, cleanup
  explanations/  (PR3) Lời giải AI: provider (OpenAI), prompt theo phiên bản, kiểm định 2 lớp,
                 cache/stale, duyệt, chế độ ChatGPT thủ công, job hàng loạt + worker
  knowledge/     (PR4) Trích xuất/dedup tri thức từ lời giải đã duyệt, graph và review items
  reviews/       (PR4) Hàng đợi, phiên ôn, lịch SRS và event history
  practice/      (PR4) Bài tập AI/manual có kiểm định và duyệt trước khi dùng
  sync/          Chỉ model + interface ChangeFeed
  seed/          Bộ dữ liệu tự biên soạn
```

Các module tính năng giữ ranh giới model/schema/service/router; analytics đọc thống kê đã lưu và
không gọi AI. Knowledge chỉ được tạo từ lời giải đã duyệt. Lượt xem/đọc không đổi lịch ôn; chỉ event
đánh giá mới cập nhật trạng thái SRS.

### Quyết định kỹ thuật

| Chủ đề | Quyết định | Lý do |
|---|---|---|
| ORM | SQLAlchemy 2.x **sync** + psycopg 3 | Ứng dụng một người dùng, tải thấp; sync đơn giản hơn, test dễ hơn. FastAPI chạy endpoint sync trong threadpool. Có thể chuyển async sau mà không đổi contract. |
| ID | UUID v4 (sinh ở app, có `gen_random_uuid()` dự phòng) | Thiết bị Android/offline có thể tự sinh ID không xung đột khi đồng bộ. |
| Enum | `TEXT` + `CHECK` thay vì PG `ENUM` | Thêm giá trị chỉ cần migration nhỏ; giá trị khớp 1-1 với JSON và enum Kotlin. |
| Thời gian | `timestamptz`, session `TIME ZONE 'UTC'`, input bắt buộc có offset và được chuẩn hoá về UTC | Tránh lỗi múi giờ (máy dev đang ở UTC+7). |
| Envelope | `{"data": ...}`, `{"data": [...], "meta": {...}}`, `{"error": {code, message, details}}` | Client xử lý thống nhất; không bao giờ trả 200 cho lỗi. |
| Phân trang | `page` (≥1) + `page_size` (1–100), `meta.total/total_pages`, sắp xếp ổn định (`created_at DESC, id`) | UI dùng page; Android sync dùng cursor commit-ordered và snapshot (`sync_changes.id`, migration 0007). |
| Validation | Pydantic (`extra="forbid"`, trim, giới hạn độ dài) → kiểm tra nghiệp vụ trong service → constraint DB | Ba lớp; lớp DB bảo vệ khi có bug hoặc ghi trực tiếp. |
| Đồng thời | `SELECT ... FOR UPDATE` trên hàng `exams` khi thêm câu hỏi / nộp bài | Tuần tự hoá thao tác trên cùng một đề; `IntegrityError` còn sót được map sang 409. |
| Unicode | Lưu nguyên văn bản gốc (không NFKC); chỉ chuẩn hoá NFKC + khoảng trắng khi tính `content_hash` | Giữ chính xác chữ Nhật toàn/nửa độ rộng, nhưng vẫn phát hiện câu trùng gõ lại. |
| Cấu hình | `pydantic-settings` đọc `.env` ở gốc repo; CORS không cho phép `*` | Không hardcode secret; allowlist rõ ràng. |

### Quy tắc đáp án (quan trọng)

- `questions.answer_status ∈ {missing, unverified, verified}`; DB ép `(missing) ⇔ correct_answer IS NULL`.
- API mặc định `unverified` khi có đáp án mà không chỉ rõ — không bao giờ tự tin tưởng.
- Sửa `correct_answer` mà không gửi lại `answer_status` ⇒ tự hạ về `unverified`.
- **Chỉ đáp án `verified` được dùng để chấm** và hiển thị là "đáp án chuẩn".
- Đáp án do AI suy luận (PR sau) chỉ nằm trong `ai_explanations.explanation_json`, không bao giờ tự
  ghi vào `questions.correct_answer`.

### Chấm điểm

Khi `POST /attempts`, trong **một transaction**: khoá đề, đọc toàn bộ câu hỏi, tạo một
`attempt_answers` cho *mọi* câu (câu không gửi = bỏ trống), phân loại:

| Trường hợp | `is_correct` | Đếm vào |
|---|---|---|
| Không chọn | `NULL` | `unanswered_count` |
| Có chọn, câu không có đáp án verified | `NULL` | `ungraded_count` |
| Chọn = đáp án verified | `true` | `correct_count` |
| Chọn ≠ đáp án verified | `false` | `incorrect_count` |

Đáp án dùng để chấm được chụp lại vào `correct_answer_snapshot`, nên sửa đề sau đó không làm thay
đổi lịch sử. `accuracy = correct / (correct + incorrect)`.

## 3. Frontend

```
frontend/src/
  app/                 Route (App Router). Page là Server Component mỏng bọc <Suspense>.
  features/            dashboard, exams, attempts — Client Component dùng React Query
  components/          app-shell, main-nav, states (Loading/Empty/Error), badges, form-field, ui/ (shadcn)
  lib/api/             client (fetch + ApiError), endpoints, types, query keys
  lib/schemas.ts       Zod schema cho form (dùng chung với unit test)
```

- Next.js 16 bật `cacheComponents`: các hook đọc URL (`useParams`, `useSearchParams`, `usePathname`)
  được đặt trong `<Suspense>` để phần khung trang vẫn prerender được.
- Dữ liệu lấy hoàn toàn phía trình duyệt bằng TanStack Query (dữ liệu cá nhân, luôn mới). Sau
  mutation, invalidate các query key liên quan (đề, danh sách, dashboard).
- Bộ lọc/tìm kiếm/trang của Kho đề nằm trên URL → reload hoặc chia sẻ link giữ nguyên trạng thái.
- Chế độ làm bài gọi `include_answers=false` nên trình duyệt không tải đáp án trước khi nộp.
- Chức năng chưa có (nhập từ URL, OCR, Chrome Extension) chỉ hiển thị thông báo "chưa khả dụng",
  không có nút giả.

## 4. Bảo mật (môi trường cá nhân, local)

- Backend, frontend và PostgreSQL chỉ bind `127.0.0.1`.
- CORS allowlist lấy từ `CORS_ORIGINS`; cấu hình từ chối `*`. `allow_credentials=False`.
- Không có secret trong mã; `.env` bị gitignore, `.env.example` chỉ chứa giá trị mẫu.
- Frontend chỉ có biến `NEXT_PUBLIC_API_BASE_URL` (không bí mật).
- Lỗi DB không lộ SQL ra client (`IntegrityError` → 409 chung, lỗi khác → 500 chung + log).
- `app/core/security.py::get_principal` là dependency gắn vào mọi router: thêm auth trước khi deploy
  cloud chỉ cần sửa một chỗ (trả 401 khi thiếu/ sai token).
- Không có endpoint import URL tuỳ ý (tránh SSRF). `source_url` chỉ được lưu, không được tải.

## 5. Sẵn sàng deploy cloud (chưa thực hiện)

Cần làm trước khi public: authentication thật, HTTPS/reverse proxy, `APP_ENV=production`,
PostgreSQL managed + backup, giới hạn tần suất, chạy `alembic upgrade head` trong pipeline deploy,
cập nhật `CORS_ORIGINS`. Chi tiết theo phase trong `roadmap.md`.

## 6. PR2 — nhập đề

Chi tiết: `import-pipeline.md`, `parser-adapters.md`, `import-security.md`.

| Quyết định | Lý do |
|---|---|
| Draft riêng (`import_drafts.content` JSONB) thay vì ghi thẳng `questions` | Dữ liệu parser chưa đáng tin; người dùng phải xem/sửa/xác nhận trước. JSONB phù hợp vì cấu trúc draft là tạm thời và được sửa nguyên khối; dữ liệu lâu dài vẫn vào bảng quan hệ khi commit. |
| Adapter là hàm thuần, chọn theo cấu trúc phát hiện được | Dễ test bằng fixture; thêm website mới không đụng API. Cấu trúc lạ → adapter chung + bắt kiểm tra, không giả vờ parse thành công. |
| Ba trường đáp án (`site_answer`, `user_answer`, `correct_answer`) + `answer_confirmed` | Không nhầm lựa chọn của người dùng hay đáp án trang với đáp án chuẩn; chỉ người dùng xác nhận mới thành `verified`. |
| `questions.answer_source` (provenance) | Biết đáp án đến từ đâu (manual / site_key / user_entered / ocr) mà không trộn với độ tin cậy (`answer_status`). |
| `questions.fingerprint` (không gồm passage) | Phát hiện cùng câu ở đề khác; `content_hash` của PR1 gồm passage nên chỉ chống trùng trong một đề. |
| Tesseract qua subprocess | Chạy hoàn toàn local, có dữ liệu `jpn` chính thức, không cần GPU/mô hình nặng; giao diện `OcrEngine` cho phép thay engine. |
| OCR đồng bộ trong request | Đơn giản cho máy cá nhân; ảnh được lưu và trạng thái `parsing` được ghi trước khi OCR để không mất dấu khi lỗi. Hàng đợi nền là việc sau nếu cần. |
| Ảnh mã hoá lại thành PNG | Loại metadata/payload ẩn, giữ nguyên độ phân giải cho chữ Nhật. |
| Hàm chấm điểm dùng chung (`build_graded_attempt`) | Bài làm nhập vào được chấm đúng như bài làm trong app; commit tạo đề + câu + bài làm trong một transaction. |
| Markup nội tuyến tối thiểu (`<u>`, `<ruby>`) lưu dạng text | Gạch chân là một phần của đề 漢字読み; furigana cần giữ. Frontend dựng phần tử an toàn, không dùng innerHTML. |

## 7. PR3 — chữa bài bằng AI

Chi tiết trong `ai-explanation-architecture.md`. Nguyên tắc: AI đọc dữ liệu thật trong DB, chỉ chữa câu
có đáp án đã xác nhận, không bao giờ ghi vào `questions`; mọi lời giải qua kiểm định 2 lớp và chỉ
thành `approved` khi người dùng xác nhận. Job hàng loạt lưu trong DB, worker có lease để khôi phục sau
restart; API khởi động worker trong lifespan khi AI khả dụng.

## 8. Khác biệt so với kế hoạch ban đầu

Xem `database-schema.md` (mục "Điều chỉnh so với đề xuất") và `api-contract.md` (endpoint bổ sung).
