# Roadmap và trạng thái hiện tại

## Web V3 (2026-11-17) — implementation ongoing

- PDF Mimikara người dùng cung cấp: 880 từ STT 1–880 đã được trích xuất từ một trang text-based và nhập có quyền sử dụng cá nhân theo SHA-256 riêng; Vocabulary Web có dữ liệu thật. Không nhập ví dụ từ Android Mimikara JSON còn bị gate. Pipeline re-import idempotent và giữ nguồn theo row ID. Bài tổng hợp 30/7/24 đã có cùng tiến độ item cũ.
- Từ của tôi có bảng và giao diện riêng, extension credential giới hạn phạm vi, popup tra exact-match từ nguồn đã duyệt, lưu từ offline retry, Chrome/Edge + Firefox packages. Translation/IPA tự động ba ngôn ngữ và browser live QA vẫn còn mở.
- Theme palette/light/dark/system đã triển khai; i18n vi/en/ja còn mới bao phủ shell và một số màn. Cần dịch đầy đủ labels/forms/errors/Help và thử accessibility/SSR trên tất cả routes trước khi gọi hoàn thành.
- Navigation mới tách Tổng quan và Phân tích; Sổ lỗi sai nằm trong tab Phân tích; route cũ redirect. PWA manifest/offline fallback có, chưa test install trên thiết bị.
- QR pairing protocol Web + mock client có; Android chưa có scanner. Cần triển khai riêng theo `ANDROID_CODEX_QR_SYNC_PROMPT.md`, chuẩn bị HTTPS hostname/certificate được điện thoại tin cậy, rồi mới kiểm chứng live. Không mở sync cho Android progress/exam/saved words khi client không hỗ trợ.
- Alembic mới `0012`–`0014` đã áp dụng sau backup dev DB. Xem `PROJECT_STATUS.md` cho số liệu và tests mới nhất. Android hoàn toàn read-only; không commit/push.

### Phần cần hoàn tất trước khi đóng V3

1. Dịch toàn bộ UI, Help, form và error states sang en/ja; kiểm chứng fallback nội dung học.
2. Chọn/đánh giá nguồn từ điển hoặc provider công khai có giấy phép và quyền chia sẻ phù hợp để hỗ trợ JA↔EN↔VI, cách đọc và IPA có xác minh; không trả kết quả bịa.
3. Kiểm thử extension trực tiếp trên Chrome, Edge, Firefox ở trang được phép và trang hạn chế; kiểm tra quyền từng site, TTS và offline queue thực tế.
4. Kiểm thử PWA install/offline fallback, theme/locale mobile, accessibility và E2E với dữ liệu V3.
5. Cấu hình HTTPS endpoint an toàn, làm Android QR ở phiên khác, rồi đo sync thực tế trên thiết bị. Android hiện không thể push tiến độ, attempt hay saved words.

## Web V2 (2026-11-17)

- Đã triển khai migrations `0010` cho quyền/tiến độ học Web và `0011` cho đáp án bài luyện ngữ pháp; đã áp dụng lên dev DB sau backup.
- Đã có Learning Home/lesson browser, flashcard luyện theo bài, ôn SRS, bookmark, bài luyện ngữ pháp khi source được phép, dashboard hợp nhất, hướng dẫn `/help`, menu năm mục. Android read-only; xem `android-web-v2-feature-audit.md`.
- Chưa đóng V2: nguồn Mimikara 880 từ chưa được khai báo quyền cụ thể nên Vocabulary vẫn 0; cần quyết định quyền theo `pack_id/source_id`, sau đó worker xử lý.
- Parity còn thiếu: Android progress/saved words/attempts local không có upload, Web chưa có timer/resume/listening/text answer và biểu đồ học theo kỳ; cần làm riêng, không tuyên bố sync hai chiều live.
- Cần kiểm chứng UX trên trình duyệt với dữ liệu thực, HTTPS + thiết bị Android thật và quản lý worker bằng supervisor khi deploy.

---

# Roadmap

Trạng thái được đối chiếu với mã nguồn, migrations và kiểm thử gần nhất. Thứ tự PR theo yêu cầu dự án.

