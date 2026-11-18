# JLPT AI Review

Ứng dụng web cá nhân để học nội dung N3, luyện flashcard, ôn bài, làm đề và chữa bài JLPT.

## Web V3 — tình trạng thực tế (2026-11-18)

Menu chính hiện là **Tổng quan**, **Học tập**, **Kho đề**, **Phân tích JLPT**; Cài đặt và Hướng dẫn ở menu phụ. `/learning` có các mục Từ vựng, Kanji, Ngữ pháp và bài tổng hợp 30/7/24; `/analytics/jlpt` chứa tab Sổ lỗi sai, còn `/mistakes` chuyển hướng để giữ deep link. Tổng quan có danh ngôn Nhật và tiến độ ngắn gọn, không trùng trang phân tích.

PDF người dùng cung cấp trong thư mục gốc đã được kiểm tra là PDF text một trang với 880 hàng STT 1–880. Nguồn này được duyệt **riêng theo SHA-256 cho mục đích học cá nhân** và nhập qua worker thành 880 từ vựng, chia theo 12 bài nguồn; 41 reading thiếu trong PDF được giữ trống. Database development sau lần đồng bộ Grammar có 6 pack metadata (một pack không có item publishable), 53 source lessons, 1.447 items (880 từ, 393 Kanji, 174 Grammar) và 1.492 ví dụ. Trong 174 Grammar, 110 mẫu gốc và 220 ví dụ liên quan được nhập theo xác nhận sử dụng riêng tư; 140 ví dụ từ source riêng vẫn bị chặn. Không có quyền tái phân phối công khai. Xem `docs/PROJECT_STATUS.md`, `docs/grammar-original-110-recovery.md` và `docs/learning-content-sync.md`.

`/learning/my-words` lưu các từ do người dùng thêm, tách khỏi từ vựng nguồn. Extension build `extension/dist-v3-1/chrome` dùng cho Chrome/Edge; `extension/dist-v3-1/firefox` dành cho Firefox. Trên site được cấp quyền, extension cho chọn từ, tra exact-match từ nguồn Web đã duyệt, sửa nghĩa rồi lưu bằng credential phạm vi My Words; có TTS nếu trình duyệt có voice và hàng chờ khi offline. **Chưa có nhà cung cấp dịch JA/EN/VI tổng quát hoặc IPA tự động**, nên từ không có nguồn tin cậy được báo chưa khả dụng; không tạo nghĩa giả. Từ điển offline cá nhân, nếu có, do người vận hành tự cung cấp và không nằm trong repo công khai; khi không có file này, extension tra qua backend. Cấu hình extension tại Options và cấp credential riêng tại `/settings/sync`. Hai package chưa được xác minh bằng thao tác browser live.

Settings có 5 palette Nhật và light/dark/system. Chuyển ngôn ngữ vi/en/ja hiện bao phủ navigation và một số tiêu đề/controls, **chưa phải bản dịch toàn bộ UI**. PWA có manifest, icon và offline fallback không cache API dữ liệu cá nhân. QR pairing Web v1 có mock-client tests, nhưng Android gốc chưa quét QR và cần HTTPS hostname có chứng chỉ được điện thoại tin cậy. Xem `docs/android-qr-sync-protocol.md` và `docs/ANDROID_CODEX_QR_SYNC_PROMPT.md`; **Web QR pairing ready; Android implementation pending**.

Chạy dev: `docker compose up -d db`, `cd backend && uv run alembic upgrade head && uv run uvicorn app.main:app --reload`, ở terminal khác `cd backend && uv run python -m app.learning_content.worker`, và `cd frontend && npm run dev`. Dùng `/settings/rights` để kiểm tra quyền từng nguồn/PDF hash; thay PDF cần kiểm tra và duyệt hash mới trước import. Chạy `./scripts/check.sh` cho backend, frontend, extension và Playwright (Android không được build/test trong tác vụ Web này). Không dùng OpenAI API hay token ChatGPT trong luồng V3.

Các mục dưới đây mô tả lịch sử PR; các số liệu V2 cũ không phải snapshot hiện tại.

- **PR1** — nền tảng: quản lý đề, câu hỏi, đáp án, lưu bài làm, chấm điểm phía server.
- **PR2** — nhập đề đã làm từ website: dán văn bản, dán HTML (có adapter đã kiểm chứng cho
  dethitiengnhat.com), ảnh chụp + OCR tiếng Nhật chạy local; xem trước, sửa, xác nhận đáp án rồi mới
  lưu; tạo bài làm từ lựa chọn của bạn.

