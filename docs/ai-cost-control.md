# Kiểm soát chi phí AI

| Cơ chế | Cấu hình | Mặc định |
|---|---|---|
| Cache: không gọi lại khi đã có lời giải hiện hành (cùng nội dung câu + đáp án) | — | bật |
| Giới hạn số lần gọi mỗi ngày (UTC) | `AI_MAX_REQUESTS_PER_DAY` | 200 |
| Ngân sách USD mỗi tháng (UTC) | `AI_MONTHLY_BUDGET_USD` + `AI_PRICE_INPUT_PER_1M_TOKENS` + `AI_PRICE_OUTPUT_PER_1M_TOKENS` | tắt (0) |
| Số yêu cầu đồng thời | `AI_MAX_CONCURRENT_REQUESTS` | 2 |
| Số câu tối đa mỗi tác vụ hàng loạt | `AI_BATCH_MAX_QUESTIONS` | 50 |
| Token đầu ra tối đa mỗi lần gọi | `AI_MAX_OUTPUT_TOKENS` | 8000 |
| Thử lại lỗi tạm thời | `AI_MAX_RETRIES` (backoff mũ + jitter, tôn trọng `Retry-After`) | 3 |
| Thử lại lỗi định dạng | `AI_MAX_FORMAT_RETRIES` | 1 |
| Timeout mỗi lần gọi | `AI_REQUEST_TIMEOUT` (giây) | 90 |

- Mỗi lần gọi (thành công hay thất bại) được ghi vào `ai_requests`: provider, model, câu hỏi, trạng
  thái, mã lỗi, token vào/ra, chi phí ước tính, thời gian. **Không** lưu prompt/nội dung trả về.
- Ngân sách được kiểm tra **trước** mỗi lần gọi; vượt ⇒ `429 ai_budget_exceeded` (tác vụ hàng loạt:
  câu đó báo lỗi, các câu khác không bị ảnh hưởng). Lần gọi thất bại vẫn bị tính.
- Giá token thay đổi theo thời gian và model nên **không hardcode**: điền giá hiện hành của
  `OPENAI_MODEL` từ trang giá của OpenAI. Không điền ⇒ chỉ đếm token, `cost_usd` = null, giới hạn USD
  không áp dụng (giới hạn số lần gọi vẫn áp dụng).
- `GET /api/v1/explanations/capabilities` trả số lần gọi hôm nay, token và chi phí tháng này.
- Không retry lỗi xác thực, hết quota, request sai hoặc lỗi kiểm định (tránh tốn tiền vô ích).

Ước lượng một câu: ~1–2k token vào (prompt + dữ liệu), ~2–4k token ra (tuỳ model; model suy luận
có thể dùng thêm token). Chi phí thực tế phụ thuộc giá model bạn chọn — **chưa đo thực tế** vì chưa gọi
API thật trong PR3.
