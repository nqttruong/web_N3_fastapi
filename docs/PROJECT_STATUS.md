# Project Status — JLPT AI Review / N3 Sensei

**Cập nhật:** 2026-11-18; xem mục Grammar N3 bên dưới để biết số liệu hiện tại. Các mục V2/PR cũ là lịch sử, không phản ánh số liệu DB hiện tại. PR7 ở HEAD `d83e3bc`; worktree chứa thay đổi chưa commit từ trước và trong V3. Android chỉ được audit read-only. Live device sync chưa được xác minh.

## 2026-11-18 — Khôi phục Grammar N3 gốc

- Database development hiện ở Alembic `0014`; trước thao tác có 64 Grammar, 0 Grammar examples/links, 10 Grammar progress rows, 19 Grammar study events và 0 rights record cho pack `n3-grammar`.
- Đã xác minh Android JSON v4 chứa đúng 110 mẫu gốc (`n3g-g001`–`n3g-g110`, source `vnjp-np-001`–`vnjp-np-110`) và 64 mẫu PDF (`n3g-g111`–`n3g-g174`). Importer không thiếu mapping: scanner loại 110 source gốc vì `licenseVerified=false` lịch sử và chưa có private grant theo từng `(pack_id, source_id)`. Không có API/UI cap 64.
- Ghi 110 source-specific private-use declarations dựa trên xác nhận trực tiếp của chủ dự án ngày 2026-11-18. Scope chỉ cho instance Web cá nhân; không cấp quyền phân phối công khai. Giữ metadata Android bất biến và không cấp quyền cho source examples độc lập.
- Official Android content worker thành công, đưa Grammar lên 174/174 stable ID; nhập 220 ví dụ gắn với 110 mẫu gốc. 140 ví dụ từ source riêng vẫn bị chặn. Hash của 64 mẫu cũ, 10 progress rows và 19 study events giữ nguyên. Sync chạy lại thành `no_changes`, không tạo duplicate. Không có migration mới.
- API phân trang trả 174 item, 174 stable IDs và 25 lessons chứa tổng cộng 174 mục. Chromium trên `/learning` hiển thị 25 thẻ Grammar với tổng đếm 174; detail bài 1 render pattern, nghĩa/cách dùng và ví dụ thật. Furigana không có trong 220 ví dụ nguồn và được giữ `null`.
- Chi tiết, source-rights basis và tests: `docs/grammar-original-110-recovery.md`. Một lần quét toàn manifest cũng đăng ký pack metadata `n2-kanji` không có item publishable; không có Vocabulary/Kanji item nào bị thêm hoặc thay bởi lần chạy này.

## V3.1 follow-up — đang triển khai, chưa hoàn tất

- Extension mở tra từ khi rê vào biểu tượng, không cần tab Web, không tự lưu; exact local lookup chỉ hoạt động khi operator tự cung cấp dictionary riêng (không phân phối trong repo công khai), backend lookup là fallback. Outbox offline retry qua alarm 15 phút và khi extension khởi động; giới hạn 100 item mới báo lỗi rõ ràng, không drop item cũ. Lint/typecheck/build và **23 extension tests** đạt. Chưa xác minh Chrome/Edge/Firefox thực tế; local dictionary không tương đương dịch tổng quát offline.
- Học tập có 4 accordion cùng cấp, mặc định đóng; Bài học tổng hợp có nút chạy mixed flashcard qua course session backend hiện có. Mặt sau hiển thị metadata theo Vocabulary/Kanji/Grammar khi nguồn có. Thêm tests accordion/mixed session; targeted tests đạt.
- Thêm tranh SVG tự tạo vào banner danh ngôn chỉ trong Sakura Zen và Indigo Washi, có overlay light/dark. Theme khác không đổi.
- Audit `N3.pdf`: 290 trang text-based, tất cả trang có text layer; TOC liệt kê 909 vocab, 195 Kanji, 156 grammar ở sáu nhóm hiện có; nhóm grammar 04 bị thiếu. Android source có 393 Kanji verified, cùng stable records/page provenance với 393 rows Web. Android/Web có 64 grammar rows có source declaration N3.pdf; PDF còn 92 grammar cards chưa được mapping sang item source approved. Trong 393 Kanji, 52 `kunReadings` là array rỗng (không phải thiếu field), 3 không có examples; 64 grammar rows không có examples vì source `n3-grammar-examples` chưa verified. Snapshot DB đọc-only: 5 packs, 880 vocab, 393 Kanji, 64 grammar. Audit đầy đủ nằm trong `docs/v3-1-n3-pdf-audit.md`.
- Không nhập 92 grammar cards chưa mapping và không công bố 140 grammar examples từ source chưa verified. Không tự tạo ví dụ/reading, không bypass rights gate. 64 approved grammar sources chỉ khai báo pattern/cấu trúc/nghĩa ngắn, không cấp provenance cho examples.
- Full i18n vi/en/ja chưa hoàn thành; hiện mới redesign language selector với Globe và compact options, nội dung nhiều trang còn hardcoded. Extension cross-browser live QA và toàn bộ regression suite chưa chạy lại sau follow-up. Android tiếp tục read-only.
- Trạng thái hiện tại: **in progress**. Không đánh dấu V3.1 hoàn thành.
- Verification sau follow-up: `./scripts/check.sh` đạt; backend **241 passed, 2 skipped**, frontend **56 passed** cùng ESLint/typecheck/production build, extension **15 passed** cùng typecheck/build Chrome/Firefox, Playwright **16 passed**. Hai skip backend là thiếu Tesseract `jpn` và OpenAI live opt-in không chạy. Không chạy Android build/test, không dùng OpenAI API.