- **PR3** — chữa bài bằng AI: giải thích từng phương án, dịch nghĩa, ngữ pháp/từ vựng, phân tích lỗi
  theo lựa chọn thật của bạn. Hai chế độ: OpenAI API (Structured Outputs) hoặc ChatGPT thủ công (xuất
  prompt → dán JSON). Có kiểm định, cache, phiên bản, duyệt/từ chối, chữa hàng loạt câu sai.
- **PR4** — trích xuất kiến thức từ lời giải đã duyệt, xem điểm yếu theo dữ liệu bài làm, tạo mục ôn và
  lịch SRS với lịch sử đánh giá.
- **PR5** — Chrome Extension MV3 đọc đề N3 đang mở sau thao tác người dùng, gửi vào import draft và
  mở preview để kiểm tra trước khi lưu. Chỉ hỗ trợ các phần `/1` và `/3`; xem hướng dẫn cài đặt trong
  `docs/chrome-extension-installation.md`.
- **PR6** — pairing thiết bị, change feed và upload review event idempotent cho N3 Sensei.
- **PR6.1** — đồng bộ nội dung offline vào Room và hàng đợi review JLPT riêng; device verification vẫn
  phụ thuộc môi trường HTTPS/emulator.
- **PR7** — Kho đề hợp nhất danh sách đề, bản nháp nhập và lịch sử theo từng đề; chữa từng attempt bằng
  ChatGPT thủ công, duyệt lời giải rồi trích xuất vào Kho kiến thức.

Navigation Web V2 trước V3 gồm **Tổng quan & Phân tích**, **Học tập**, **Kho đề & Thi thử**, **Sổ lỗi sai** và **Cài đặt**. Hướng dẫn sử dụng ở `/help`. Kho kiến thức và Web review cũ không còn trong menu; dữ liệu và API vẫn được giữ.
Trong Kho đề, tab **Đề đã lưu** có
thống kê attempts/lời giải hiện hành; tab **Bản nháp nhập** tiếp tục workflow preview → verify → commit.
Lịch sử bài làm nằm ở chi tiết từng đề. Web không đưa SRS review session vào menu; dữ liệu, backend API,
scheduler và Android sync vẫn được giữ nguyên. Xem `docs/chatgpt-exam-review-workflow.md`.

Thi thử lưu attempt trên Web và chỉ chấm đáp án đã xác nhận. Sổ lỗi sai và Phân tích JLPT được
tính từ Web attempts/imported attempts; Android hiện chưa upload lịch sử thi hoặc trạng thái sổ lỗi.
Android pull nhận Web content/attempt mirrors và push review events theo PR6.1, nhưng điều đó không
đồng nghĩa Android exam history đã đồng bộ hai chiều. Audit/mapping: `docs/android-bidirectional-sync-audit.md`,
`docs/android-web-data-mapping.md`, `docs/android-web-sync-gap.md`.

Web có mục **Học tập** cho từ vựng, Kanji và ngữ pháp từ các Android content pack được phép sử dụng theo source. Có browser bài học, flashcard luyện bài, bài trắc nghiệm ngữ pháp từ source được phép, ôn SRS và nội dung đã lưu. Practice ratings chỉ ghi kết quả phiên như Android; nút Ôn bài mới cập nhật SRS Web riêng. Dashboard hiển thị tiến độ Web thật; không lấy tiến độ từ Android Room.
Sync worker chỉ đọc JSON asset Git-tracked, nhận diện thay đổi bằng SHA-256 + pack version + commit SHA,
validate rồi upsert trong một transaction; nội dung bị gỡ được archive. Worker chạy riêng FastAPI:
`cd backend && uv run python -m app.learning_content.worker`. Worker kiểm tra ngay lúc khởi động và
mặc định mỗi 30 phút; điều chỉnh bằng `ANDROID_LEARNING_SOURCE_DIR` và
`LEARNING_CONTENT_SYNC_INTERVAL_MINUTES`. Trong Settings có nút **Kiểm tra cập nhật bài học** để xếp
hàng manual check; cần worker đang chạy. Xem `docs/learning-content-sync.md` và
`docs/android-learning-data-inventory.md`.

