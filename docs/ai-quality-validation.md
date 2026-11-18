# Kiểm định chất lượng lời giải

Mã: `backend/app/explanations/validation.py`. Áp dụng giống hệt cho lời giải từ API và JSON nhập từ
ChatGPT.

## Lớp 1 — xác định (lỗi ⇒ không lưu)

| Mã | Kiểm tra |
|---|---|
| `schema` | Đúng cấu trúc Pydantic (kiểu, trường bắt buộc, không trường lạ) |
| `schema_version` | = "1.0" |
| `question_id_mismatch` | Trùng câu được yêu cầu / được chọn |
| `answer_mismatch` | `correct_answer_index` = đáp án verified (AI không đổi đáp án) |
| `option_count`, `missing_option`, `unknown_option`, `duplicate_option_index` | Đủ và đúng từng phương án |
| `is_correct_mismatch` | Đúng một phương án `is_correct`, trùng đáp án |
| `option_text_modified` | Nội dung phương án giữ nguyên văn |
| `evidence_not_in_passage`, `evidence_without_passage` | Trích dẫn có thật trong đúng passage |

Với API: lỗi lớp 1 hoặc lỗi định dạng (`BadOutputError`: refusal, cắt cụt, không parse được) ⇒ thử lại
tối đa `AI_MAX_FORMAT_RETRIES` lần (mặc định 1) kèm danh sách lỗi; vẫn lỗi ⇒ `502 ai_output_invalid`,
không lưu gì. Với nhập thủ công: phần tử lỗi bị bỏ, phần tử hợp lệ vẫn lưu được.

## Lớp 2 — chất lượng nội dung (cảnh báo ⇒ `needs_review`)

| Mã | Dấu hiệu |
|---|---|
| `generic_reason`, `thin_reason`, `thin_correct_explanation` | Lý do chung chung ("không phù hợp ngữ cảnh") hoặc quá ngắn |
| `missing_meaning`, `missing_difference`, `missing_misconception` | Thiếu phân tích phương án sai |
| `missing_translation` | Thiếu dịch nghĩa |
| `contradiction` | Lời văn nhắc một số đáp án khác đáp án đã xác nhận |
| `missing_grammar_points` / `missing_vocabulary` / `missing_kanji` / `missing_evidence` | Thiếu mục kiến thức phù hợp loại câu |
| `reading_not_kana`, `example_not_japanese` | Cách đọc không phải kana; ví dụ không có tiếng Nhật |
| `model_reports_missing_context` | Model báo thiếu ngữ cảnh |
| `possible_wrong_key` | Model nghi ngờ đáp án nguồn → gắn cờ `flagged_answer_concern`, hiển thị cảnh báo, **không** đổi đáp án |
| `invented_learner_answer` | Nói về "bạn đã chọn" khi không có dữ liệu |
| `uncertainty` (info) | Ghi chú không chắc chắn của model |

## Trạng thái

| Trạng thái | Khi nào |
|---|---|
| `generated` | Qua cả 2 lớp, không cảnh báo — vẫn **chờ người dùng xác nhận** |
| `needs_review` | Có cảnh báo lớp 2, hoặc nhập thủ công từ ChatGPT |
| `approved` | Người dùng bấm "Xác nhận lời giải" (không bao giờ tự động; không duyệt được lời giải đã cũ) |
| `rejected` | Người dùng bấm "Đánh dấu chưa chính xác" (kèm ghi chú) — không còn là lời giải hiện hành |

`quality.*` do model tự báo **không** được dùng làm bằng chứng chính xác; nó chỉ có thể làm trạng thái
nghiêm ngặt hơn (thành `needs_review`).

## Giới hạn

Qua kiểm định ≠ đúng về ngôn ngữ. Validator không biết một lời giải ngữ pháp có đúng hay không; nó chỉ
bắt lỗi cấu trúc, mâu thuẫn và dấu hiệu sơ sài. Người dùng phải đọc và duyệt.
