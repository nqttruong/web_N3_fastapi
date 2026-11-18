# JLPT AI Review V3.1 — Final Acceptance Report

**Ngày:** 2026-11-18
**Trạng thái cuối:** **PARTIAL**
**Phạm vi xác minh:** Web repository và database phát triển; Android chỉ đọc. Báo cáo không tuyên bố Android device verification.

## 1. Kết quả theo task A–H

| Task | Trạng thái | Bằng chứng nghiệm thu | Việc còn lại |
|---|---|---|---|
| A — Grammar PDF mapping | **VERIFIED** | Đối chiếu 156 thẻ PDF; 64 mục được xác minh khớp ID/pattern Web và Android. 92 mục được phân loại thành 57 candidate, 24 biến thể, 11 thẻ so sánh. PDF không có Grammar 04 trong TOC/text layer; không tạo mục giả. | Không nhập 81 candidate/variant từ nguồn có `licenseVerified=false`. Bản tóm tắt công khai: `docs/v3-1-grammar-gap-review-summary.md`; chi tiết nguồn giữ ngoài repo công khai. |
| B — Grammar examples | **BLOCKED** | 140 ví dụ được giữ trong review queue riêng, có stable IDs, text nguồn, cách đọc/dịch và lý do chờ duyệt. Không ví dụ nào bị công bố thành nội dung approved. | Nguồn ví dụ chưa có xác nhận quyền sử dụng và kiểm chứng ngôn ngữ; cần review có thẩm quyền trước khi publish. |
| C — i18n toàn ứng dụng | **IN_PROGRESS** | Ba locale hiện có catalog chung. `/learning`, My Words/Flashcards/Review, `/exams`, attempts, imports, explanations, Analytics và Mistakes có các test locale theo tracker; 107 frontend tests đạt. | Chưa có bằng chứng bao phủ toàn bộ route/component và mọi UI string trong vi/en/ja. Không đánh dấu hoàn tất toàn ứng dụng. |
| D — Browser Extension độc lập | **IN_PROGRESS** | Extension typecheck, 23 tests và Chrome/Firefox builds đạt. Tests bao gồm hover/no-click, popup state, explicit save, cache/outbox/retry và regression capture. | Không xác minh được extension chạy trong browser thật ở môi trường headless. Provider hiện chỉ có lookup chính xác Nhật→Việt; chưa có nguồn đã xác minh cho EN/JA gloss và IPA. |
| E — Learning UI và composite flashcards | **VERIFIED** | Bốn accordion ngang cấp mặc định thu gọn. Course grouping từ dữ liệu thật tạo 30 bài, giới hạn 30 Vocabulary/7 Grammar/24 Kanji; bài cuối 10/0/0. Session/resume, practice event và Review dùng cơ chế hiện tại; tests xác nhận persistence và không sửa SRS khi practice. | Grammar approved examples hiện bằng 0; đây là gap nội dung ở B, không được bù bằng ví dụ dựng. |
| F — Kanji provenance/readings | **VERIFIED** | 393/393 stable IDs và character khớp Android. Hán Việt/On/Kun field parity 393/393, trong đó 52 Kun rỗng đúng như nguồn. 1.272 examples approved; 7 source examples chưa được phép nên vẫn bị loại. | Không tự suy diễn 52 Kun còn thiếu và không nhập 7 ví dụ chưa xác minh. |
| G — Theme/navigation | **VERIFIED** | Sakura Zen và Indigo Washi dùng SVG phong cảnh local; chỉ đặt ở banner/quote, có light/dark overlay. Navigation, redirect Mistakes, quote và không có Knowledge shortcut được xác nhận trong code/tests. Tracker lưu bằng chứng kiểm tra responsive 390×844, 768×1024, 1440×900 và theme variants; E2E cũng kiểm tra mobile navigation. | Không có blocker Web đã biết. |
| H — Integration/regression | **VERIFIED** | Full Web regression đạt. Mock QR pairing/revoke, My Words, import, exam/attempt, ChatGPT review được kiểm thử. Database ứng dụng được so sánh read-only trước/sau: revision 0014 và mọi số hàng ở 47 bảng không đổi. | Real Android sync/QR không thể xác minh vì client Android hiện tại chưa có QR flow; xem I-android. |

### QR protocol follow-up