| PR | Phạm vi | Trạng thái hiện tại |
|---|---|---|
| **PR1** | Next.js + FastAPI + PostgreSQL; quản lý đề/câu hỏi/bài làm, dashboard | Đã triển khai; backend/frontend/E2E được kiểm tra trong đợt audit 2026-11-11. |
| **PR2** | Import text, HTML, ảnh + OCR cục bộ, draft, kiểm tra, xác nhận, commit idempotent | Đã triển khai; test parser/import/E2E đạt. OCR thật bị skip khi thiếu Tesseract `jpn`. |
| **PR3** | Giải thích bằng OpenAI API hoặc prompt/JSON thủ công; lưu, kiểm định, duyệt và batch jobs | Đã triển khai. Đường manual được test end-to-end. OpenAI live test chưa chạy; không có bằng chứng inference thật. |
| **PR3.5** | ChatGPT Web Chat thủ công: mở ChatGPT, trao đổi prompt/JSON do người dùng chuyển | Đã triển khai trên nền manual prompt/JSON PR3; không dùng API key, OAuth/token hoặc truy cập credential. Kiểm thử lại trong đợt hiện tại. |
| **PR4** | Trích tri thức từ lời giải đã duyệt, dedup/merge, weakness analytics, review history và SRS | Backend, migration `0004`, frontend knowledge/reviews và test đã triển khai. Kiểm tra trong đợt audit/hoàn thiện này. |
| **PR5** | Chrome Extension gửi DOM đã render từ Dethitiengnhat sau khi người dùng chấm | Đã triển khai extension, endpoint capture có bearer secret + loopback, preview draft và migration `0005`; fixture/integration checks chạy trong `scripts/check.sh`. Chưa xác minh DOM runtime sau khi chấm trên trang live. |
| **PR6** | Đồng bộ Android N3 Sensei: pairing thiết bị, change feed và review events idempotent | Đã có ở revision `0006`; trước PR6.1 pull feed chưa được áp dụng vào Room. |
| **PR6.1** | Đồng bộ nội dung offline, review queue riêng và outbox sự kiện Android | Đã implementation và integration-test theo lần xác minh 2026-11-12; pairing/sync với backend thật trên thiết bị vẫn pending. Chi tiết ở `docs/PROJECT_STATUS.md`. |
| **PR7** | ChatGPT Exam Review Integration và hợp nhất UI Kho đề | Đã triển khai trong worktree 2026-11-13; `scripts/check.sh` đạt backend/frontend/extension/Playwright. Không cần OpenAI API key cho manual workflow. |
| **PR8 / Android-Web JLPT** | Thi thử, sổ lỗi sai, phân tích và đồng bộ Android | Web routes/API implemented and tested. Read-only audit xác nhận Android chưa upload exam attempts/mistake records; không gọi đây là bidirectional live sync. |
| **PR9 / Android learning content sync** | Scanner read-only, detect thay đổi content pack, PostgreSQL mirror/audit, worker định kỳ và UI Học tập/Settings | Đã implementation trong worktree; scanner xác minh source local và license-gated projection. Migration `0008` chưa áp dụng vào dev DB; worker/source checkout cần cấu hình để vận hành. Chưa đồng bộ tiến độ cá nhân Room. |

## PR9 — Tự động phát hiện và đồng bộ nội dung học

- Android content source đã xác minh là Git-tracked JSON content packs trong checkout Android local; scanner dựa trên SHA-256 file/manifest, pack version và commit SHA. Scanner không đọc Room, không lấy remote, không chạy code Android.
- Import có validate toàn bộ pack và references trước transaction, deterministic stable IDs, audit trail, source version, PostgreSQL upsert và soft archive. Nội dung Web hiện có cùng tiến độ học không bị cập nhật/xóa.
- Worker riêng enqueue khi khởi động và theo interval; manual Settings enqueue job. Cần đúng một worker process, PostgreSQL và Alembic `0008` đã được triển khai trước khi bật.
- Tại audit 2026-11-16, phần source metadata khai báo quyền rõ ràng gồm 64 grammar, 393 Kanji, 1.272 examples. Nội dung chưa xác minh bị chặn; đây không phải rà soát pháp lý độc lập.
- Test tự động và trạng thái migration/DB được cập nhật trong `docs/PROJECT_STATUS.md`. Sync runtime production chưa được xác minh; Android progress/Room không nằm trong contract.

## Android ↔ Web JLPT worktree

