# PR7 — Kho đề và chữa bài bằng ChatGPT

## Navigation web

Menu chính gồm **Tổng quan**, **Kho đề** và **Kho kiến thức**. Nhập đề và bản nháp nằm trong Kho đề;
lịch sử bài làm nằm trong chi tiết đề. Web không có mục SRS Ôn tập. Route cũ `/imports`, `/attempts`
(index) và `/reviews` redirect về Kho đề để bookmark không dẫn tới trang lỗi. Kết quả
`/attempts/{attempt_id}` vẫn được giữ vì nó là trang xem một bài làm cụ thể.

## Thêm đề và bản nháp

Tại `/exams`, nút **Thêm đề** mở lựa chọn tạo thủ công, dán text, dán HTML và nhập ảnh. Các lựa chọn
dùng lại importer PR2. Muốn nhập bằng Chrome Extension, cài và mở extension trên tab đề đã chấm; extension
gửi capture tạo draft theo PR5.

Tab **Bản nháp nhập** hiển thị method/source, ngày nhập, số câu, status và lỗi validation gần nhất.
**Xem trước**/**Chỉnh sửa** mở `/imports/{draft_id}`; ở đó người dùng kiểm tra nội dung, xác nhận đáp án
rồi commit. Draft vẫn riêng biệt với đề đã lưu cho đến khi commit thành công.

## Lịch sử và chữa bài

Mở tab **Đề đã lưu** → chọn một đề → phần **Lịch sử bài làm**. Danh sách gọi endpoint phân trang
`GET /api/v1/attempts?exam_id=…`; mỗi dòng hiển thị thời gian, điểm, đúng/sai/bỏ trống, trạng thái lời
giải hiện hành và liên kết xem kết quả.

Trong kết quả attempt, panel **Chữa bài bằng ChatGPT hoặc AI** mặc định chọn câu sai đủ điều kiện chưa có
lời giải hiện hành. Người dùng có thể chọn **Câu sai** hoặc **Toàn bộ đề**, sau đó điều chỉnh từng checkbox.
Câu không có đáp án verified hoặc thiếu passage cần thiết sẽ bị loại khỏi prompt. Prompt tối đa 20 câu mỗi
lượt; đề dài được chia thành các nhóm 20 câu tiếp nối trong trang manual. Luồng ChatGPT thủ công:

1. Chọn **Xuất prompt cho ChatGPT**; prompt chứa question IDs, lựa chọn thật từ attempt, đáp án verified và passage.
2. Chọn **Chữa bài với ChatGPT** để sao chép prompt và mở `chatgpt.com` trong tab mới. Người dùng tự dán/gửi.
3. Dán JSON trả về ở `/explanations/manual`; backend kiểm tra IDs, schema, lựa chọn và key hiện hành.
4. Lưu lời giải hợp lệ ở trạng thái chờ duyệt. Người dùng mở lời giải, duyệt hoặc từ chối.
5. Từ attempt, mở **Trích xuất kiến thức** để lưu mục kiến thức. `/knowledge` chỉ hiển thị tri thức từ lời giải
   đã duyệt và hiện hành.

Ứng dụng không điều khiển UI ChatGPT, không đọc cookie/session, không cần OpenAI API key hay ChatGPT token.
Provider OpenAI API vẫn là cấu hình riêng phía backend và không được gọi bởi manual workflow.

## Dữ liệu và API

- Reuse: `GET /exams`, `GET/PATCH /imports`, `POST /imports/*`, `POST /imports/{id}/validate`,
  `POST /imports/{id}/commit`, `GET /attempts`, `GET /attempts/{id}`, explanation/manual-import và knowledge APIs.
- Exam list response có thêm attempt count, latest attempt summary, và số lời giải approved khớp hash câu hỏi
  hiện tại. Attempt list response có số lời giải approved/pending trên câu sai. Đây là field bổ sung trong response;
  không cần database migration.
- Review records, review items, scheduler, review APIs và Android sync tiếp tục tồn tại. PR7 chỉ bỏ màn điều
  hướng SRS khỏi web. Việc trích xuất knowledge tiếp tục tạo các backend review items theo hành vi hiện có,
  nhưng không tự chuyển người dùng vào review session.
- Không cập nhật đáp án verified từ JSON lời giải; thông tin thống kê không tính lời giải stale.