## Web V3 — snapshot triển khai 2026-11-17

- Trước V3: Alembic `0011`; 4 content packs, 26 lessons, 457 items (393 Kanji, 64 grammar, 0 vocabulary), 1.271 examples. Backup PostgreSQL riêng trước các migration 0012–0014 nằm trong `backups/`; không reset. Sau import PDF chính thức: 5 packs, 38 source lessons, 1.337 items (880 vocabulary, 393 Kanji, 64 grammar), 1.271 examples. PDF không có examples nên không tự thêm. Các dữ liệu Web study cũ được giữ nguyên.
- PDF người dùng cung cấp có SHA-256 `a943ffaf90149f7d98bff5fb4d4296195adc942796600a2aefe9ce8243ac5728`, 1 trang text-based và STT 1–880 trong 19 nhóm cột. Parser đọc tọa độ text, validate 880 số liên tục; 41 ô reading trống giữ trống, không đoán. Nguồn PDF được khai báo quyền sử dụng cá nhân **riêng theo hash**, không duyệt hàng loạt Android JSON. Worker nhập 880 mục từ theo stable row ID, 12 bài nguồn, giữ nghĩa tiếng Việt và Unicode. Lần queue tiếp theo trả `no_changes`. Không khẳng định PDF chứa trọn bộ Mimikara N3 ngoài 880 hàng này.
- `/learning` có bài tổng hợp theo từng list gốc, giới hạn 30 từ/7 ngữ pháp/24 Kanji một bài; 30 bài, bài cuối 10 từ và không có grammar/Kanji. Các bài nguồn Android/PDF vẫn giữ riêng; item progress và practice/review event cũ được tái sử dụng. Đã bỏ UI tra cứu toàn bộ item không phân nhóm. Các mục Từ vựng/Kanji/Ngữ pháp, flashcard, ôn bài và bài luyện có dữ liệu tiếp tục hoạt động.
- `/learning/my-words` là kho từ do người dùng tạo, có CRUD/soft archive, nghĩa đa ngôn ngữ do người dùng nhập, flashcard, TTS browser và review event idempotent trong bảng riêng. Không tự chép toàn bộ 880 từ vào kho này. Extension có từ điển exact-match từ nguồn Web được phép nhập; từ không có nguồn xác thực báo không khả dụng, chưa có dịch JA↔EN↔VI tổng quát hay IPA/reading tự động cho mọi từ. Extension có chọn text theo site, popup, sửa nghĩa trước lưu, scope credential riêng, hàng chờ offline, Chrome/Edge và Firefox build. Chưa kiểm chứng tương tác browser live.
- Theme có 5 palette (Modern, Wabi, Sakura, Indigo, Tokyo) và light/dark/system, lưu trên browser; i18n vi/en/ja hiện áp dụng navigation, theme controls, một số tiêu đề/quote/analytics. **Chưa dịch toàn bộ form, error states và Help**, vì vậy full multilingual acceptance còn mở.
- Navigation chính V3: Tổng quan, Học tập, Kho đề, Phân tích JLPT; phụ: Cài đặt, Hướng dẫn. Tổng quan có danh ngôn Nhật tự biên soạn theo ngày, không còn ba hero CTA và không lặp analytics. Sổ lỗi sai ở tab Analytics; `/mistakes` redirect. Kho đề vẫn có draft, attempts và ChatGPT thủ công.
- QR Web protocol v1 thêm session 5 phút, claim, ready, human confirmation, reject/cancel/revoke, hashed-at-rest secrets, audit log. Migration `0014`; QR chỉ phát khi cấu hình `SYNC_PUBLIC_HTTPS_BASE_URL` là HTTPS hostname thật. Mock client tests đạt. Android hiện chưa quét QR; **Web QR pairing ready; Android implementation pending**. Xem `android-qr-sync-protocol.md` và `ANDROID_CODEX_QR_SYNC_PROMPT.md`. Android không upload local learning progress/exam history/saved words.
- PWA có manifest/icons và offline fallback chỉ cho trang fallback; không cache dữ liệu cá nhân. Live install/browser compatibility chưa kiểm thử.
- Migrations forward-only: `0012` rights hash cho PDF, `0013` My Words + extension credentials, `0014` QR session/audit. Dev DB ở head `0014`; không sửa migration cũ. Không gọi OpenAI API/ChatGPT credential, không commit/push.
- Kiểm thử gần nhất: backend **239 passed, 2 skipped**, frontend **54 passed** và production build đạt; extension **14 passed** và build Chrome/Firefox; Playwright **13 passed** sau cập nhật navigation V3. Skip là thiếu Tesseract `jpn` và OpenAI live opt-in (không gọi). Trình duyệt headless nối Web dev/API thật đã thấy 1.337 nội dung, 0/880 từ đã học và bài Vocabulary PDF trong bài tổng hợp; không chèn dữ liệu mock.
- Trong lúc làm việc Android HEAD **đổi từ** `07f0d0b` **sang** `e194a44` do hai commit ngày 2026-11-17 13:10 +07 (Kanji N2 và tài liệu Contrast Lab); Git worktree status giảm từ 49 xuống 6 entry. Phiên Web này không ghi/chạy Gradle/commit Android, song không thể khẳng định manifest Android trước/sau bằng nhau khi repository được thay đổi đồng thời bên ngoài. N3 CoursePlan vẫn giữ giới hạn 30/7/24; commit mới loại Kanji N2 khỏi course N3.
- Giới hạn V3: dịch đa ngôn ngữ toàn giao diện, dịch từ/cụm từ JA/EN/VI và IPA/reading chưa có nguồn tin cậy, browser live verification, HTTPS QR endpoint và Android QR client cần công việc tiếp. Không đánh dấu V3 hoàn thành toàn bộ.

