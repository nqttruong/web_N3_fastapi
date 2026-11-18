# Schema lời giải (`schema_version: "1.0"`)

Định nghĩa: `backend/app/explanations/payload.py::ExplanationPayload`. Cùng một schema cho API
(Structured Outputs) và JSON dán từ ChatGPT. **Chỉ số 0-based** (tương thích Android); DB lưu đáp án
1-based.

```json
{
  "schema_version": "1.0",
  "question_id": "uuid",
  "correct_answer_index": 1,
  "translation_vi": "Vì trời đang mưa nên trận đấu bị huỷ.",
  "solution_summary_vi": "…",
  "correct_explanation": "…",
  "recognition_tips": "… | null",
  "options_analysis": [
    {
      "option_index": 0,
      "option_text": "のに",
      "meaning_vi": "vậy mà",
      "is_correct": false,
      "reason": "lý do cụ thể trong câu này",
      "when_it_would_be_correct": "… | null",
      "difference_from_correct": "… | null",
      "common_misconception": "… | null",
      "how_to_distinguish": "… | null",
      "example_ja": "… | null",
      "example_vi": "… | null"
    }
  ],
  "grammar_points": [{ "pattern": "〜ので", "meaning_vi": "…", "usage": "…", "contrast": "… | null", "example_ja": "… | null" }],
  "vocabulary": [{ "surface": "試合", "reading": "しあい", "meaning_vi": "…", "note": null }],
  "kanji": [{ "kanji": "試", "readings": "音: シ", "meaning_vi": "…", "note": null }],
  "sentence_structure": "… | null",
  "evidence": [{ "quote_ja": "trích nguyên văn passage", "explanation_vi": "…" }],
  "key_takeaway": "…",
  "review_topics": ["〜ので", "〜のに"],
  "quality": { "context_sufficient": true, "source_answer_concern": null, "uncertainty_notes": [] }
}
```

## Ràng buộc

Strict mode của OpenAI (đã kiểm tra tài liệu 2026-11-10): mọi trường bắt buộc, trường không áp dụng
dùng `null`/`[]`, `additionalProperties: false`, không dùng `minLength`… Vì vậy schema không chứa ràng
buộc; mọi quy tắc nằm trong validator (dùng chung cho cả hai chế độ):

- `question_id` = câu được yêu cầu; `correct_answer_index` = đáp án verified − 1.
- `options_analysis`: số mục = số lựa chọn; mỗi `option_index` 0…n−1 đúng một lần; đúng một
  `is_correct`, trùng đáp án; `option_text` khớp nguyên văn (bỏ qua khoảng trắng và thẻ `<u>/<ruby>`).
- `evidence[].quote_ja` phải nằm trong passage; câu không có passage thì không được có evidence.

## Phần riêng của người học (không lưu trong lời giải)

API trả thêm `learner_error_analysis` khi gọi kèm `attempt_answer_id` thật:

```json
{ "selected_answer_index": 0, "is_correct": false, "selected_option_text": "のに",
  "possible_misconception": "…", "how_to_distinguish": "…", "study_advice": "…" }
```

Suy ra từ `options_analysis[selected]` + `key_takeaway`/`review_topics`. Không có lựa chọn thật →
không có phần này.

## Bản ghi lưu trong DB

`ai_explanations`: `explanation_json` (payload trên) + `provider`, `model`, `origin` (api/manual),
`prompt_version`, `schema_version`, `content_hash`, `cache_key`, `verified_answer_snapshot`,
`validation_issues`, `flagged_answer_concern`, `usage`, `verification_status`, `reviewed_at`,
`review_note`. Xem `database-schema.md`.

## Nâng phiên bản schema

Thay đổi không tương thích → `SCHEMA_VERSION = "2.0"`, model mới; lời giải 1.0 vẫn đọc được (hoặc
hiển thị "định dạng cũ"). `schema_version` nằm trong `cache_key`.
