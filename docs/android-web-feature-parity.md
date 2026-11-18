# Android / Web JLPT feature parity

Audit source được đối chiếu lại ngày 2026-11-16 và API Web hiện tại. Android chỉ được đọc;
không chạy build/test Android nên parity runtime trên thiết bị chưa được xác minh.

| Tính năng | N3 Sensei Android | JLPT AI Review Web | Parity |
|---|---|---|---|
| Thi thử | Full/section/generated sets; sections; timer và timeout; resume; choice/text answers; submitted/expired/abandoned | Kho đề → Làm bài; lưu attempt server-side; câu hỏi theo thứ tự; chọn đáp án; nộp và xem kết quả | Luồng mock/submit tương đương ở mức choice; Web hiện không lưu duration/time limit, section order, text answer, resume hoặc attempt timeout |
| Chấm điểm | Một điểm cho mỗi câu đúng; kết quả có đúng/sai/bỏ trống; độ chính xác correct / total; không tuyên bố điểm JLPT scaled | Verified answer snapshot; đúng/sai/bỏ trống/chưa chấm; API accuracy correct / (correct + incorrect) | Cùng phân biệt outcome; hai tỷ lệ có mẫu số khác nhau. Web hiện hiển thị cả hai để không gây hiểu nhầm |
| Kỹ năng | vocabulary, kanji, grammar, reading, listening; OTHER lấy skill từ section | 4 category: vocabulary, kanji, grammar, reading; không có listening hoặc section per question | Partial; listening và section data cần schema/import Web mở rộng |
| Sổ lỗi | Một record/question, occurrence count, first/last wrong, cause, mastery/review state, important flag, snapshots; answer trống cũng tạo UNANSWERED record | Một dòng/question tổng hợp từ answer có is_correct=false; lọc đề/skill/search; chọn sai gần nhất, snapshot answer key, attempt nguồn, approved explanation hiện hành | Wrong occurrences tương thích; Web cố ý không gọi blank là sai. Trạng thái mastery/archive và notes Android không được đồng bộ |
| Phân tích | Từ graded attempt history; skill/weekly/type trends, durations, error notebook, weak knowledge; riêng với học từ vựng | Aggregate Web attempts: tổng outcomes, 4 skills, trend tuần, duration, repeated exams, type errors | Chỉ tính Web source; không trộn Android data. Một số Android breakdowns cần fields chưa có trong Web |
| Lời giải | Nhận approved/current explanations trong synced Room mirror | ChatGPT manual workflow, validate/import/approve, xem lời giải và trích xuất knowledge | Web → Android supported qua feed; không dùng OpenAI API/token để chạy manual workflow |

Android scoring source: domain/exam/ExamResults.kt (ExamScoring.score), skill map
domain/exam/ExamModels.kt (ExamSkill.of), timer domain/exam/ExamTimer.kt, submit/history
data/repository/OfflineExamRepository.kt. Web grading source:
backend/app/attempts/service.py.

Web exam record không có duration limit; không có timer giả định. Web API answer API đang là
1-based, còn Android choice index là 0-based. No official scaled JLPT score is calculated
in either parity report.