- Menu thêm Sổ lỗi sai và Phân tích JLPT; Kho đề giữ draft/history/practice.
- `/mistakes` nhóm câu hỏi có graded wrong occurrence từ Web attempts/imported attempts. `/analytics/jlpt` chỉ tính dữ liệu Web; missing Android attempts được báo là chưa đồng bộ.
- Backend thêm paginated `GET /attempts/mistakes` và read-only aggregate `GET /analytics/jlpt`; không migration database mới.
- Mock exam reuse các API hiện có. Web và Android cùng giữ outcome correct/wrong/unanswered, nhưng accuracy denominator khác nhau; trang kết quả Web trình bày rõ correct/total riêng. Web chưa có timer field, section/listening hay text answer.
- PR6/6.1 Android pull content/feed mirrors và push review events đã có source. Android attempt/error upload chưa có; **Backend ready — Android client change required.**
- Alembic head `0007`, database hiện tại `0006`; không migrate database hiện tại. Không chạy Android Gradle/test hoặc xác minh live device.
- Kiểm tra cuối `./scripts/check.sh`: backend 207 passed/2 skipped, frontend 45 passed + build, extension 11 passed + build, Playwright 13 passed. Skip gồm OCR tiếng Nhật chưa cài và test OpenAI live opt-in.

## PR7 — Luồng Kho đề → Lịch sử → Chữa bằng ChatGPT

- Menu web chỉ còn Tổng quan, Kho đề, Kho kiến thức. `/imports`, `/attempts` index và `/reviews` redirect về Kho đề để bookmark cũ không gãy; trang kết quả `/attempts/{id}` vẫn hoạt động.
- `/exams` có tab đề đã lưu và bản nháp nhập. Import API hiện có tiếp tục cung cấp preview, verify và commit. Chrome Extension tiếp tục tạo draft; người dùng mở extension đã cài để gửi capture.
- Chi tiết đề tải lịch sử qua `GET /attempts?exam_id=…` có phân trang; mỗi attempt đi tới kết quả và panel ChatGPT PR3/PR3.5.
- ChatGPT handoff là thủ công: chọn câu sai hoặc toàn bộ đề, export prompt có IDs/selected/verified answer/context (20 câu mỗi nhóm), copy + mở chatgpt.com, nhập JSON, validate, save pending, rồi người dùng approve. Không điều khiển ChatGPT và không cần token.
- Không có migration database mới cho PR7. API response mở rộng thống kê đọc; backend SRS, review records và Android sync giữ nguyên. Không xóa lịch sử.

## Công việc còn mở

### PR3 / AI

- Không có OpenAI live test hoặc số liệu độ trễ/chi phí thực tế. `tests/test_openai_live.py` là opt-in và không được chạy trong kiểm thử mặc định.
- Chưa đánh giá chất lượng trên corpus N3 có lời giải chuẩn độc lập; validator hiện chỉ kiểm cấu trúc và quy tắc.
- Worker batch chạy trong tiến trình API; deployment nhiều worker/rate limit dùng chung cần thiết kế thêm.
- Không có chế độ phân tích câu chưa xác nhận đáp án (ngoài phạm vi hiện tại).

### PR3.5 / ChatGPT Web Chat

- Người dùng tự mở ChatGPT, dán prompt và gửi; sau đó tự sao chép JSON trả lời về app.
- App chỉ ghi prompt vào clipboard theo thao tác rõ ràng và mở `https://chatgpt.com/`; không đọc trang, cookie, session hoặc credential.
- Xem `docs/manual-chatgpt-workflow.md`. Báo cáo nghiên cứu OAuth cũ được giữ làm tư liệu lịch sử và không còn là hướng triển khai PR3.5.

### PR2 / Import

- OCR đồng bộ; rate limiter import chỉ dùng trong bộ nhớ một tiến trình.
- Chưa nhận diện câu nghe (聴解) hoặc hình minh hoạ trong câu 情報検索.
- Adapter chỉ kiểm chứng cho trang đề Dethitiengnhat; trang Phòng thi chưa khảo sát.
- Gạch chân mất khi dán text/OCR; HTML giữ được định dạng này.

### PR5 / Chrome Extension

- Adapter hỗ trợ các trang `/jlpt/N3/{exam}/1` và `/3`; phần nghe `/2` chưa hỗ trợ.
- Kết quả graded DOM live chưa được quan sát trong trình duyệt; fixture là bằng chứng kiểm thử hiện tại.
- Extension chỉ tạo import draft; người dùng phải rà soát và xác nhận đáp án trong preview trước khi commit thành đề/bài làm.
- Cần cấu hình `EXTENSION_IMPORT_TOKEN` riêng ở backend và Options của extension. Route tắt mặc định khi chưa cấu hình.

### PR1 / nền tảng

- Chưa có xác thực người dùng/thiết bị để deploy công khai. API hiện là app cá nhân/local.
- Feed `sync_changes` lưu snapshot payload và cursor tuần tự theo commit (migration `0007`).
- UI chưa có đầy đủ thao tác sửa/xoá đề, đoạn văn và sửa câu đã lưu.
- Chưa có CI pipeline.
- Audio cho câu nghe chưa nằm trong phạm vi.
