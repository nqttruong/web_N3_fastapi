# Hướng dẫn nhập đề (người dùng)

Trang **Nhập đề** (`/exams/new`) có 4 tab: *Dán văn bản*, *Dán HTML*, *Upload ảnh*, *Tạo thủ công*.
Ba tab đầu tạo **bản nháp**; chưa có gì được lưu vào kho đề cho tới khi bạn bấm *Lưu thành đề*.

## 1. Nhập đề từ Dethitiengnhat

Cách tốt nhất: **Dán HTML sau khi chấm điểm**.

1. Mở đề, ví dụ `https://dethitiengnhat.com/jlpt/N3/32/1`, làm bài và bấm **Tính Điểm**.
2. Nhấn **F12** → tab **Elements** → chuột phải thẻ `<html>` → **Copy → Copy outerHTML**.
3. Ở tab *Dán HTML*, dán vào ô *Mã HTML*, điền URL đề (nếu HTML có link canonical, hệ thống tự lấy) →
   *Phân tích & xem trước*.

| Lấy được tự động | Ghi chú |
|---|---|
| Nội dung câu, 4 lựa chọn, gạch chân | Kể cả đoạn đọc hiểu dùng chung |
| Đáp án của trang | Hiển thị là "Trang: đáp án", **chưa xác nhận** |
| Lựa chọn của bạn | Chỉ khi đã bấm Tính Điểm trước khi sao chép |
| Dạng câu, loại đề | Suy ra từ tiêu đề 問題 — kiểm tra lại |

| Chưa lấy được | Làm gì |
|---|---|
| Câu nghe | Không hỗ trợ (mặc định không lưu) |
| Lựa chọn của bạn khi dùng "Xem nguồn trang" | Dùng DevTools → Copy outerHTML sau khi chấm |
| Thời gian làm bài | Tự nhập ở mục *Bài làm từ dữ liệu nhập* |

Cách khác: *Dán văn bản* (Ctrl+A trong khung đề → Ctrl+C). Nhanh nhưng **mất gạch chân** và chỉ có
đáp án cho các câu bạn đã trả lời.

## 2. Kiểm tra & sửa lỗi parser

Trang xem trước hiển thị: tổng số câu, câu sẽ lưu, câu hợp lệ, thiếu đáp án, cần kiểm tra, đáp án đã
xác nhận; danh sách lỗi/cảnh báo; từng câu với ghi chú của parser.

- **Sửa** một câu: số câu, dạng câu, đoạn văn liên kết, nội dung, lựa chọn (thêm/xoá), đáp án chuẩn,
  lựa chọn của bạn.
- **Đã kiểm tra câu này**: bấm sau khi đối chiếu câu có ghi chú parser (bắt buộc trước khi lưu).
- **Lưu câu này**: bỏ chọn để loại câu rác, câu ví dụ.
- Mũi tên ↑↓ đổi thứ tự câu; khung *Đoạn văn* để sửa/thêm/xoá đoạn văn.
- Parser tách sai nhiều? Sửa trực tiếp ở khung *Văn bản gốc / HTML gốc* rồi bấm *Phân tích lại*
  (sẽ thay các chỉnh sửa câu hỏi hiện tại).
- Bấm **Lưu thay đổi** để lưu bản nháp (có thể đóng trình duyệt và quay lại ở *Bản nháp nhập*).

## 3. Xác nhận đáp án

- Đáp án lấy từ trang chỉ là gợi ý. Bấm **Xác nhận đáp án N** trên từng câu sau khi đã đối chiếu.
- Không có nút nào xác nhận tất cả một lúc; đổi đáp án sẽ tự bỏ xác nhận.
- Khi lưu: đã xác nhận → *Đã xác nhận* (dùng để chấm); chưa xác nhận → *Chưa xác nhận* (không chấm);
  không có → *Chưa có đáp án*. Có thể xác nhận sau ở trang chi tiết đề.

## 4. Tạo bài làm từ kết quả trên trang

Nếu dữ liệu có lựa chọn của bạn: bật *Tạo bài làm khi lưu*, nhập thời điểm bắt đầu và nộp bài. Bài
làm được chấm theo đáp án đã xác nhận, đánh dấu nguồn *import*.

## 5. Nhập lại một đề đã có

Hệ thống báo *Đã có đề với cùng URL nguồn* hoặc *Tất cả câu đã có trong đề …*. Khi bấm *Lưu thành
đề*, chọn **Dùng đề đã có**:
- câu giống hệt được dùng lại, câu mới được thêm;
- đáp án mới xác nhận bổ sung cho câu cũ chưa xác nhận; đáp án cũ đã xác nhận được giữ nguyên;
- bài làm mới được **thêm**, lịch sử cũ không đổi;
- nếu số câu bị trùng với câu khác nội dung → báo xung đột, không lưu gì; sửa số câu rồi thử lại.

## 6. Ảnh chụp & OCR

Cần Tesseract với dữ liệu tiếng Nhật trên máy chạy backend (xem README). Nếu chưa cài, tab *Upload
ảnh* báo "OCR chưa khả dụng" — dùng *Dán văn bản*.

- Chụp rõ, đủ sáng, chữ ≥ ~20 px; ảnh dài cả trang được hỗ trợ; sắp xếp ảnh theo thứ tự đọc.
- **OCR không chính xác tuyệt đối**: mọi câu từ ảnh đều bị gắn *Cần kiểm tra*. Mở ảnh gốc trong khung
  *Ảnh đã tải lên* để đối chiếu, sửa từng chữ sai, đặc biệt dấu ngoặc trống `（　　）`, gạch chân
  (OCR không đọc được gạch chân), dấu `゛゜`, trường âm `ー`.
- OCR đọc sai nhiều: đổi thứ tự ảnh / *Phân tích lại*, hoặc gõ lại bằng *Dán văn bản*.
