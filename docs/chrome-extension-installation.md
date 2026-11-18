# Cài Chrome Extension

## Yêu cầu

- Chrome hỗ trợ Manifest V3.
- JLPT AI Review backend tại `http://127.0.0.1:8000` và frontend tại `http://127.0.0.1:3000` (có thể đổi trong Options).
- Backend cấu hình `EXTENSION_IMPORT_TOKEN` bằng một secret ngẫu nhiên dài ít nhất 32 ký tự. Ví dụ: `openssl rand -hex 32`. Không đưa secret này vào Git hoặc gửi cho người khác.

Khởi động dịch vụ như hướng dẫn trong README, sau đó tạo bản extension:

```bash
cd extension
npm run build
```

Trong Chrome:

1. Mở `chrome://extensions`.
2. Bật **Developer mode**.
3. Chọn **Load unpacked** và chọn thư mục `extension/dist-v3-1/chrome`.
4. Mở **Details → Extension options**. Điền URL backend `/api/v1`, URL frontend và cùng secret đã cấu hình ở backend; lưu lại.
5. Mở một trang đề N3 được hỗ trợ, làm bài và tự bấm chức năng chấm trên website nếu muốn lấy kết quả.
6. Bấm biểu tượng extension → **Đọc đề ở tab này**. Kiểm tra số câu, đáp án và cảnh báo; mở **Xem dữ liệu** khi cần.
7. Bấm **Chuyển sang JLPT AI Review**. Extension gửi capture tới backend local rồi mở `/imports/{id}`.
8. Trong preview, rà lại câu hỏi, passage, phương án, lựa chọn và đáp án nguồn. Tự đánh dấu các đáp án đã xác minh rồi mới chọn thao tác lưu đề / bài làm.

Extension không tự bấm chấm bài trên trang nguồn. Trang chưa chấm vẫn có thể được gửi dưới dạng draft, với đáp án nguồn và lựa chọn không tìm thấy để trống.

## Tra từ trên website

Trong popup extension, chọn **Bật tra từ** trên từng website và cấp optional permission. Từ đó, bôi đen tối đa 200 ký tự rồi di chuột hoặc đưa keyboard focus vào biểu tượng `訳`; popup tra cứu mở ngay tại trang hiện tại, không cần tab Web. Chỉ đoạn đã chọn được tra. Muốn lưu, tạo credential riêng **My Words** tại `/settings/sync` một lần rồi lưu credential đó trong Options của extension; credential capture không được dùng cho việc này. Bấm **Lưu từ** mới gửi nội dung. Nếu backend offline, extension giữ pending local và báo rõ rằng dữ liệu chưa được đồng bộ.

Nguồn hiện có cung cấp các mục tiếng Nhật khớp chính xác, cách đọc và nghĩa tiếng Việt. Nghĩa tiếng Anh/tiếng Nhật bổ sung và IPA chỉ hiện khi provider có dữ liệu; trường trống không phải bản dịch. TTS tùy thuộc voice có sẵn trong hệ điều hành/trình duyệt.

Để cập nhật code: chạy lại `npm run build`, quay về `chrome://extensions` và bấm nút Reload trên extension đã load. Gói Firefox thử nghiệm nằm ở `extension/dist-v3-1/firefox`.