## Web V2 — cập nhật 2026-11-17 (trạng thái hiện tại)

- Android chỉ được đọc tại HEAD `07f0d0bfd84086cc322d30b8bd4ce89b59222a92`. Audit chi tiết: `docs/android-web-v2-feature-audit.md`. Các mục cũ bên dưới là lịch sử theo từng PR, không phải snapshot hiện tại.
- PostgreSQL dev hiện ở Alembic `0011 (head)` sau backup `backups/v2_before_0010_20261117.dump` và `backups/v2_before_0011_20261117.dump`; trước/sau migration đều có 4 packs, 26 lessons, 457 items, 1.271 examples. Migration `0010` thêm quyền và Web study state; `0011` thêm grammar exercise answers append-only. Các bảng mới hiện rỗng. Worker V2 đã chạy startup check `no_changes`, sync_runs hiện 6; 2.335 record nguồn vẫn bị chặn.
- Web hiện có `/learning` (bài học, tìm kiếm/lọc, tiến độ và hoạt động), lesson detail, flashcard luyện bài, ôn SRS, bookmark `/learning/saved`, `/help`, Settings khai báo quyền `/settings/rights`. Bài luyện trắc nghiệm ngữ pháp từ Android assets đã có endpoint lưu kết quả và UI, nhưng hiện không có câu hợp lệ được nhập do illustration pack chưa được khai báo quyền. Kết quả luyện được lưu theo phiên; chỉ review mode cập nhật lịch SRS. UI dùng ruby từ markup furigana Android. Dashboard hợp nhất phân tích, menu gồm Tổng quan & Phân tích, Học tập, Kho đề & Thi thử, Sổ lỗi sai, Cài đặt; Knowledge/Reviews backend và deep link cũ vẫn còn.
- Nguồn Mimikara có **880 vocabulary items** + **870 source examples** nhưng hai source `mimikara-n3-sheet`, `mimikara-n3-vocab-examples` đều `licenseVerified=false`. Người dùng xác nhận sử dụng cá nhân nói chung, song chưa có khai báo rights holder/căn cứ quyền/phạm vi **theo từng source**; Web giữ nguyên gate. Dev DB hiện 0 vocabulary. Không tuyên bố V2 đầy đủ hoặc Vocabulary hoàn thành. Operator có thể khai báo riêng từng source ở `/settings/rights`; worker sẽ xử lý qua queue khi đã xác nhận căn cứ phù hợp.
- Tiến độ Web hiện tách hẳn Android Room; Android chưa upload progress/saved words/local exam attempts/mistakes. Android chỉ pull Web mirrors và push JLPT review events. Live device/HTTPS chưa được xác minh.
- `./scripts/check.sh` cuối: backend **229 passed, 2 skipped**; frontend **54 passed**, lint/typecheck/build; extension **11 passed** + build; Playwright **13 passed**. Browser headless trên dev DB mở `/learning` thấy 26 lesson links, tổng 457 item và chi tiết Kanji N3 bài 1 có 27 cards cùng ruby furigana thật. Không ghi tiến độ mẫu vào dev DB.
- Manifest SHA-256 Android trước/sau giống nhau: `5a7555d8f1f6dbee344e77c967dfa16886cee161e5ef4f584932c0652a22b88e`. Không chạy Android Gradle hoặc ghi Android. Không commit/push.

