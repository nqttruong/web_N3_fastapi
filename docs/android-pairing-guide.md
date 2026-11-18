# Ghép nối N3 Sensei với JLPT AI Review

## Điều kiện mạng

Android N3 Sensei chỉ chấp nhận URL `https://` và dùng certificate validation mặc định của Android.
Hãy dùng hostname có certificate được Android tin cậy. Với LAN, có thể dùng domain bạn kiểm soát,
DNS riêng trỏ hostname về IP LAN và certificate CA công khai hợp lệ (ví dụ cấp bằng DNS-01). Không
dùng địa chỉ `127.0.0.1` trên điện thoại, không dùng HTTP, không dựa vào certificate tự ký chưa
được Android tin, và không tắt TLS validation. Không mở cổng development ra Internet công khai.

Backend mặc định bind `127.0.0.1`; để điện thoại truy cập, đặt backend sau HTTPS reverse proxy trên
mạng riêng. Giới hạn proxy tới các route `/api/v1/sync/*`, cấu hình CORS origin Web cụ thể, và giữ
các API dữ liệu Web/operator ở loopback/private. Cấu hình trusted proxy forwarding chính xác.

## Ghép nối lần đầu

1. Đặt `SYNC_ADMIN_KEY` thành secret ngẫu nhiên tối thiểu 32 ký tự trong môi trường backend nếu
   trang Settings/admin API được truy cập qua mạng. Không đưa secret vào URL hoặc log.
2. Chạy migration additive: `cd backend && uv run alembic upgrade head`.
3. Khởi động lại FastAPI process để nạp code/revision mới và cấu hình HTTPS proxy. Không restart
   PostgreSQL; migration không thay dữ liệu học tập.
4. Mở Web **Cài đặt → Đồng bộ Android**. Nhập admin key nếu backend yêu cầu; chọn **Tải danh sách
   thiết bị**, rồi **Tạo mã ghép nối**.
5. Mã ngẫu nhiên chỉ hiển thị một lần, mặc định hết hạn sau 10 phút (tối đa 15 phút). Không gửi mã
   qua chat/log. Mã mới thu hồi các mã cũ chưa dùng.
6. Trên N3 Sensei: **Cài đặt → Đồng bộ JLPT AI Review**. Nhập base URL HTTPS có `/api/v1` theo
   contract hiện tại (ví dụ `https://sync.example.test/api/v1`) và pairing code. Chọn ghép nối.
7. Pair chỉ cấp credential. Bấm **Đồng bộ ngay** trong Android để thực hiện pull/push. Settings Web
   chỉ ghi nhận last request/pull/push thực sự quan sát được; không khẳng định full sync nếu client
   không gửi tín hiệu hoàn tất.

## Theo dõi và thu hồi

Trong cùng trang, thiết bị hiển thị thời điểm ghép nối, request gần nhất, pull gần nhất, push review
event gần nhất và trạng thái revoke. Nếu bị revoke, Android nhận 401 và cần ghép nối lại. Có thể
thu hồi thiết bị trong Web hoặc ngắt kết nối từ Android khi online. Disconnect offline chỉ xóa
credential cục bộ; operator cần revoke server-side nếu muốn chặn ngay.

Android đã ghép nối nhưng không gửi attempt history, saved words, `learning_progress`, mistake
notebook hay JLPT analytics. Xem `android-sync-capability-matrix.md` trước khi diễn giải trạng thái.

## Kiểm tra an toàn

- Verify certificate/hostname trên chính Android; không cài bypass hoặc custom trust workaround.
- Xác nhận **Request gần nhất**, **Pull gần nhất**, và **Push review event gần nhất** thay đổi sau
  thao tác tương ứng.
- Thử thu hồi thiết bị và xác nhận request tiếp theo nhận unauthorized.
- Không có emulator/điện thoại thật trong kiểm thử hiện tại: **Device verification pending**.
