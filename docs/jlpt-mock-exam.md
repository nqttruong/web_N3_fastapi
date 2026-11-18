# Thi thử JLPT trên Web

## Luồng

Vào **Kho đề**, chọn đề đã lưu rồi bấm **Làm bài**. Web tải câu hỏi với answer key bị ẩn
và hiển thị từng câu một. Có thể chuyển câu trước/sau; lựa chọn vẫn nằm trong phiên làm bài
khi di chuyển. Ở câu cuối, nộp bài để server chấm và lưu attempt. Chi tiết bài làm mở từ lịch
sử của đề, giữ answer key snapshot tại thời điểm submit và có panel chữa bằng ChatGPT thủ công.

API dùng lại GET /exams, GET /exams/{id}/questions?include_answers=false,
GET /exams/{id}/passages, POST /attempts, GET /attempts/{id} và paginated
GET /attempts?exam_id=.... Grading chỉ dùng đáp án verified. Không có khóa verified thì
câu đã chọn là ungraded; câu bỏ trống là unanswered.

## Quy tắc điểm

- Đúng/sai được chấm theo verified key và snapshot khi nộp.
- Tỷ lệ chính xác Web là correct / (correct + incorrect).
- Tỷ lệ đúng trên tổng câu là correct / total_questions, tương đương mẫu số accuracy trong
  ExamScoring Android.
- Không tính điểm scaled hoặc pass/fail JLPT chính thức.

## Giới hạn tương thích hiện tại

Android hỗ trợ duration/timer, section, resume, expired attempt, câu trả lời text và kỹ năng
listening. Web exam schema hiện không có duration/section/text answer/timeout persistence;
Web không tự đặt thời gian thi. Câu trả lời chỉ nằm trong bộ nhớ phiên trình duyệt cho đến lúc
nộp; chưa có API lưu bản nháp đang thi hoặc resume sau khi đóng trang. Nguồn Web cũng hiện
không có category listening. Các trường này cần mở rộng Web schema/API và nhập nguồn tương ứng
trước khi tuyên bố parity hoàn toàn. Lịch sử thi Android chưa được upload bởi client hiện tại.