## Automatic Android learning content sync (PR9 worktree)

- Đã xác minh nguồn nội dung tĩnh Android là các content-pack JSON UTF-8 trong `app/src/main/assets/content/`, không phải API tải bài học. Web scanner chỉ đọc file Git-tracked trong checkout local đã cấu hình; không fetch/pull hoặc chạy script Android.
- Scanner thực tế ghi nhận Android commit `07f0d0bfd84086cc322d30b8bd4ce89b59222a92`; source manifest hash `745d4e3356e2f8c69f02f8a626c0802f9ecf501f8d024e33fec5b44cb460fab0`. Source có 64 grammar, 393 Kanji và 1.272 examples đủ license metadata; importer lưu 1.271 ví dụ được item tham chiếu, còn `n3k-x-10-002` không gắn với item nào. Chặn 2.335 record không đủ điều kiện quyền (Mimikara, illustrations và record chưa xác minh); N2 JSON chưa track.
- Nguyên nhân web trống: `0008` đã có và `ANDROID_LEARNING_SOURCE_DIR` trỏ đúng source, nhưng trước lần sửa các bảng mirror đều 0 hàng, `learning_content_sync_runs` cũng 0 hàng; worker định kỳ chưa chạy nên chưa có lần import đầu. Không có lỗi parser.
- Đã chạy import qua queue + `claim_and_process_one` (service worker chính thức): `succeeded`, 1 lần thử; 4 packs, 26 lessons, 457 items (393 Kanji + 64 grammar), 1.271 examples và 1.758 audit changes. Sau lần chạy thứ hai: `no_changes`, số hàng không đổi. Có 3 sync runs (1 `succeeded`, 1 manual `no_changes`, 1 startup `no_changes`).
- DB hiện có `learning_content_packs=4`, `lessons=26`, `items=457`, `examples=1271`, `item_examples=1271`, `changes=1758`, `sync_runs=4`; active counts: vocabulary 0, Kanji 393, grammar 64. API trả HTTP 200 với Kanji 393/grammar 64/vocabulary 0. Trình duyệt thật `/learning` hiển thị item Nhật, lesson, ví dụ và pagination `60/457`; grammar filter hiển thị `60/64`; vocabulary hiển thị empty state do license gate.
- Worker periodic 30 phút đã được khởi động trong môi trường hiện tại và startup scan trả `no_changes`. Đây là process đang chạy, chưa được cài dưới service supervisor bền vững; deployment cần quản lý worker bằng process manager để tự khởi động lại.
- PostgreSQL migration `0008` tạo mirror pack/lesson/item/example, audit changes, run history và queue lock; không sửa bảng tiến độ. DB hiện tại đã xác nhận ở revision `0008`.
- Import validate toàn snapshot trước khi ghi trong một transaction; upsert theo ID ổn định/hash, lưu commit/version, audit create/update/archive/restore và soft-archive nguồn bị gỡ. Nội dung Android tách namespace khỏi nội dung Web do người dùng tạo. Tiến độ Room cá nhân không được quét hoặc suy ra.
- Web có `/learning` và Settings hiển thị phiên bản, lần kiểm tra/lần sync thành công, counts, license-blocked và lỗi gần nhất. Token thủ công chỉ dùng để enqueue sync trên môi trường production.
- Kiểm tra code/test trong worktree: backend target learning-sync tests 11 passed; frontend lint/typecheck và Vitest 47 passed. Lần chạy đầu của full suite phát hiện race condition khi hai manual sync enqueue cùng lúc; queue mutex đã được gia cố để tự tạo lại singleton row nếu bị dọn và test concurrent/restart được thêm.
- Xác minh cuối `./scripts/check.sh`: backend **218 passed, 2 skipped**; frontend lint/typecheck, **47 passed** và production build; extension typecheck, **11 passed** và build; Playwright **13 passed**. Hai skip backend là thiếu Tesseract `jpn` và OpenAI live test opt-in không chạy. E2E đã migrate `0008` trên DB `_e2e` cô lập.
- `uv run alembic heads`: `0008`; `uv run alembic current`: `0006`. Dev database không được migrate. `git diff --check` đạt.
- Backend regression `tests/test_learning_content_sync.py`: **11 passed**; fixture test xác minh content hash/update/archive/idempotent no-change. `./scripts/check.sh` trước lượt import đạt backend 218 passed/2 skipped, frontend 47 passed + build, extension 11 passed + build, Playwright 13 passed.
- Không đồng bộ private Room/progress. Remote Git không được fetch tự động; worker nhận thay đổi khi source checkout local cập nhật.
- Android repo được giữ read-only; worktree người dùng hiện có thay đổi N2 Kanji. Không chạy Android build/test. Không dùng AI API/ChatGPT credential, không commit/push.

