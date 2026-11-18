# Chrome Extension security

- Popup chỉ trích xuất khi người dùng bấm nút. `activeTab` cấp quyền tạm thời với tab đang được người dùng thao tác; không có content script chạy nền.
- Permissions: `activeTab`, `scripting`, `storage`. Không có `tabs` permission, `<all_urls>`, cookie, webRequest hoặc quyền truy cập ChatGPT. Host permissions chỉ gồm `127.0.0.1`/`localhost` (HTTP/HTTPS) cho frontend/backend.
- Adapter chỉ đọc DOM đang hiển thị và checked radio. Không đọc cookie, localStorage, session, credential, mật khẩu hoặc dữ liệu tài khoản; không chạy code từ trang nguồn.
- Extension chỉ gửi capture tới backend loopback đã cấu hình (`credentials: omit`, không gửi request ra dịch vụ ngoài). Cấu hình URL từ chối host không phải loopback. Frontend URL cũng chỉ cho phép loopback.
- Backend capture bị tắt mặc định. Khi bật, cần secret bearer riêng tối thiểu 32 ký tự và peer IP loopback; so sánh constant-time. Kiểm tra Origin/CORS không được xem là xác thực. Kết nối backend local là HTTP, phù hợp cho app local; secret này không nên dùng trên mạng không tin cậy.
- Payload có giới hạn dung lượng/schema, URL nguồn được allowlist, và capture trùng được chống bằng unique fingerprint. Backend tạo draft, không tạo exam, không đánh dấu answer verified.
- Token chỉ nằm trong extension `chrome.storage.local`, không được gửi về trang nguồn hay in ra popup. Người dùng có thể xóa token trong Options. Máy local và browser profile vẫn là vùng tin cậy của secret.
- Không dùng OAuth, ChatGPT tokens, API key, automation ChatGPT, remote executable code, Selenium hoặc Playwright để điều khiển trang nguồn.
