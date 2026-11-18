# Bảo mật luồng nhập đề

| Rủi ro | Biện pháp |
|---|---|
| SSRF / thu thập tự động | Không có endpoint nhận URL để tải. `source_url` (và `<link rel=canonical>` đọc từ HTML dán vào) chỉ được **lưu**. Test `test_no_server_side_url_fetching` chặn socket trong lúc import. |
| XSS từ HTML dán vào | HTML được phân tích bằng lxml (BeautifulSoup), không chạy JS, không render. Trước khi trích xuất: xoá `script/style/iframe/object/embed/svg/img/link/meta/template…`, comment, mọi thuộc tính `on*`, `style`, `srcdoc`, `formaction`, URL `javascript:/vbscript:/data:`. Chỉ lấy **văn bản**. |
| XSS khi hiển thị | Frontend không dùng `dangerouslySetInnerHTML`. `RichText` chỉ dựng `<u>`, `<ruby>`, `<rt>` từ chuỗi; còn lại là text. HTML gốc chỉ hiển thị trong `<textarea>` (text). |
| File độc hại giả ảnh | Loại file xác định bằng magic bytes + Pillow (phải khớp nhau), không tin đuôi file hay `Content-Type`. Chỉ PNG/JPEG/WEBP. |
| Bom giải nén / ảnh khổng lồ | Giới hạn số pixel (`IMPORT_MAX_IMAGE_PIXELS`, mặc định 60 MP) kiểm tra trước khi giải mã; bật `Image.MAX_IMAGE_PIXELS`. |
| Payload ẩn / metadata (GPS…) | Ảnh được xoay theo EXIF rồi **mã hoá lại thành PNG** không mất dữ liệu; file gốc không được lưu, mọi metadata/phần thừa bị loại. |
| Path traversal | Tên file lưu do server sinh (`<draft_id>/<asset_id>.png`); `storage.resolve` từ chối `..`, đường dẫn tuyệt đối và mọi đường ra ngoài thư mục gốc; CHECK trong DB (`storage_path !~ '(^/|\.\.)'`). Tên file gốc chỉ để hiển thị. |
| Phục vụ file | `GET /imports/{id}/assets/{asset_id}` chỉ trả file của đúng draft, `Content-Type: image/png`, `X-Content-Type-Options: nosniff`, `inline`. |
| Lạm dụng tài nguyên | Giới hạn: văn bản 200 000 ký tự, HTML 3 MB, 10 ảnh × 10 MB, kiểm tra `Content-Length` sớm (413). Rate limit 30 yêu cầu/phút/IP cho các POST nhập (429). OCR có timeout (`OCR_TIMEOUT_SECONDS`). |
| Lệnh hệ thống | Tesseract gọi bằng `subprocess.run([...])`, không qua shell, argv cố định, đường dẫn ảnh do server sinh. |
| Ghi trùng / race | Khoá dòng draft khi commit, unique index bài làm theo draft, optimistic locking bằng `version`. |
| Tin tưởng dữ liệu sai | Không có đường nào tự đặt `verified`: chỉ cờ `answer_confirmed` do người dùng bấm. |
| Lỗi tiết lộ thông tin | Lỗi trả envelope chung; IntegrityError → 409 chung; lỗi OCR được log, client chỉ thấy thông báo ngắn. |

## Giới hạn hiện tại

- Rate limiter nằm trong bộ nhớ tiến trình: đúng cho một tiến trình local. Nhiều worker/sau proxy
  cần store dùng chung (Redis) và đọc IP thật từ proxy tin cậy.
- Chưa có xác thực (giống PR1). Bắt buộc thêm trước khi mở ra ngoài `127.0.0.1`, vì API nhận upload.
- OCR chạy đồng bộ trong request; ảnh lớn có thể mất vài giây đến hàng chục giây.

## Bản quyền nội dung

Chỉ xử lý nội dung người dùng chủ động cung cấp, cho mục đích ôn tập cá nhân. Repository không chứa
nội dung thu thập từ dethitiengnhat.com; fixture là câu hỏi tự soạn.
