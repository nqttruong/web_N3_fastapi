# Phân tích JLPT Web

Route /analytics/jlpt đọc trực tiếp Web exam_attempts và attempt_answers, không dùng
review SRS để thay cho dữ liệu thi. Endpoint GET /api/v1/analytics/jlpt trả:

- Số attempt và số câu đúng/sai/bỏ trống/chưa chấm.
- Accuracy trên câu đã chấm và correct/total để so sánh với Android.
- Phân loại outcomes theo vocabulary, kanji, grammar và reading.
- Trend theo ISO week, nhóm lỗi theo question type, đề làm lặp và duration suy ra từ
  completed_at - started_at khi timestamp tồn tại.
- Nguồn Web practice hoặc imported attempt.

Android dashboard phân loại thêm listening và OTHER theo section. Web hiện không lưu
section/listening, nên báo rõ giới hạn thay vì suy đoán. Android attempts chưa được gửi lên;
trang không hiển thị Android count = 0 như thể client đã kết nối. Analytics chỉ có Web
attempts đến khi Android bổ sung upload.

Accuracy không phải scaled JLPT score hoặc quyết định đỗ/trượt. API /analytics/weaknesses
vẫn là báo cáo knowledge/SRS khác, được giữ nguyên.