## Hai repository và dữ liệu

- FastAPI repo: branch `main`, HEAD `d83e3bc` trước thay đổi hiện tại.
- Android repo: branch `main`, HEAD `07f0d0b`, ahead `origin/main` 3 commit; worktree có thay đổi người dùng chưa commit (gồm Kanji N2). Không chỉnh sửa, build hay test Android.
- Không commit, push, reset hay xóa file dự án. Không chạy migration trên dev database; 0007 chỉ được chạy trên PostgreSQL test/migration database.
- Bảo toàn Room bằng migration cộng thêm `14 → 15`; các test trên emulator xác nhận `learning_progress` và `review_records` cũ vẫn nguyên giá trị. Không đụng các bảng này từ sync mapper.

## PR1–PR6 đã có trước PR6.1

| PR | Trạng thái và bằng chứng |
|---|---|
| PR1 — quản lý đề/bài làm | Đã có trong source/commit nền; backend, frontend và E2E được chạy trong `scripts/check.sh`. |
| PR2 — import/OCR | Đã triển khai; import/E2E pass. OCR Nhật bị skip khi máy thiếu Tesseract `jpn`. |
| PR3 — lời giải AI/manual | Đã triển khai; manual flow được test. Không gọi OpenAI trong phiên này; live test opt-in bị skip. |
| PR3.5 — ChatGPT Web Chat thủ công | Đã triển khai theo prompt/clipboard handoff; app không đọc token/cookie/session. E2E chỉ dùng mock. |
| PR4 — knowledge/analytics/reviews/SRS | Đã triển khai; backend, frontend, SRS và E2E regression được kiểm tra. |
| PR5 — Chrome Extension | Đã triển khai; extension tests/build pass. Live graded DOM chưa được xác minh. |
| PR6 — pairing/change feed/review push | Backend PR6 ở migration `0006`, sau đó PR6.1 backend snapshot feed ở `0007`; Android source hiện audit ở HEAD `07f0d0b`. |

## PR6.1 — trạng thái đã ghi nhận 2026-11-12

### Backend

