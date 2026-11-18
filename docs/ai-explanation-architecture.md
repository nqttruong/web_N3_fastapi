# Kiến trúc chữa bài bằng AI (PR3)

```
                       ┌──────────────── app/explanations ────────────────┐
 POST /generate ──────▶│ service.generate_for_question                     │
 (1 câu, đồng bộ)       │   context.build_context ── chỉ dữ liệu có trong DB │
                       │   ├─ chưa verified / thiếu passage → 422           │
                       │   ├─ cache: find_current(content_hash) → "cached"  │
                       │   ├─ advisory lock theo cache_key (chống tạo đôi)  │
                       │   └─ generate_validated                            │
                       │        usage.check_budget → concurrency_slot       │
                       │        retry.call_with_retry (backoff + jitter)    │
                       │        ExplanationGenerator.generate ──────────────┼──▶ OpenAI Responses API
                       │        validation.validate (2 lớp)                 │    (Structured Outputs)
                       │        lỗi định dạng → thử lại có phản hồi lỗi     │
                       │   save_explanation (status generated/needs_review) │
 POST /batch ─────────▶│ jobs.create_batch → explanation_jobs + items      │
                       │ worker.ExplanationWorker (thread trong API hoặc    │
                       │   tiến trình riêng): claim SKIP LOCKED + lease →   │
                       │   generate_for_question cho từng item              │
 POST /export-prompt ─▶│ prompts.render_manual  (ChatGPT thủ công)         │
 POST /manual-import ─▶│ validation.validate → preview / lưu (needs_review)│
                       └──────────────────────────────────────────────────┘
```

## Thành phần

| Module | Trách nhiệm |
|---|---|
| `interfaces.py` | `ExplanationGenerator` (mở rộng từ PR1), `GenerationResult`, `Usage`, các lỗi provider có cờ `retryable` |
| `providers/openai_provider.py` | `OpenAIExplanationGenerator`: `client.responses.parse(text_format=ExplanationPayload, store=False)`, map lỗi SDK → lỗi nội bộ |
| `providers/registry.py` | Chọn generator theo cấu hình; báo lý do khi không khả dụng; điểm cắm fake cho test |
| `context.py` | `QuestionContext` lấy từ DB (câu, lựa chọn, passage, đáp án verified, lựa chọn thật của người học), quy tắc đủ điều kiện, `content_hash` |
| `payload.py` | Schema lời giải v1.0 (Pydantic), view lỗi người học suy ra |
| `prompts/` | Prompt theo phiên bản (file `.md`), render dữ liệu an toàn, prompt thủ công |
| `validation.py` | Kiểm định 2 lớp (xem `ai-quality-validation.md`) |
| `retry.py`, `usage.py` | Retry giới hạn; log từng lần gọi, chi phí ước tính, ngân sách, giới hạn đồng thời |
| `service.py` | Sinh/cache/khoá, phiên bản & stale, duyệt/từ chối, chế độ thủ công |
| `jobs.py`, `worker.py` | Tác vụ hàng loạt lưu trong DB và worker local |
| `router.py` | HTTP mỏng |

Không có logic gọi AI trong router hay React component.

## Quyết định chính

| Quyết định | Lý do |
|---|---|
| Mở rộng `ai_explanations` (PR1) thay vì bảng mới | Bảng đã có đúng vai trò; chỉ thêm cột phiên bản, cache, kiểm định, duyệt. |
| AI không bao giờ ghi vào `questions` | Đáp án chuẩn chỉ do người dùng xác nhận (PR1/PR2). Lời giải sai đáp án bị từ chối; nghi ngờ của AI chỉ được gắn cờ. |
| Chỉ chữa câu `verified`; câu đọc hiểu phải có passage | Không có căn cứ để giải thích khẳng định. |
| Lời giải chung + view lỗi người học suy ra | Mỗi phương án sai có `common_misconception` và `how_to_distinguish`, nên phân tích lỗi cho bất kỳ lựa chọn nào được lấy từ lời giải chung — không có dữ liệu cá nhân trong cache, không gọi AI riêng cho từng người. |
| Stale tính khi đọc (so `content_hash`) | Không cần trigger; đổi nội dung câu, lựa chọn, passage hoặc đáp án verified là lời giải cũ tự thành "đã cũ". |
| Job trong DB + worker có lease | Sống qua reload và restart; không cần Celery/Redis cho máy cá nhân. Trạng thái không nằm trong RAM. |
| Advisory lock theo cache key | Hai yêu cầu cùng lúc cho cùng một câu không gọi AI hai lần (yêu cầu sau nhận 409, worker để item quay lại hàng đợi). |
| `store=False` | Không lưu hội thoại trên kho Responses của OpenAI. |

## Model mặc định

`OPENAI_MODEL=gpt-6-astra` — tài liệu Structured Outputs của OpenAI (kiểm tra ngày 2026-11-10) khuyến nghị
model này cho dự án mới và dùng nó trong ví dụ `responses.parse(text_format=…)`. SDK `openai` 2.54.
Model là cấu hình, không hardcode: bất kỳ model nào hỗ trợ Responses API + Structured Outputs đều dùng
được. **Chưa gọi thử API thật** trong môi trường phát triển (không có API key) — xem README để chạy
test tích hợp opt-in.

## Đồng bộ Android về sau

Lời giải gắn với `question_id` (UUID ổn định), chỉ số 0-based, `schema_version` — Android có thể nhận
nguyên `explanation_json`. Chỉ nên đồng bộ lời giải `approved` (xem `android-integration-plan.md`).