| Phần | Trạng thái | Bằng chứng / giới hạn |
|---|---|---|
| I-web — QR pairing protocol | **VERIFIED** | Backend tests dùng mock Android client cho claim → confirmation → authenticated sync → revoke, expiry, replay, rate limit và authorization. Protocol dùng pairing hiện có, không cấp long-lived token trong QR. Tài liệu: `docs/android-qr-sync-protocol.md` và `docs/ANDROID_CODEX_QR_SYNC_PROMPT.md`. Chưa kiểm tra endpoint HTTPS đã deploy trên thiết bị. |
| I-android — QR client | **TODO / PENDING** | Android chưa có QR scanner/claim flow. Không chỉnh sửa hoặc build Android. Trạng thái chính xác: **Web QR pairing ready; Android implementation pending.** |

## 2. Regression results

Các bộ kiểm thử được chạy trên database test và E2E riêng, không dùng database ứng dụng cho thao tác ghi.

| Bộ kiểm thử | Kết quả cuối |
|---|---|
| Backend: Ruff lint | Passed |
| Backend: Ruff format check | Passed — 168 files |
| Backend: mypy | Passed — 116 source files |
| Backend: pytest | **253 passed, 2 skipped** |
| Frontend: ESLint | Passed |
| Frontend: TypeScript | Passed |
| Frontend: Vitest | **23 files, 107 tests passed** |
| Frontend: Next production build | Passed; route generation completed |
| Extension: TypeScript/typecheck | Passed |
| Extension: Vitest | **3 files, 23 tests passed** |
| Extension: Chrome build | Passed |
| Extension: Firefox build | Passed |
| Playwright E2E | **16 passed** (desktop and mobile project coverage) |

Backend skips: OCR test cần Tesseract Japanese data không có trong môi trường; live OpenAI test là opt-in và không được gọi. Pytest cũng cảnh báo hai config option `approval_policy` và `sandbox_mode` không được pytest nhận diện; không ảnh hưởng kết quả tests.

Trong quá trình nghiệm thu, E2E ban đầu gặp selector cũ do nhãn UI đã đổi. Đã chuyển statistic test IDs sang ID ổn định và cập nhật selectors theo UI đang chạy. Kết quả full Playwright cuối cùng là 16/16 pass.

## 3. Database và bảo toàn dữ liệu

Database cấu hình được mở bằng transaction `READ ONLY` để đối chiếu snapshot trước/sau:

- Alembic revision: `0014` trước và sau.
- Số bảng trong snapshot: 47 trước và sau.
- Số bảng có thay đổi row count: 0.
- Nội dung học: 5 packs, 38 lessons, 1.337 items, 1.272 examples trước/sau.
- Tiến độ học/session: 20 progress rows và 7 sessions trước/sau.
- Bài thi: 3 attempts, 6 attempt answers trước/sau.

Không chạy migration trên database ứng dụng, không reset/truncate/xóa dữ liệu. Các E2E và backend fixtures dùng database riêng có hậu tố `_e2e`/`_test`.

## 4. Android read-only verification

- Không chạy Gradle, build, tests hay Room migration.
- Không ghi file hoặc sửa source Android.
- Git index Android vẫn rỗng; hash `git diff --binary` cuối trùng hash baseline trong checkpoint (`9ab47ade…`), không có staged diff.
- Android worktree đã có các sửa đổi/untracked thuộc Contrast Lab từ trước; chúng được giữ nguyên.
- Vì Android chỉ được khảo sát read-only, không có kiểm thử client thật hoặc xác minh QR trên điện thoại.

## 5. Chức năng chưa kiểm chứng thực tế và blocker

1. **Grammar**: 140 ví dụ ngoài nguồn approved chưa đủ xác nhận quyền/correctness; Grammar 04 không tồn tại trong PDF đã kiểm tra. Không tạo nội dung thay thế.
2. **i18n**: các route được nêu trong tracker có locale tests, nhưng chưa có automated audit chứng minh toàn bộ UI của ứng dụng không còn hardcoded strings ở cả ba locale.
3. **Extension live browser**: Chrome/Firefox packages build được, nhưng chưa chạy được extension trong browser thật tại môi trường hiện có. Lookup đa ngôn ngữ và IPA bị giới hạn bởi nguồn provider chưa cấu hình; không giả lập kết quả dịch.
4. **Android sync/QR**: mock protocol đạt nhưng Android client chưa hỗ trợ QR; chưa có device verification.
5. **OCR/OpenAI live**: tương ứng 2 backend tests skipped vì môi trường/opt-in; không ảnh hưởng offline/manual workflow.

## 6. Kết luận

Regression Web cuối cùng đạt, dữ liệu ứng dụng không thay đổi, và các task A, E, F, G, H cùng I-web có bằng chứng nghiệm thu. Tuy nhiên B còn bị chặn bởi quyền/xác minh Grammar examples; C và D chưa đáp ứng toàn bộ acceptance criteria; Android QR vẫn pending. Do đó trạng thái tổng thể là **PARTIAL**, không phải COMPLETE.
