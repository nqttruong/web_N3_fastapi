# Parser adapters

Adapter = hàm thuần: dữ liệu thô → `DraftContent` + ghi chú. Không truy cập mạng, không truy cập DB,
không bao giờ xác nhận đáp án. Mã: `backend/app/imports/adapters/`.

| Adapter | Đầu vào | Mức hỗ trợ | Câu bị gắn "cần kiểm tra" |
|---|---|---|---|
| `dethitiengnhat_html` | HTML trang đề dethitiengnhat.com | **Đã kiểm chứng trên trang thật** (xem dưới) | Chỉ khi có bất thường |
| `generic_text` | Văn bản dán | Theo quy ước chung, heuristics | Khi không chắc |
| `generic_html` | HTML cấu trúc lạ | Chuyển HTML → văn bản → `generic_text` | **Mọi câu** |
| `ocr_text` | Văn bản do Tesseract đọc từ ảnh → `generic_text` | Phụ thuộc chất lượng OCR | **Mọi câu** |

Chọn adapter HTML: nếu nhận ra cấu trúc Dethitiengnhat → adapter riêng; ngược lại → generic (nếu URL
là dethitiengnhat.com nhưng cấu trúc không khớp → cảnh báo `dethitiengnhat_layout_mismatch`).

## Dethitiengnhat — đã khảo sát ngày 2026-11-10

Đã tải hợp lệ 2 trang công khai (`/jlpt/N3/32/1` từ vựng, `/jlpt/N3/32/3` ngữ pháp + đọc hiểu; robots.txt
cho phép), và chấm thử một lần trên trình duyệt headless để xem DOM sau khi bấm "Tính Điểm". Không đăng
nhập, không vượt CAPTCHA, không thu thập hàng loạt. **Không lưu nội dung trang vào repository**; fixture
trong `tests/fixtures/imports/` chỉ mô phỏng cấu trúc class/id với câu hỏi tự soạn.

Kết quả chạy adapter trên dữ liệu trang thật (chỉ kiểm thử cục bộ):

| Trang | Câu | 4 lựa chọn | Đáp án trang | Đoạn văn | Lựa chọn của người dùng |
|---|---|---|---|---|---|
| N3/32/1 (chưa chấm) | 35/35 | 35/35 | 35/35 | 0 | — (thông báo `not_scored`) |
| N3/32/3 (chưa chấm) | 38/38 | 38/38 | 38/38 | 9 | — |
| N3/32/1 (đã chấm, chọn 2 câu) | 35/35 | 35/35 | 35/35 | 0 | 2/2 đúng như đã chọn |
| N3/32/1 đã chấm — **dán văn bản** | 35/35 | 35/35 | chỉ câu đã trả lời | 0 | 2/2 |

Cấu trúc nhận diện:

| Phần tử | Ý nghĩa |
|---|---|
| `div.big_item` | Tiêu đề 問題 → suy ra dạng câu (読み方 → kanji_reading, 漢字で書く → orthography, 文章全体の内容 → text_grammar, 文章を読んで → reading…) |
| `div.question_content` | Đoạn đọc hiểu, dùng chung cho các câu sau đến tiêu đề kế tiếp; `<br>` → xuống dòng |
| `div.question_list .japanese-reader-content` | Nội dung câu ("1. …" — bỏ số đầu dòng nếu trùng số câu) |
| `div.answers#QS{n}{k}` | Lựa chọn k của câu n ("k) …"); sau khi chấm: `正解:　` / `不正解:　` ở đầu |
| `div#AS{n}` (ẩn) | Đáp án của trang |
| `div#type{n}` | 1 từ vựng · 2 ngữ pháp · 3 đọc hiểu · 4 nghe (chưa hỗ trợ, mặc định không lưu) |
| `div#diemso{n}` | Điểm; `0` = câu ví dụ (例) → mặc định không lưu |
| `#trinhdothi` | Cấp độ; khác N3 → cảnh báo |