Nguồn nội dung có `licenseVerified=true` được nhập mặc định. Nguồn chưa xác minh chỉ được nhập khi người vận hành khai báo riêng quyền sử dụng cá nhân tại `/settings/rights` (source ID, chủ quyền, căn cứ, phạm vi, ghi nguồn). Không cấp quyền tái phân phối công khai. Ở thời điểm V2, Mimikara Android JSON có 880 vocabulary items và 870 examples nhưng hai source liên quan chưa được khai báo nên dev DB có 0 từ; V3 đã nhập **PDF riêng** 880 từ theo quyền và hash của đúng PDF. Illustration pack có 7 câu luyện ngữ pháp vẫn chưa được khai báo; UI chỉ hiển thị bài luyện khi source có quyền và đã nhập. Không dùng dữ liệu giả. Xem `docs/android-web-v2-feature-audit.md`.
Sync nội dung không đọc private Room database, không chuyển progress/scheduler/backup và không thay đổi
learning progress hay nội dung người dùng tạo trên Web. Không chạy script Android hoặc `git pull` trong
repository Android; thay đổi source phải hiện trong checkout Git cục bộ để worker nhận ra.

Máy chủ không tự tải URL. AI không bao giờ thay đổi đáp án chuẩn. ChatGPT Web workflow là thủ công và không
yêu cầu API key; OpenAI API là provider riêng, chỉ khả dụng khi người vận hành chủ động cấu hình.

| Thành phần | Công nghệ |
|---|---|
| Frontend | Next.js 16 (App Router), TypeScript strict, Tailwind CSS 4, shadcn/ui, TanStack Query, React Hook Form, Zod |
| Backend | Python 3.13, FastAPI, Pydantic v2, SQLAlchemy 2, Alembic, BeautifulSoup + lxml, Pillow |
| OCR (tuỳ chọn) | Tesseract 5 + dữ liệu `jpn`, chạy local |
| AI (tuỳ chọn) | OpenAI Responses API + Structured Outputs (SDK `openai` 2.x); hoặc ChatGPT thủ công |
| Database | PostgreSQL 17 (Docker Compose) |
| Test | Pytest, Vitest, Playwright |

```
jlpt-ai-review/
├── backend/            FastAPI app, Alembic migrations, pytest
├── frontend/           Next.js app, Vitest unit tests, Playwright e2e
├── extension/          Chrome MV3 extension (TypeScript; load unpacked từ extension/dist)
├── docs/               architecture, database-schema, api-contract, android-integration-plan, roadmap,
│                       import-pipeline, parser-adapters, import-security, manual-import-guide,
│                       ai-explanation-architecture, ai-prompt-design, ai-schema,
│                       ai-quality-validation, ai-cost-control, manual-chatgpt-workflow,
│                       chrome-extension-architecture, chrome-extension-installation,
│                       dethitiengnhat-capture, extension-security
├── scripts/            check.sh (mọi kiểm tra), reset-dev-db.sh
├── docker-compose.yml  PostgreSQL (chỉ bind 127.0.0.1)
└── .env.example
```

## Yêu cầu

