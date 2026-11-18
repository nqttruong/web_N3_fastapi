# Feasibility: ChatGPT account for JLPT AI Review

> **Tài liệu lịch sử, đã được thay thế cho PR3.5.** Hướng hiện hành là workflow ChatGPT Web thủ công trong
> `manual-chatgpt-workflow.md`. Không triển khai Sign in with ChatGPT, OAuth, PKCE hoặc token theo yêu cầu mới.

**Kiểm tra tài liệu:** 2026-11-11. Đây là đánh giá kỹ thuật; chưa có OAuth login, token, inference request hay xác minh bằng tài khoản thật trong repository này.

## Kết luận

OpenAI hiện có cơ chế chính thức **Sign in with ChatGPT – ChatGPT plan usage cho ứng dụng open-source chạy local**. Cơ chế này cho phép người dùng đủ điều kiện cấp quyền để ứng dụng gọi Responses API bằng OAuth token, không cần OpenAI API key/client secret. Vì vậy PR3.5 khả thi theo hướng được hỗ trợ; đây không phải việc dùng phiên ChatGPT web hoặc biến subscription thành API key.

Tài liệu OpenAI phân biệt identity-only sign-in với quyền inference: cần scope `chatgpt.tokens.use.direct` được người dùng chấp thuận. Luồng OSS đăng ký client động theo tài khoản/workspace và yêu cầu `ext_agent_host_id` ổn định. OpenAI ghi nhận use case ứng dụng open-source/local-hosted; ứng dụng trả phí hoặc remote-hosted cần đi qua quy trình partner riêng. Xem [quickstart](https://developers.openai.com/siwc/quickstart), [overview cho OSS/local](https://developers.openai.com/siwc/token-sharing-open-source) và [registration/sign-in](https://developers.openai.com/siwc/token-sharing-open-source/sign-in).

## Điều kiện và giới hạn

- Luồng lần đầu dùng `client_id=dynamic_agent_client`, `agent_name_hint` đúng tên JLPT AI Review, PKCE, `state`, OIDC `nonce`, redirect loopback `127.0.0.1`; callback trả `client_id` đã cấp để lưu và tái sử dụng. Không cần client secret hay partner API key.
- Cần các scope identity và plan usage: `openid profile email offline_access resource.invoke chatgpt.tokens.use.direct`. Nếu consent không có `chatgpt.tokens.use.direct`, phải tắt inference và cho phép user thử cấp quyền lại theo lựa chọn rõ ràng.
- Tài liệu quickstart nêu ChatGPT Plus/Pro đủ điều kiện cho OSS usage; quyền thực tế vẫn phụ thuộc account/workspace, khu vực, admin policy, model và usage limits. Một giới hạn app có thể dừng request; không có quota/renewal time bảo đảm cho ứng dụng.
- Chỉ model được trả về cho tài khoản qua `GET https://api.openai.com/v1/models` mới được chọn. Inference dùng public `POST https://api.openai.com/v1/responses` với bearer OAuth access token. Không dùng `backend-api` hoặc endpoint nội bộ ChatGPT.
- Preview hiện yêu cầu `stream=true` và `store=false`; input phải gửi đầy đủ ở mỗi request và dùng `instructions` hoặc developer message, không gửi system role message. Một số request fields đang bị cấm, gồm `max_output_tokens`, `temperature`, `top_p`, `metadata`, `background`, `previous_response_id`; audio/video, Files API và một số hosted tools không hỗ trợ. Xem [models/inference](https://developers.openai.com/siwc/token-sharing-open-source/models-and-inference) và [preview limitations](https://developers.openai.com/siwc/token-sharing-open-source/preview-limitations).
- Access/refresh token phải được lưu cục bộ dưới quyền kiểm soát của người dùng, được bảo vệ, refresh an toàn và không ghi log/commit. OpenAI terms cấm dùng token ở môi trường remote/managed cho luồng OSS, chia sẻ/quy đổi usage giữa user, hoặc cung cấp proxy API đa dụng. Xem [Sign in with ChatGPT Terms](https://openai.com/policies/sign-in-with-chatgpt-terms/).
- ChatGPT plan usage đi theo entitlement/usage của ChatGPT account, không phải API billing; không lấy API key và không bảo đảm inference không bị giới hạn. ChatGPT/API billing vẫn là hai hệ thống riêng ([billing FAQ](https://help.openai.com/en/articles/9039756-managing-billing-for-chatgpt-and-the-api-platform)).

## Tương thích với code hiện tại

- FastAPI có thể sở hữu callback loopback và trao output JSON đã parse/validate cho pipeline hiện hữu; Next.js có thể hiển thị trạng thái account, consent và model. Mọi request phải phát sinh từ thao tác người dùng và chạy trên local runtime mà họ kiểm soát.
- Pipeline hiện tại đã lưu `explanation_json`, usage, provenance, validation và review status; manual prompt/JSON vẫn là fallback không tính phí API.
- Provider hiện dùng OpenAI API key và kiểu `responses.parse` đồng bộ, dựa trên `max_output_tokens`. Nó chưa đáp ứng contract preview bắt buộc stream + `store=false`, dynamic model per account hay token refresh. Chưa xác minh `text.format` JSON Schema/Structured Outputs hoạt động với scope này bằng live request; cần adapter streaming parse + contract tests trước khi bật.
- Không nên mặc định gửi background batch qua ChatGPT account: điều khoản yêu cầu user authorization, và automation/background cần consent rõ. Giữ API-key provider riêng, opt-in, không tự fallback sang đó.

## Quyết định hiện tại

1. Giữ workflow hiện tại: export prompt → ChatGPT → import structured JSON → validation → user approval. Không cần API key và đã có E2E test.
2. Không thêm OAuth code trong đợt này: PR4 đang được hoàn thiện; feasibility chỉ đánh giá khả năng và không có tài khoản/credential để kiểm tra luồng thực tế.
3. Khi bắt đầu PR3.5: thiết kế local token store, PKCE/callback, ID-token validation, account-scoped client/model selection, token refresh/revocation/error handling, privacy/consent UI, và provider streaming riêng. Giữ `AI_PROVIDER=none`/manual mode là mặc định không phát sinh API billing.