- Migration mới `backend/alembic/versions/0007_sync_snapshot_feed.py` thêm `schema_version` và snapshot JSON payload, thay cursor IDENTITY bằng cấp phát commit-ordered qua singleton row lock.
- Trigger feed cho exam, passage, question, attempt, attempt answer, AI explanation, knowledge item, review item và Android review event. Link question/knowledge tạo snapshot knowledge mới; backfill dữ liệu hiện có.
- Câu hỏi đổi nội dung sẽ phát change cho lời giải liên quan; lời giải approved nhưng stale/rejected được gửi thành tombstone. Chỉ đáp án verified và lời giải approved/current mới được publish.
- Push event dùng insert-on-conflict idempotent, xử lý an toàn retry cùng `request_id`; thêm `POST /api/v1/sync/disconnect` để revoke credential phía server.

### Android

- Room schema 15 thêm bảng riêng `synced_exams`, `synced_passages`, `synced_questions`, `synced_explanations`, `synced_attempts`, `synced_attempt_answers`, `synced_knowledge`, `synced_review_items`, `synced_review_events`, `sync_checkpoints`.
- Android pull bootstrap/incremental theo page, kiểm tra schema/cursor/payload, áp dụng content+tombstone và checkpoint trong cùng Room transaction. Event outbox tồn tại cho tới acknowledgement; retry HTTP transient, duplicate feed, app restart và backend restart không ghi đè content/SRS legacy.
- Settings có pair, sync now, ngắt/revoke, lần sync thành công, số knowledge item, pending event, lỗi gần nhất; lỗi offline và credential revoked/expired có thông báo riêng.
- Có mục JLPT AI Review offline trong Settings: knowledge yếu kèm số câu sai liên quan; câu sai, lựa chọn, lựa chọn người học, đáp án verified, lời giải approved; ôn Again/Hard/Good/Easy.
- JLPT review dùng schedule riêng và append-only event outbox. Existing `learning_progress`/`review_records` và `WordsReciteRecord` không bị mapper chỉnh sửa.

## PR7 UI Restructuring baseline

PR7 was committed in `d83e3bc`. The navigation below is the PR7 baseline; the 2026-11-16 Android-Web follow-up adds Sổ lỗi sai and Phân tích JLPT, documented in the next section.

- Navigation web còn Tổng quan, Kho đề, Kho kiến thức; bỏ menu Nhập đề, Bài làm và Ôn tập. `/imports` chuyển tới `/exams?tab=drafts`, `/attempts` chuyển tới `/exams`, `/reviews` chuyển tới `/exams`; route kết quả `/attempts/{id}` được giữ.
- `/exams` có tab đề đã lưu và bản nháp nhập. Draft list nhận issues từ API list hiện tại; preview/editor/commit vẫn dùng endpoint PR2/PR5. Nút Thêm đề mở các importer đang dùng; Chrome Extension vẫn khởi chạy từ extension đã cài.
- Exam list API bổ sung đếm attempts, thời điểm/độ chính xác lần gần nhất, và số lời giải approved còn khớp nội dung hiện tại. Attempt list API bổ sung số lời giải approved/pending current cho các câu sai. Đây là field đọc thêm, không cần migration.
- Exam detail tải attempts bằng API pagination theo `exam_id`; từng attempt mở result và panel chữa PR3/PR3.5. Manual prompt nhận attempt ID để giữ đáp án người học, cho phép chọn câu sai/toàn đề và phân nhóm 20 câu. Knowledge vẫn chỉ lấy nguồn lời giải đã duyệt; giao diện không điều hướng người dùng sang SRS review.
- Không thay đổi Android, bảng SRS, scheduler, review APIs hay dữ liệu. Không gọi OpenAI API/ChatGPT credential trong PR7.

## Android ↔ Web JLPT features (worktree ngày 2026-11-16)