- Docker + Docker Compose
- [uv](https://docs.astral.sh/uv/) (tự cài Python 3.13 nếu thiếu)
- Node.js 20.9+ (đã kiểm thử với Node 24) và npm

- Tuỳ chọn cho nhập ảnh: Tesseract + gói ngôn ngữ Nhật
  - Ubuntu/Debian: `sudo apt install tesseract-ocr tesseract-ocr-jpn`
  - macOS: `brew install tesseract tesseract-lang`
  - Không có quyền root: `conda create -p ~/ocr-env -c conda-forge tesseract` rồi đặt
    `OCR_TESSERACT_CMD=~/ocr-env/bin/tesseract` trong `.env`
  - Không cài cũng được: tab "Upload ảnh" sẽ báo OCR chưa khả dụng, các cách nhập khác vẫn hoạt động.

## 1. Cấu hình môi trường

```bash
cp .env.example .env
# đổi POSTGRES_PASSWORD và cập nhật mật khẩu tương ứng trong DATABASE_URL / TEST_DATABASE_URL
```

Frontend mặc định gọi `http://127.0.0.1:8000/api/v1`. Muốn đổi, tạo `frontend/.env.local` từ
`frontend/.env.example`.

## 2. Cài dependencies

```bash
cd backend && uv sync && cd ..
cd frontend && npm install && cd ..
```

## 3. Chạy PostgreSQL

```bash
docker compose up -d db
docker compose ps           # chờ trạng thái "healthy"
```

PostgreSQL chỉ lắng nghe trên `127.0.0.1:5433` (cổng đặt bằng `POSTGRES_PORT`).

## 4. Chạy migration (và seed tuỳ chọn)

```bash
cd backend
uv run alembic upgrade head
uv run python -m app.seed      # 3 đề mẫu tự biên soạn; chạy lại nhiều lần không bị trùng
```

## 5. Chạy backend

```bash
cd backend
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

- Health: <http://127.0.0.1:8000/api/v1/health>
- OpenAPI/Swagger: <http://127.0.0.1:8000/api/v1/docs>

## 6. Chạy frontend

```bash
cd frontend
npm run dev                    # http://127.0.0.1:3000
```

Build production: `npm run build && npm run start`.

## 7. Chạy tests

PostgreSQL phải đang chạy. Test backend tự tạo database `<tên>_test` (và `<tên>_test_migrations`),
không đụng tới database phát triển.

```bash
# Backend
cd backend
uv run pytest                  # API, validation, chấm điểm, phân trang, lỗi, migration, constraint DB
uv run ruff check . && uv run ruff format --check . && uv run mypy app

# Frontend
cd frontend
npm test                       # Vitest
npm run lint && npm run typecheck

# E2E (Playwright) — tự khởi động backend :8001 với database <tên>_e2e mới và frontend :3001
npx playwright install chromium   # lần đầu
npm run test:e2e
```

Hoặc chạy tất cả gồm extension checks: `scripts/check.sh` (thêm `--no-e2e` để bỏ Playwright).

> Playwright dùng thư mục build riêng (`.next-e2e`) nên có thể chạy song song với `npm run dev`.

Test OCR thật (`test_real_tesseract_reads_japanese_screenshot`) tự bỏ qua nếu không tìm thấy
Tesseract có `jpn`; chạy nó bằng `OCR_TESSERACT_CMD=/đường/dẫn/tesseract uv run pytest`.

## 8. Reset database phát triển

```bash
scripts/reset-dev-db.sh           # xoá + tạo lại + migrate
scripts/reset-dev-db.sh --seed    # ... và nạp seed
```

Script từ chối chạy khi `APP_ENV=production`.

Dọn bản nháp nhập đề cũ và ảnh tạm: `cd backend && uv run python -m app.imports.cleanup` (thêm
`--dry-run` để xem trước). Ảnh tải lên nằm ở `backend/var/imports/` (đổi bằng `IMPORT_STORAGE_DIR`). Xoá toàn bộ dữ liệu kể cả volume Docker:
`docker compose down -v`.

## Chạy Web V2 và nguồn học

1. Cấu hình PostgreSQL và `ANDROID_LEARNING_SOURCE_DIR` trỏ tới checkout Android local **chỉ đọc**; chạy `cd backend && uv run alembic upgrade head`. Cần backup trước migration trên DB có dữ liệu.
2. Chạy API: `cd backend && uv run uvicorn app.main:app --host 127.0.0.1 --port 8000`; chạy Web: `cd frontend && npm run dev`.
3. Chạy **một** worker riêng: `cd backend && uv run python -m app.learning_content.worker`; worker kiểm tra lúc khởi động và mỗi `LEARNING_CONTENT_SYNC_INTERVAL_MINUTES` (mặc định 30). Trạng thái và nút manual ở Cài đặt.
4. Mở `/learning` để chọn bài; flashcard luyện bài lưu kết quả phiên, Ôn bài lưu lịch SRS Web, `/learning/saved` chứa nội dung đã lưu. `/help` hướng dẫn từng luồng.
5. Nếu Vocabulary trống, mở `/settings/rights`, kiểm tra từng source và chỉ xác nhận nguồn có căn cứ quyền sử dụng cá nhân phù hợp. Đối với Mimikara cần khai báo riêng `mimikara-n3-sheet` và `mimikara-n3-vocab-examples`; worker xử lý queue sau khi lưu. Không chấp nhận tự suy ra quyền phân phối công khai.

Android repository luôn read-only. Dữ liệu Web study không được đồng bộ về Room, vì Android hiện chưa nhận entity type này. Việc kiểm thử trên thiết bị thật với HTTPS tin cậy vẫn đang chờ.

## Trang giao diện

| Đường dẫn | Nội dung |
|---|---|
| `/` | Tổng quan & Phân tích: tiến độ học Web, đề/attempt, thống kê JLPT và hoạt động gần đây |
| `/learning` | Bài học, tìm kiếm/lọc nội dung, tiến độ và ôn SRS |
| `/learning/lessons/[packId]/[lessonId]` | Chi tiết bài, ví dụ, lưu nội dung, bắt đầu flashcard |
| `/learning/study/[id]` | Phiên flashcard/ôn bài bền vững, tự đánh giá và kết quả |
| `/learning/saved` | Nội dung đã lưu và luyện lại |
| `/exams` | Kho đề: đề đã lưu, bản nháp và lối vào thi thử |
| `/exams/new` | Nhập đề: tab Dán văn bản · Dán HTML · Upload ảnh (OCR) · Tạo thủ công |
| `/imports`, `/imports/[id]` | Bản nháp nhập đề: xem trước, sửa, xác nhận đáp án, lưu thành đề, tạo bài làm |
| `/questions/[id]/explanation` | Lời giải AI của một câu: chữa, tạo lại, xuất prompt, nhập JSON, xác nhận/từ chối, phiên bản |
| `/explanations/manual` | Chữa bằng ChatGPT thủ công |
| `/exams/[id]` | Chi tiết đề: câu hỏi, đáp án đã xác nhận, thêm câu hỏi/đoạn văn, xác nhận đáp án, đổi trạng thái |
| `/exams/[id]/practice` | Làm bài (không tải đáp án về trình duyệt) |
| `/attempts`, `/attempts/[id]` | Lịch sử và chi tiết bài làm, liên kết tới đề gốc |
| `/settings/rights` | Khai báo quyền sử dụng cá nhân theo từng source nội dung |
| `/settings/sync` | Ghép nối và quản lý thiết bị Android |
| `/help` | Hướng dẫn sử dụng các chức năng đang hoạt động |
| `/knowledge` | Deep link cũ cho tri thức đã duyệt; không còn trong menu |
| `/knowledge/extract?attempt=…` | Duyệt, gộp trùng và xác nhận tri thức từ lời giải đã duyệt |
| `/reviews` | Route tương thích cũ; ôn nội dung học hiện nằm trong `/learning` |

## Nhập đề bằng Chrome Extension (PR5)

1. Cấu hình `EXTENSION_IMPORT_TOKEN` trong `.env` (ít nhất 32 ký tự), khởi động backend và frontend.
2. Build `cd extension && npm run build`, rồi cài `extension/dist` qua `chrome://extensions` → **Developer mode** → **Load unpacked**.
3. Mở Options của extension, nhập token giống backend (cùng URL local mặc định đã điền sẵn).
4. Làm đề N3 trên Dethitiengnhat và tự chấm bài nếu muốn lấy lựa chọn/kết quả.
5. Mở popup → **Đọc đề ở tab này** → kiểm tra cảnh báo → **Chuyển sang JLPT AI Review**.
6. Sửa/kiểm tra `/imports/{id}`; đáp án nguồn chưa verified. Chỉ lưu sau khi tự kiểm tra và xác nhận trong preview.

Extension không điều khiển trang nguồn và không đọc thông tin đăng nhập. Chưa xác minh live DOM sau khi chấm; chi tiết tại `docs/dethitiengnhat-capture.md`.

## Đồng bộ Android N3 Sensei (single-user)

Không cần tạo tài khoản. Mở Web **Cài đặt → Đồng bộ Android**, tạo mã ghép nối dùng một lần, rồi
nhập mã cùng URL HTTPS trong Android **Cài đặt → Đồng bộ JLPT AI Review**. Pairing chỉ cấp credential;
hãy bấm **Đồng bộ ngay** trên Android để trao đổi dữ liệu. Hướng dẫn HTTPS/LAN và revoke ở
[`docs/android-pairing-guide.md`](docs/android-pairing-guide.md).

Mã hết hạn sau 10 phút, chỉ dùng một lần; credential riêng từng thiết bị được lưu dạng hash ở
backend và Android giữ token mã hóa bằng Android Keystore. Android pull nội dung Web vào `synced_*`
và push review events idempotently. Android chưa upload learning progress, saved words, exam
attempts/answers, mistake notebook hay analytics. Không có device/emulator live verification trong
lượt này. Xem [`docs/android-sync-capability-matrix.md`](docs/android-sync-capability-matrix.md),
[`docs/sync-security-review.md`](docs/sync-security-review.md) và `docs/PROJECT_STATUS.md`.

## Chữa bài bằng AI (PR3)

### Cấu hình OpenAI (tuỳ chọn)

Trong `.env` (chỉ backend đọc; trình duyệt không bao giờ thấy key):

```bash
AI_PROVIDER=openai
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-6-astra          # model bất kỳ hỗ trợ Responses API + Structured Outputs
AI_MAX_REQUESTS_PER_DAY=200
# Tuỳ chọn: ngân sách USD/tháng — cần điền giá hiện hành của model (USD / 1M token)
AI_MONTHLY_BUDGET_USD=5
AI_PRICE_INPUT_PER_1M_TOKENS=...
AI_PRICE_OUTPUT_PER_1M_TOKENS=...
```

Khởi động lại backend. Worker xử lý chữa hàng loạt chạy cùng backend (hoặc riêng:
`uv run python -m app.explanations.worker`, khi đó đặt `AI_WORKER_ENABLED=false` cho API). Không có key:
ứng dụng vẫn chạy, các nút gọi AI được thay bằng "Xuất prompt cho ChatGPT".

Kiểm tra key thật (tốn một lần gọi, không chạy mặc định):
`RUN_OPENAI_LIVE=1 uv run pytest tests/test_openai_live.py -s`.

### Sử dụng

- **Chữa một câu**: trang bài làm → "Lời giải" ở câu bất kỳ (hoặc trang đề → "Lời giải") → **Chữa bằng AI**.
  Chỉ câu có đáp án **đã xác nhận** mới chữa được; câu đọc hiểu cần đoạn văn.
- **Chữa hàng loạt câu sai**: trang bài làm → khung *Chữa bài bằng AI* → chọn câu → **AI chữa các câu
  sai**. Tiến độ hiển thị từng câu, vẫn tiếp tục sau khi tải lại trang; câu lỗi có nút **Chạy lại câu lỗi**.
- **ChatGPT thủ công**: chọn câu sai → **Xuất prompt cho ChatGPT** → **Chữa bài với ChatGPT** để sao chép
  prompt và mở chatgpt.com → tự dán/gửi rồi sao chép JSON trả về → **Kiểm tra & xem trước** → **Xác nhận lưu**.
  Xem `docs/manual-chatgpt-workflow.md`. Không cần API key; app không đọc credential hay điều khiển ChatGPT.
- **Duyệt**: lời giải mới luôn "Chờ xác nhận"/"Cần kiểm tra". Đọc kỹ rồi **Xác nhận lời giải**, hoặc
  **Đánh dấu chưa chính xác** (kèm ghi chú) nếu sai.
- **Tạo lại lời giải**: nút **Tạo lại lời giải** (một câu) hoặc **Chữa lại** (hàng loạt). Lời giải cũ
  vẫn xem được trong *Các phiên bản*. Đổi nội dung câu hoặc đáp án đã xác nhận ⇒ lời giải cũ thành
  "Đã cũ" và không được dùng làm lời giải hiện hành.
- AI nghi ngờ đáp án nguồn sai ⇒ cảnh báo đỏ trên lời giải; đáp án **không** bị đổi — tự kiểm tra trong
  trang đề.

## Nhập đề (PR2)

Xem `docs/manual-import-guide.md` (cách dùng), `docs/import-pipeline.md` (luồng xử lý),
`docs/parser-adapters.md` (mức hỗ trợ Dethitiengnhat thực tế), `docs/import-security.md`.
AI: `docs/ai-explanation-architecture.md`, `docs/ai-prompt-design.md`, `docs/ai-schema.md`,
`docs/ai-quality-validation.md`, `docs/ai-cost-control.md`.

## Bảo mật

Dự án dành cho chạy local: mọi dịch vụ bind `127.0.0.1`, CORS theo allowlist, không có secret trong
mã nguồn, không lưu API key ở frontend, không có endpoint tải URL tuỳ ý. HTML dán vào không bao giờ
được chạy hay render; ảnh được kiểm tra theo nội dung và mã hoá lại. **Phải bổ sung
authentication trước khi deploy lên cloud** — xem `docs/architecture.md` §4–5.

## Dữ liệu

Seed (`backend/app/seed/data.py`) gồm các câu N3 **tự biên soạn** chỉ để phát triển/kiểm thử; không
dùng nội dung có bản quyền từ dethitiengnhat.com.
