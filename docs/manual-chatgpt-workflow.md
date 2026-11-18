# Chữa bài bằng ChatGPT thủ công (không cần API key)

1. Từ `/exams`, mở đề → chọn một dòng trong **Lịch sử bài làm** → mở kết quả của attempt.
2. **Chọn câu sai**
   - Khung *Chữa bài bằng ChatGPT hoặc AI* → tick các câu sai (mặc định chọn câu chưa có lời giải) →
     **Xuất prompt cho ChatGPT**; hoặc
   - Trang lời giải của một câu → **Xuất prompt**.
   Tối đa 20 câu mỗi lần. Câu chưa xác nhận đáp án hoặc câu đọc hiểu thiếu đoạn văn bị loại khỏi prompt
   (được liệt kê lý do).
3. Trên `/explanations/manual`, nhấn **Chữa bài với ChatGPT**. Ứng dụng sao chép chính xác prompt vào clipboard
   và mở `https://chatgpt.com/` trong tab mới. Nếu clipboard bị chặn, dùng **Sao chép prompt** hoặc sao chép
   trực tiếp từ ô prompt. Ứng dụng không đọc hay điều khiển tab ChatGPT.
4. Trong ChatGPT, người dùng tự dán prompt và gửi. Prompt gồm dữ liệu từng câu (có `question_id`, đáp án đã
   xác nhận, lựa chọn của người học, đoạn đọc liên quan) và JSON Schema cần trả về.
5. Sao chép câu trả lời JSON, quay lại JLPT AI Review và dán vào ô *JSON từ ChatGPT*. Chấp nhận `{"explanations": [...]}`, một mảng,
   hoặc một object; có thể còn khung ```` ```json ````. Trình duyệt báo lỗi cú pháp ngay.
6. **Kiểm tra & xem trước**: máy chủ kiểm định từng lời giải (cùng quy tắc với API):
   - `question_id` phải thuộc các câu đã xuất prompt — không thể chèn lời giải cho câu khác;
   - đáp án phải trùng đáp án đã xác nhận — JSON **không thể** đổi đáp án chuẩn;
   - đủ và đúng từng phương án, trích dẫn có trong đoạn văn…
   Lời giải hợp lệ hiển thị bản xem trước đầy đủ; lời giải lỗi hiển thị lý do và sẽ không được lưu.
7. **Xác nhận lưu**: chỉ lưu các lời giải hợp lệ, trạng thái **Cần kiểm tra** (nguồn: thủ công). Không
   bao giờ tự thành "đã xác nhận".
8. Mở từng câu → đọc kỹ → **Xác nhận lời giải** hoặc **Đánh dấu chưa chính xác**. Sau khi duyệt, dùng luồng PR4
   để trích xuất kiến thức. SRS/review records và Android sync vẫn tồn tại, nhưng web không mở review session từ luồng này.

Luồng này không yêu cầu API key, OAuth, access/refresh token hay quyền truy cập tài khoản ChatGPT. Mọi thao tác
trên chatgpt.com do người dùng thực hiện.

## Sửa JSON lỗi

Sửa trực tiếp trong ô JSON rồi bấm *Kiểm tra* lại. Hệ thống không tự sửa nội dung (ngoài việc bỏ khung
```` ```json ````). Nếu ChatGPT đổi đáp án hoặc thiếu phương án, hãy yêu cầu ChatGPT làm lại theo đúng
quy tắc thay vì sửa đáp án cho khớp.

## API

```
POST /api/v1/explanations/export-prompt  {"question_ids": [...]}
POST /api/v1/explanations/manual-import  {"question_ids": [...], "raw_json": "...", "save": false}
POST /api/v1/explanations/manual-import  {"question_ids": [...], "raw_json": "...", "save": true, "model_label": "ChatGPT"}
```