- Navigation Web gồm Tổng quan, Kho đề, Sổ lỗi sai, Phân tích JLPT và Kho kiến thức; không có menu Ôn tập.
- Thi thử dùng API đề/attempt hiện có: answer key ẩn trong lúc làm, chấm server-side theo verified answer snapshot, kết quả được lưu trong lịch sử đề. Web hiển thị cả accuracy đã chấm và correct/total; không suy ra điểm JLPT chính thức.
- Màn làm bài hiển thị từng câu, điều hướng trước/sau giữ lựa chọn trong bộ nhớ của phiên. Chưa có timer, lưu bản nháp attempt hoặc resume sau khi tải lại trang vì API/schema Web chưa hỗ trợ.
- Thêm API phân trang `GET /attempts/mistakes` để nhóm câu sai theo question từ attempt Web/import đã chấm; bỏ trống/chưa chấm không tính là sai. Thêm `GET /analytics/jlpt` để tổng hợp attempts Web.
- Không có migration mới. Alembic head `0007`; cấu hình DB hiện tại báo current `0006`. Không chạy migration hay ghi vào DB.
- Android source hiện nhận content/attempt/answer/explanation mirrors qua PR6.1 change feed và upload review events. Android local attempts, error_records và analytics không có upload; Web không nhận tự động dữ liệu thi Android. Xem `android-bidirectional-sync-audit.md` và `android-web-sync-gap.md`.
- Android exam schema có timer, section, text-answer, resume và listening mà Web chưa biểu diễn; timer không được đặt nếu thiếu duration source. Chưa chạy Android Gradle/test hay thiết bị live theo giới hạn read-only.
- Không sửa Android hoặc dùng OpenAI API/ChatGPT token.
- Kiểm tra lại `./scripts/check.sh` ngày 2026-11-16: backend **207 passed, 2 skipped**; frontend **45 passed** và production build; extension **11 passed** và build; Playwright **13 passed**. `git diff --check` đạt. Skip vẫn là OCR thiếu Tesseract `jpn` và OpenAI live opt-in không chạy.
- Alembic head vẫn `0007`; database cấu hình dev vẫn `0006`. Script E2E nâng revision trên database `_e2e` cô lập; không chạy migration trên database dev. Android Git status sau tác vụ vẫn giữ các thay đổi người dùng chưa commit, không có file Android nào được sửa bởi tác vụ.
- `./scripts/check.sh` cuối cùng đạt: backend **207 passed, 2 skipped**; frontend **45 passed** + production build; extension **11 passed** + build; Playwright **13 passed**. Hai skip backend là OCR thiếu Tesseract jpn và OpenAI live test opt-in không chạy. Test mới cover mistake aggregation/exclusions, JLPT buckets, navigation, score denominators và flow exam → mistakes → analytics.
- `./scripts/check.sh` chạy sau thay đổi cuối: backend **205 passed, 2 skipped**; frontend **44 passed** và production build; extension **11 passed** và build; Playwright **13 passed**.
- Skip: OCR thiếu Tesseract `jpn`, OpenAI live opt-in không chạy. PR7 không gọi OpenAI API/ChatGPT credential.
- Không tạo migration mới; không chạy migration trên database dev. Không có thay đổi Android.

## Kiểm thử lịch sử PR6.1 / PR7

- Kiểm tra PR7 trước follow-up: backend Ruff/format/mypy + **204 passed, 2 skipped**; frontend ESLint/TypeScript/Vitest **44 passed**, production build; extension TypeScript/build **11 passed**; Playwright **13 passed**. Kiểm tra mới nhất được ghi ở phần follow-up phía trên.
- Sync+migration backend tests: **13 passed**, gồm 0007 upgrade/downgrade/schema drift, cursor commit-order concurrency, approved→stale explanation tombstone, knowledge/review feed, disconnect/revoked credential và push idempotency.
- Android `testDebugUnitTest assembleDebug`: **476 unit tests passed**, build thành công. `compileDebugAndroidTestKotlin` thành công.
- Android emulator `Medium_Phone_API_36.1`: **372 instrumented tests, 369 passed, 2 skipped, 1 failed**. Room migration 14→15, legacy SRS preservation và fake-transport pagination/atomic rollback tests passed. Một test hiện fail ngoài sync scope: `HourPickerReachabilityTest.everyHourOfTheEndMenu_canBeReachedOnScreen` không tìm được nút `21:00` trong UI test. ML Kit device-dependent tests bị skip.
- Sau đó chạy riêng Room migration + sync integration tests trên `Pixel_8` emulator: **19 passed**, gồm test tombstone mới, pagination, atomic cursor rollback, fake-transport upload acknowledgement và bảo toàn SRS.
- Cảnh báo pytest không nhận cấu hình `approval_policy`/`sandbox_mode`; không ảnh hưởng kết quả tests.

## Giới hạn còn lại

