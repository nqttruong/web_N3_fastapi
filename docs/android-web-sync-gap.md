# Android–Web sync gaps

## Đang hoạt động trong contract PR6/6.1

- Android pairing với device credential qua HTTPS.
- Android pulls Web exam, passage, question, approved/current explanation, attempt,
  attempt answer, knowledge và review item qua commit-ordered incremental change feed.
- Room mirror dùng namespace jlpt:; apply change page và checkpoint cùng transaction.
- Android gửi review events có stable request_id; server dedupe idempotently và giữ
  device provenance.

Các điểm trên được xác nhận bằng source code trong audit; không chạy Android build/test hoặc
device live verification vì repository Android được giữ read-only. Device live sync chưa
được kiểm chứng ở tác vụ này.

## Chưa hỗ trợ

- exam_attempts và exam_answers Android local không có outbox / upload call.
- error_records và notebook state không có upload contract, stable server mapping hay
  conflict/version rules.
- Analytics là derived data; không có Android aggregate upload. Cần upload source attempts
  trước, rồi server tính toán lại.
- Web duration/section/listening schema chưa đủ để tái tạo đầy đủ Android mock test.

**Backend ready — Android client change required.** Tạo upload path an toàn cần Android
client thay đổi để tạo stable operation ID, gửi local ID + device + entity type, normalize
timestamp và answer index, và retry append-only. Trong phạm vi này không sửa Android; không
tạo receiver chưa được client dùng, không nhận nhầm review event thành attempt, không mở
endpoint không xác thực. Web existing /attempts tạo bài làm của Web user, không phải
receiver Android.

### Future receiver contract (design only; endpoint chưa được bật)

Khi Android có outbox cho attempt đã nộp, dùng endpoint riêng
`POST /api/v1/sync/attempts:batch`, xác thực bằng paired-device credential PR6; không dùng
extension token. Mỗi item cần `operation_id` UUID ổn định, `source_attempt_id` local string,
`source_exam_id`, timestamps ISO-8601 UTC, trạng thái `SUBMITTED` hoặc `EXPIRED`, cùng danh
sách `source_question_id`, `selected_index` (0-based) hoặc `text_answer`, và snapshot câu hỏi
để audit. Device ID lấy từ credential, không tin device ID do body gửi lên.

Receiver tương lai phải dedupe trên `(device_id, operation_id)` và giữ mapping
`(device_id, entity_type, source_id) → Web UUID`; không match theo tên. Chỉ nhận attempt khi
exam/question mapping đã tồn tại hoặc được đăng ký qua contract import có xác thực. Trong một
transaction, tạo attempt, answer snapshot, source provenance và dedupe receipt; retry trả lại
cùng Web attempt ID. Answer nộp là immutable. Web tự chấm bằng verified answer hiện hành tại
thời điểm nhận và lưu snapshot đó; không tin `is_correct` hoặc answer key do Android client
gửi, không thay đổi verified answer. Invalid mapping/payload từ chối toàn bộ item, không advance
cursor. Analytics và mistake occurrences được tính lại từ attempt/answer đã nhận; notebook
state Android không merge cho tới khi có versioned state operations.

Đây mới là contract thiết kế, chưa phải endpoint triển khai hoặc kiểm thử tích hợp. Android
hiện không tạo outbox/call cho attempts nên không có request tương thích để xác minh.

Khi Android hỗ trợ upload, cần transaction idempotency theo (device_id, source_entity_type,
source_entity_id) hoặc operation ID, validate attempt/question membership và timestamp,
giữ immutable answers sau submit, và chỉ rebuild mistake/analytics từ accepted attempts.
Conflict với verified answers không được phép: attempt phải giữ key snapshot, answer key
hiện tại chỉ đổi qua verification workflow.
