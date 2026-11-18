# Sổ lỗi sai Web

Route /mistakes là danh sách câu hỏi có ít nhất một answer đã chấm sai (is_correct=false).
Backend GET /attempts/mistakes lọc theo đề, skill hoặc từ khóa và phân trang; mỗi dòng
đại diện một câu hỏi với tổng số wrong occurrences, lần sai đầu/cuối, lựa chọn và attempt
nguồn gần nhất, cùng correct answer snapshot đã dùng khi chấm. Bỏ trống và chưa chấm không
được tính thành sai.

Trang có thể hiện lời giải ChatGPT chỉ khi API trả current + approved + non-stale; nội dung
pending/rejected/stale không được xem là kiến thức đã xác nhận. Link chữa bài mở panel từ
attempt nguồn, không cần OpenAI API key hoặc ChatGPT token.

error_records Android có trạng thái NEW/REVIEWING/MASTERED/ARCHIVED, notes, flags,
error cause và scheduler riêng. Những state này chưa có contract upload và không được giả
lập trên Web; Web hiển thị nhãn **Lỗi sai · tổng hợp**. Dòng tổng hợp lỗi khác với knowledge
weakness, Web SRS review item và Android error record.

API: GET /api/v1/attempts/mistakes?page=&page_size=&exam_id=&skill=&q=.
