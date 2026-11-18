# Dethitiengnhat capture

## Trang hỗ trợ

Adapter chỉ nhận URL `https://dethitiengnhat.com/jlpt/N3/{exam}/1` (Từ vựng) và `/3` (Ngữ pháp/Đọc hiểu), bao gồm host `www`. Trang danh sách và phần nghe `/2` bị từ chối.

Khi người dùng bấm popup, adapter duyệt các node `big_item`, `question_content`, `question_list`, `answers#QS…`, `#AS…` và `#diemso…`. Thứ tự DOM giữ quan hệ phần thi, câu hỏi và passage. Nội dung inline chỉ giữ text, `<u>`, `<ruby>`, `<rt>` và xuống dòng; không chuyển HTML tùy ý. Lựa chọn chỉ được lấy từ radio `checked`. Đáp án chỉ được lấy từ dấu đúng/sai đã render hoặc phần tử answer key; khi hai nguồn mâu thuẫn, capture giữ dấu kết quả và gắn cờ để người dùng kiểm tra.

Payload schema `1.0` gồm capture UUID, nguồn, URL, N3, tiêu đề/loại đề, trạng thái chấm, thời điểm capture và câu hỏi với index 0-based. Index thiếu để `null`; API chuyển index sang dạng 1-based của PR2. Dấu đáp án nguồn không đồng nghĩa với `verified`.

## Trạng thái xác minh

Fixture HTML tự tạo kiểm tra câu đã chấm/chưa chấm, radio, đáp án đúng, gạch chân, ruby/furigana, passage, Unicode, key mâu thuẫn và layout không hỗ trợ. Backend integration test xác minh draft, idempotency, auth, validation và không tạo exam.

Trang nguồn đã được xem ở [danh sách N3](https://dethitiengnhat.com/jlpt/N3), [N3/32/1](https://dethitiengnhat.com/jlpt/N3/32/1) và [N3/32/3](https://dethitiengnhat.com/jlpt/N3/32/3). Trong môi trường triển khai này, không thực hiện thao tác làm/nộp bài trực tiếp trên trang và không quan sát runtime DOM sau nút chấm. Do đó cấu trúc sau khi chấm hiện chỉ được kiểm thử bằng fixture; cần xác minh thủ công trên một trang kết quả thực tế trước khi coi parser đã được kiểm chứng live. Khi DOM thay đổi, popup báo không nhận diện được hoặc bản preview phải được kiểm tra và sửa thủ công.
