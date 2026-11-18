# Đồng bộ content học Android → Web

## Kiến trúc

`Git-tracked Android assets → read-only scanner → SHA-256/manifest/version check → validation + license gate → stable-ID mapping → PostgreSQL transaction → /learning UI`.

Scanner đọc `app/src/main/assets/content/*.json` qua Git index và working tree của checkout được cấu hình. Nó chỉ chạy lệnh Git metadata (`rev-parse`, `ls-files`), không gọi remote, checkout, pull, build hay thực thi script Android. SHA-256 của từng file và manifest được dùng làm dấu phát hiện thay đổi; pack version và Android commit SHA được lưu kèm để audit. Thay đổi file được phát hiện kể cả khi pack version chưa bump.

Nguồn được parse toàn bộ trước khi bắt đầu transaction. Sai UTF-8/JSON/schema/ID/reference hoặc lỗi DB sẽ rollback toàn lượt; phiên bản đang hoạt động không đổi. Upsert dùng `(pack_id, item_type, source_ref)` và deterministic UUID. FKs cùng pack kiểm lesson/example mapping. Mục biến mất được chuyển `is_archived=true`, giữ bản ghi và audit; không hard-delete. Bảng nội dung này tách khỏi exams, attempts, knowledge do người dùng tạo, review items và SRS.

Mỗi item chỉ được publish khi source cụ thể đặt `licenseVerified: true`. Examples có gate riêng. Example chưa xác minh bị bỏ khỏi quan hệ và không được lưu public. Số record bị gate hiển thị trong Settings. Đây là metadata do source pack cung cấp, không thay thế rà soát pháp lý độc lập; quyền chưa rõ không được tự động xuất bản.

## Khởi động và chu kỳ

Migration `0008` tạo bảng mirror/audit, không sửa bảng hoặc tiến độ cũ. Sau khi môi trường đã chạy `alembic upgrade head`, cấu hình `.env`:

```dotenv
ANDROID_LEARNING_SOURCE_DIR=/media/truong/01DBB45ECE0C4E001/app/N3 Sensei
LEARNING_CONTENT_SYNC_INTERVAL_MINUTES=30
LEARNING_CONTENT_SYNC_MAX_RUN_SECONDS=300
```

Chạy đúng **một** sync worker như process/service riêng:

```bash
cd backend
uv run python -m app.learning_content.worker
```

Worker kiểm tra ngay khi khởi động, sau đó enqueue lần kiểm tra mỗi interval. PostgreSQL singleton advisory lock ngăn hai scheduler cùng chạy; queue row lock và advisory run lock chống đồng thời với manual request. Lỗi tối đa ba lần thử, lỗi cuối được lưu trong sync run. `statement_timeout` giới hạn transaction; Git metadata command có timeout riêng.

Khi worker dừng/restart, yêu cầu queued còn trong DB. Run đang dở được phục hồi sau timeout; lần khởi động worker mới sẽ enqueue một check. Không bật scheduler trong từng FastAPI worker. Không cần dịch vụ trả phí.

## Manual sync và Settings

Mở **Cài đặt → Kiểm tra cập nhật bài học**. Nút chỉ enqueue tác vụ, không chạy import nặng trong Next.js request. Settings hiển thị nguồn có truy cập được, chu kỳ, pack/version/commit, lần check/success, counts mới/đã đổi/archive, số item bị chặn do license và lỗi gần nhất. Cần worker hoạt động để xử lý queue.

Production cần `LEARNING_CONTENT_SYNC_TOKEN` là secret tối thiểu 32 ký tự; UI gửi qua `X-Learning-Sync-Token`, không lưu vào localStorage hoặc logs. Backend development mặc định bind localhost. Nếu dùng qua mạng, phải dùng HTTPS; không đưa token vào `NEXT_PUBLIC_*`.

## Dữ liệu Web

`/learning` có tab lọc Từ vựng, Kanji, Ngữ pháp, tìm kiếm, furigana/reading, meanings, lesson order và examples. IDs nguồn được giữ trong namespace pack riêng. Tiến độ Android không được suy ra hoặc đồng bộ từ việc nội dung xuất hiện.

## Kiểm tra log và phục hồi

- Backend logs dùng logger `learning_content_sync`, có run ID, commit SHA và aggregate counts; không log source payload.
- `learning_content_sync_runs` giữ status/trigger/attempt/counts/errors và commit/manifest SHA.
- `learning_content_changes` giữ từng create/update/archive/restore cùng hash cũ/mới và pack version.
- Settings đọc trạng thái từ API `GET /api/v1/learning-content/sync/status`; trigger manual qua `POST /api/v1/learning-content/sync`.
- Nếu source sai schema hoặc quyền, sửa nguồn trong workflow sở hữu Android repo. Sau đó chạy manual check hoặc restart worker. Bản Web đang hoạt động được giữ nguyên khi lần mới thất bại.
- Không chỉnh trực tiếp database mirror để sửa lỗi; sửa source pack rồi sync lại. Stable IDs giữ learning references nếu cùng ID được khôi phục.