- Chưa đồng bộ với FastAPI server thật từ app: emulator test dùng fake transport. Chưa kiểm tra pairing/upload/download qua HTTPS thực tế hoặc điện thoại vật lý.
- App chỉ nhận HTTPS và giữ platform certificate verification. Chưa có endpoint HTTPS/LAN development được cấu hình/trust trong phiên này; không dùng HTTP hay tắt TLS verification.
- Chưa chạy OpenAI API; không dùng ChatGPT credential/token.
- Chưa có test chạy end-to-end qua backend thật và app Android thật. Vì vậy không gọi live sync end-to-end verified.

## Tiếp theo

1. Chạy lại instrumented migration + `AndroidSyncClientIntegrationTest` trên emulator sau khi thêm tombstone case.
2. Điều tra riêng failure `HourPickerReachabilityTest` (có thể phụ thuộc UI state/timing; chưa sửa vì ngoài phạm vi PR6.1).
3. Cấu hình HTTPS development endpoint được thiết bị/emulator tin cậy, rồi xác minh pair → pull → offline review → push và revoke trên emulator/điện thoại.
4. Chỉ sau khi bước 3 đạt mới đánh dấu PR6.1 live end-to-end hoàn tất.

## Single-user sync hardening — 2026-11-16 worktree

- Audit source Android thực tế (read-only): URL bắt buộc HTTPS; dùng HttpURLConnection với platform
  certificate validation; token mã hóa AES-GCM bằng Android Keystore. Settings có pairing/sync/
  disconnect. Không tìm thấy custom trust manager, HTTP cleartext exception hay token logging.
- Android pull: exam, passage, question, approved/current explanation, Web attempt/answer mirrors,
  knowledge và review-item metadata. Android push: append-only review events qua request UUID. Room
  checkpoint và apply từng trang transactionally. Android không upload local exam attempts/answers,
  mistake records, saved words, full `learning_progress`/`WordsReciteRecord`, hoặc analytics.
- Web đã thay secret pairing lâu dài bằng one-time code 256-bit, TTL mặc định 10 phút/tối đa 15,
  hash-at-rest, single-use, thay code cũ, lockout sau 5 lần sai/15 phút. Device credential riêng
  từng máy vẫn hash-at-rest; revoke qua admin API. API admin yêu cầu `SYNC_ADMIN_KEY` tối thiểu 32
  ký tự khi truy cập ngoài loopback; UI chỉ giữ key trong memory.
- Normal Web data API bị giới hạn loopback; sync từ xa yêu cầu HTTPS; `/changes`, `/push`,
  `/disconnect` yêu cầu bearer device credential. Health metadata công khai. Extension/import và
  learning-content routes giữ token riêng đã có.
- Migration forward-only `0009_single_user_device_pairing.py`: thêm timestamps pull/push cho thiết bị,
  bảng pairing code và brute-force attempt. Không đổi exam, learning progress, reviews hay content.
  Đã áp dụng an toàn lên dev DB từ `0008` lên `0009`; trước/sau vẫn có exams=3, attempts=2,
  answers=5, content packs=4, lessons=26, items=457, examples=1,271. Pairing tables mới rỗng.
- Web có `/settings/sync`: cấp code, liệt kê thiết bị và last request/pull/push, revoke; copy nêu rõ
  pairing không đồng nghĩa sync hoàn tất. Thêm tests cho UI và backend pairing/access.
- Tài liệu mới: `single-user-sync-architecture.md`, `android-sync-capability-matrix.md`,
  `android-pairing-guide.md`, `sync-security-review.md`; README/API/offline/integration docs được
  cập nhật khỏi `SYNC_PAIRING_KEY` cũ.
- `./scripts/check.sh`: backend 226 passed, 2 skipped; frontend lint/typecheck + 49 Vitest + build;
  extension typecheck/build + 11 tests; Playwright 13 passed. Skip backend: Tesseract `jpn` thiếu
  và OpenAI live test opt-in (không được gọi). Ruff/mypy và `git diff --check` đạt.
- Backend sync/migration tests: 21 passed. Chưa có thiết bị/HTTPS endpoint phù hợp để xác minh live;
  trạng thái **Device verification pending**. Sync hỗ trợ thật vẫn giới hạn ở Android pull mirrors
  và Android push review events; exam history/progress/mistakes/analytics Android cần sửa Android.
- Android repository không được ghi; không chạy Gradle/build/test. Không commit/push. Worktree chứa
  thay đổi chưa commit trước đó của người dùng, được bảo toàn.
