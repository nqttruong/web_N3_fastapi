# Import learning data: N3 Sensei → JLPT AI Review

Pipeline chạy tự động bằng worker; không có thao tác export private Room. Nguồn là repository Android checkout cục bộ.

1. Cấu hình `ANDROID_LEARNING_SOURCE_DIR` trỏ tới Git root `N3 Sensei` (đường dẫn có dấu cách được hỗ trợ).
2. Chạy migration Web `alembic upgrade head`; PR này thêm forward-only revision `0008`.
3. Chạy một sync service: `cd backend && uv run python -m app.learning_content.worker`.
4. Mở Web → Cài đặt để xem commit/version, license-blocked counts, lỗi và lần sync gần nhất. Có thể bấm **Kiểm tra cập nhật bài học**; worker cần đang chạy.
5. Mở **Học tập** để lọc vocab/Kanji/grammar.

Scanner chỉ nhận JSON Git-tracked dưới `app/src/main/assets/content`, kiểm format/version/UTF-8/stable IDs/references rồi transaction upsert. Source `licenseVerified` false bị cách ly. Không chạy `tools/content/*.py`, không `git pull` trong Android repo. Một file mới phải được Git track để xuất hiện trong manifest; thay đổi tracked working file được phát hiện bằng content hash.

Nếu source lỗi, run log ở `learning_content_sync_runs` giữ exception và content DB trước đó không đổi. Sửa source qua Android maintainer rồi manual sync lại. Source removal được archive, không delete. Id người dùng Web, exams/attempts/verified answers, knowledge từ ChatGPT, reviews và SRS không bị merge hoặc ghi đè.

Tiến độ Android chỉ có thể đồng bộ khi có API/export cá nhân được app hỗ trợ và người dùng chủ động cung cấp. Hiện không đọc app sandbox/Room backup, không dùng Android credential, không chuyển learning progress.

## Kết quả import đã xác minh (2026-11-16)

Trước import: 0 packs, lessons, items, examples và sync runs. Sau import qua queue/worker chính thức: 4 packs, 26 lessons, 457 items (393 Kanji, 64 grammar), 1.271 examples được liên kết và 1.758 audit changes; lượt chạy thành công, không có lỗi. Ba lượt tiếp theo (manual, startup worker, và HTTP manual endpoint) trả `no_changes`, không sinh duplicate. API và trang `/learning` đã xác minh với dữ liệu thật.

Vocabulary vẫn bằng 0 vì toàn bộ 880 Mimikara vocabulary và 870 examples của pack đó bị license gate chặn; không bỏ qua kiểm soát quyền. Source có thêm 1.272 example Kanji đủ metadata nhưng 1 ví dụ không được item tham chiếu, nên chỉ 1.271 được upsert. Worker đã được khởi chạy ở interval 30 phút trong môi trường này; cần supervisor để duy trì sau restart máy.