## Lần đồng bộ đã xác minh

Ngày 2026-11-16 database tại revision `0008` ban đầu có 0 pack/lesson/item/example/run. Source path đã cấu hình đúng nhưng chưa có worker/import run. Manual run qua queue và worker service hoàn tất `succeeded`: 4 packs, 26 lessons, 457 items (393 Kanji, 64 grammar), 1.271 examples có liên kết và 1.758 audit changes. Lượt sync tiếp theo, startup run và manual request qua HTTP API đều trả `no_changes`; số row không đổi. Hiện có 4 run (1 thành công tạo dữ liệu, 3 lượt no-change).

API thật trả HTTP 200; `/learning` đã kiểm tra bằng trình duyệt với dữ liệu PostgreSQL (Kanji `意`, lesson `Kanji N3 · bài 1: 意–距`, ví dụ và grammar `〜ため（に）`). Vocabulary hiện 0 vì source Mimikara và examples đi kèm thiếu quyền phân phối được xác minh. Source có 1.272 examples đủ metadata license; ví dụ `n3k-x-10-002` không được item nào tham chiếu nên không được importer lưu.

Worker interval 30 phút đang chạy trong môi trường làm việc hiện tại, nhưng không được cài bằng process supervisor bền vững. Khi triển khai lâu dài, chạy `python -m app.learning_content.worker` dưới systemd/container supervisor; app worker không tự cập nhật/fetch Git remote.

## Giới hạn

- Scanner đọc checkout local. Nó không theo dõi remote Git tự động; upstream commit cần được cập nhật vào checkout qua quy trình riêng. Worker chỉ tự phát hiện khi file manifest/hash local đổi.
- Content pack do người dùng import vào Room mà không có trong Git sẽ không được thấy.
- Mimikara vocabulary và examples, illustration pack, phần unverified của grammar/Kanji, và N2 Kanji hiện không được xuất bản. Bản quyền cần xác minh riêng.
- Private Room database, user-created edits/words, learning_progress, `WordsReciteRecord`, reviews, exam attempts, mistakes, settings và SRS state không thuộc pipeline.
- Hiện source có data N3 và một file N2 untracked; project Web nav vẫn hiển thị nhãn JLPT tùy trang, không tự nhập N2 file chưa track.

## Web V2: khai báo quyền từng source và trạng thái học (2026-11-17)

Migration `0010` thêm `learning_source_rights` và các bảng `learning_study_*`, `learning_saved_items` độc lập với Android Room. Scanner chỉ bỏ chặn một source chưa `licenseVerified=true` khi có hàng `(pack_id, source_id)` được phê duyệt cho phạm vi `private`. UI `/settings/rights` yêu cầu chủ quyền/bên cấp phép, căn cứ quyền, phạm vi sử dụng và attribution; lưu khai báo sẽ xếp một sync run qua queue worker. Chỉ xác nhận nguồn mà người vận hành có căn cứ cụ thể. Gỡ phê duyệt rồi cho worker chạy sẽ soft-archive bản mirror; study events và progress không bị xóa.

Hiện `mimikara-n3-vocab.json` có 880 từ từ `mimikara-n3-sheet` và 870 ví dụ từ `mimikara-n3-vocab-examples`. Cả hai `licenseVerified=false`, nên dev DB giữ 0 vocabulary trước khi khai báo từng nguồn. Khai báo quyền dùng ứng dụng cá nhân không tạo quyền phát hành công khai. Mọi content scanner access đều read-only; worker không fetch Git, không thực thi script Android.

### Quản lý worker lâu dài

Chạy duy nhất một instance `cd backend && uv run python -m app.learning_content.worker` khi phát triển. Bản mẫu `deploy/learning-content-worker.service.example` ở **Web repo** dùng để cấu hình supervisor khi triển khai; thay đường dẫn/tài khoản rồi cài bằng quy trình vận hành của máy đích. Worker có PostgreSQL advisory singleton lock, job queue lock, retry giới hạn và timeout; hai process không quét/ghi đồng thời. Chỉ gắn Android checkout read-only với `ANDROID_LEARNING_SOURCE_DIR`; không cấp quyền ghi cho worker ở đó. Sau khi đổi quyền source, kiểm tra `learning_content_sync_runs` hoặc Settings để xác nhận job `succeeded`/`no_changes`; thất bại không thay snapshot trước đó.
