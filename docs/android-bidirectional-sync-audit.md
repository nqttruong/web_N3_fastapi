# Android ↔ Web sync audit

Audit source được đối chiếu lại ngày 2026-11-16. Android repository được mở ở chế độ chỉ đọc. Không chạy Gradle,
Room migration hay test trên Android.

## Trạng thái repository

- Web: main, HEAD d83e3bc trước thay đổi hiện tại.
- Android: main, HEAD 07f0d0b, ahead origin/main 3 commit; worktree đã có thay đổi
  chưa commit của người dùng, gồm các thay đổi Kanji N2. Không sửa các thay đổi đó.
- Alembic head 0007; database được cấu hình trong môi trường này đang ở 0006.
  Không nâng revision hay thay đổi database.

## Kết quả theo dữ liệu

| Dữ liệu | Android entity / cơ chế | Web entity / cơ chế | Chiều hiện hỗ trợ | Trạng thái |
|---|---|---|---|---|
| Exam content | Room exam_sets, exam_sections, exam_passages, exam_questions; riêng synced_exams là mirror PR6.1 | exams, passages, questions; backend sync_changes | Web → Android qua GET /api/v1/sync/changes | Supported but untested (source path exists; Android tests/device not run in this task) |
| Exam attempts | exam_attempts, exam_attempt_items; ID local String; attempt có IN_PROGRESS/SUBMITTED/EXPIRED/ABANDONED | exam_attempts; UUID; Web POST tạo một lượt đã nộp, append-only theo API hiện tại | Web → Android có mirror synced_attempts; Android → Web không có upload | Android change required |
| Attempt answers | exam_answers (có thể đổi trước submit), exam_attempt_items snapshot kết quả; answer được ghi theo attempt/question | attempt_answers; UUID; lựa chọn và khóa đáp án snapshot khi submit | Web → Android có mirror synced_attempt_answers; Android → Web không có upload | Android change required |
| Sổ lỗi Android | error_records một hàng theo question ID; numeric autoincrement ID; error_count, first/last wrong, ACTIVE/MASTERED/ARCHIVED; review_items giữ lịch riêng | Không có bảng trạng thái notebook; API mới tổng hợp câu is_correct=false từ attempts Web | Web → Android chỉ gián tiếp qua answer feed; Android status/state không gửi lên Web | Backend-only derived notebook |
| JLPT analysis | ExamDashboardManager đọc getGradedHistory() và error notebook; ExamScoring tính đúng/sai/bỏ trống theo tổng câu, phân tích skill và thời lượng | API /analytics/jlpt tính từ Web attempts/answers | Không có entity analytics để sync; dữ liệu nguồn Android chưa upload | Backend-only, cần Android change để có nguồn Android |
| Android learning analytics | learning_progress, review_records; đây là thống kê học từ vựng, không phải lịch sử thi JLPT | Không map sang attempts JLPT | Không hỗ trợ trong contract JLPT; không ghi đè | Not supported for this feature |
| Approved explanation | Android synced_explanations, change handler chỉ nhận approved; query chỉ trả mirror còn available | ai_explanations, chỉ approved/current được phát trong feed | Web → Android | Supported but untested; no reverse explanation upload |
| Knowledge/review content | synced_knowledge, synced_review_items | knowledge_items, review_items | Web → Android; Android push review events | Supported but untested from source; no live device verification in this task |
| Review event | Room synced_review_events append-only outbox; request_id UUID | android_review_events, unique request ID + device provenance | Hai chiều với giới hạn: Android upload event; backend feed không thay đổi learning progress Android | Supported but untested in this task; not a proxy for exam upload |

## Sync contract hiện tại

AndroidSyncClient pair qua /sync/pair, pull /sync/changes theo cursor, áp dụng các
change page cùng checkpoint trong Room transaction, rồi upload hai luồng review event:
JLPT review outbox và legacy review_records. Payload chỉ hỗ trợ schema 1.0; unknown
entity type gây lỗi thay vì bị bỏ qua. Push dùng request_id để retry idempotent.

Feed hiện có exam, passage, question, ai_explanation, exam_attempt,
attempt_answer, knowledge_item, review_item, và review event. Android tạo mirror
riêng synced_*; ID server được namespaced với prefix jlpt: để tránh va chạm với ID
content local. Feed không đưa attempt Android local lên server.

### Mapping / conflict rules

- Android attempt ID đang là local string; chưa có mapping local ID ↔ server UUID hay
  source device + source entity cho exam attempts.
- Android thời gian thi là epoch milliseconds. Web API nhận datetime có timezone và lưu
  PostgreSQL timestamptz; convert cần dùng UTC và chia milliseconds đúng một lần.
- Android choice index là 0-based. Web selected_answer là 1-based; change feed đổi về
  selected_index 0-based cho Android. Không có Android upload để xác minh chiều ngược.
- Web attempt answers bất biến sau submit và giữ correct_answer_snapshot; Web answer
  verified chỉ được đổi qua workflow xác minh. Không cập nhật verified answer từ attempt.
- Mistake occurrence có thể tính từ attempt answers; notebook state Android không thể
  merge vì chưa có version/operation semantics hay identity mapping.
- JLPT analytics là dữ liệu dẫn xuất; không đồng bộ aggregate thay cho attempt/answer nguồn.

## Kết luận

**Backend ready — Android client change required.** Web có thể nhận và hiển thị bài thi Web
và bài nhập đã lưu ở Web. Để đưa attempt, attempt answers, error record state và nguồn
analytics từ Android lên Web cần Android client bổ sung outbox/upload, stable operation IDs,
device provenance, ID mapping và retry. Phạm vi này bị giới hạn read-only nên không thực hiện.
Không có endpoint nhận attempt giả danh; review event endpoint không nhận attempt payload.

Device pairing hoặc việc Android tải mirror attempt từ feed không chứng minh lịch sử thi
Android đã được upload. Chưa có xác minh sync live trong phiên audit này.