Suy ra lựa chọn của người dùng (đúng theo hàm `Saiten()` của trang): phương án có `不正解:` là lựa
chọn sai của người dùng; nếu chỉ có `正解:` thì người dùng đã chọn đúng phương án đó; câu không có ký
hiệu = bỏ trống. Thuộc tính `checked` trên radio (nếu có) được ưu tiên.

Giới hạn đã biết:
- "Xem nguồn trang" / tải HTML thô **không** chứa kết quả chấm (do JavaScript tạo) → phải dùng
  DevTools → *Copy outerHTML* sau khi chấm.
- Furigana trên trang là chữ trong ngoặc (`緑葉（りょくよう）`), được giữ nguyên như nội dung.
- Câu nghe (聴解) không được hỗ trợ.
- Trang thay đổi cấu trúc → adapter không nhận ra → rơi về `generic_html` (mọi câu cần kiểm tra),
  không giả vờ parse thành công.

## Generic text — quy ước nhận diện

| Thành phần | Dạng được nhận |
|---|---|
| Tiêu đề phần | `問題１ …`, `文法 問題1`, `読解 問題5` |
| Câu hỏi | `1.` `１．` `1：` `問1` `問 1.` `【19】` (giữ nguyên `【19】` làm nội dung) |
| Lựa chọn | `1)` `１）` `A.` `Ａ．` `①`, mỗi dòng một phương án hoặc nhiều phương án trên một dòng (`1) あ 2) い`, `①あ ②い`) |
| Đáp án trang | `正解: 2`, `答え：A`, `Đáp án: 3`, khối `解答` cuối bài (`1. 3` / `2. 4`) |
| Lựa chọn người dùng | `あなたの答え: 1`, `Bạn chọn: 2`, ký hiệu `正解:`/`不正解:` đầu phương án |
| Đoạn văn | `（１）` + đoạn, hoặc khối chữ dài trong phần đọc hiểu, trước câu hỏi |
| Bỏ qua | Nhãn giao diện đã biết ("Đọc tiếng Nhật", "Tính Điểm"…); dòng không nhận diện được → cảnh báo `ignored_lines` (liệt kê, không lặng lẽ bỏ) |

Phân biệt "1." là câu hỏi hay lựa chọn: kiểu chấm chỉ được coi là lựa chọn nếu các lựa chọn của câu
đang dùng kiểu chấm, đúng thứ tự tiếp theo và chưa đủ 4.

Ghi chú parser (bắt người dùng kiểm tra): `missing_number`, `duplicate_number`, `option_count`,
`option_order`, `answer_from_markers`, `ambiguous_markers`, `key_conflict`, `example`, `ocr_source`,
`unverified_layout`, `listening_unsupported`, `empty_text`.

## Văn bản được giữ nguyên

- Không đổi kanji, hiragana/katakana, trường âm, toàn/nửa độ rộng; chỉ bỏ ký hiệu đầu dòng (số câu,
  nhãn phương án, `正解:`) và khoảng trắng hai đầu.
- Giữ một tập markup nội tuyến tối thiểu: `<u>…</u>` (gạch chân trong câu 漢字読み) và
  `<ruby>漢字<rt>かんじ</rt></ruby>`. Frontend (`RichText`) chỉ dựng đúng các thẻ này thành phần tử
  React; mọi thứ khác hiển thị như chữ thường — không dùng `innerHTML`.
- OCR: chỉ xoá khoảng trắng Tesseract chèn giữa hai ký tự tiếng Nhật.

## Thêm adapter mới

1. Tạo class có `name` và `parse(raw) -> ParseResult` trong `adapters/`; ném `UnsupportedInputError`
   nếu không nhận ra cấu trúc.
2. Thêm nhánh nhận diện trong `parse_html` (hoặc chọn theo method).
3. Thêm fixture **tự soạn** mô phỏng cấu trúc + test trong `tests/test_import_parsers.py`.
4. Ghi lại ngày khảo sát và kết quả kiểm thử thực tế trong tài liệu này.
