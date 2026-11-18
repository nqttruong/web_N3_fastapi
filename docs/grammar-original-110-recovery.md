# Khôi phục 110 mẫu Grammar gốc N3

Cập nhật 2026-11-18. Đây là ghi nhận lần đồng bộ thực tế từ N3 Sensei vào database JLPT AI Review Web.

## Nguyên nhân

`app/src/main/assets/content/n3-grammar.json` trong Android có 174 Grammar stable ID: `n3g-g001`–`n3g-g110` là 110 mẫu gốc, `n3g-g111`–`n3g-g174` là 64 mẫu bổ sung từ `N3.pdf`. Trước lần khôi phục, Web chỉ có 64 ID sau. 110 bản ghi gốc khai báo source `vnjp-np-001`–`vnjp-np-110`, mỗi source có `licenseVerified=false` theo metadata lịch sử; bảng `learning_source_rights` chưa có quyền private cho các source này.

Scanner ở `backend/app/learning_content/source.py::_project_pack` chỉ xuất bản record khi metadata nguồn đã xác minh hoặc cặp `(pack_id, source_id)` có quyền `approved=true, scope=private`. Worker ở `backend/app/learning_content/service.py::claim_and_process_one` đã đọc đúng các quyền theo từng cặp đó. Đây là nguyên nhân chính xác; không có giới hạn 64 ở API/frontend và schema Android không thiếu trường bắt buộc.

## Quyền và phạm vi

Người sở hữu dự án trực tiếp xác nhận ngày 2026-11-18 quyền sử dụng bộ dữ liệu N3 Sensei của mình trong ứng dụng Web JLPT AI Review cá nhân. Quyền được lưu riêng cho đúng 110 cặp `n3-grammar/vnjp-np-NNN`, với phạm vi `private`, không phân phối lại công khai hoặc cấp phép lại. Không thay metadata `licenseVerified=false` trong Android và không cấp quyền cho source `n3-grammar-examples`.

Phân biệt ba điều: quyền sử dụng cá nhân do chủ dự án xác nhận; metadata license lịch sử trong asset Android; và quyền phân phối công khai. Việc khôi phục chỉ xác lập điều thứ nhất, không xác nhận điều thứ ba hay xác minh chuyên môn nội dung.

## Kết quả trước/sau

| Dữ liệu | Trước | Sau |
|---|---:|---:|
| Grammar gốc `n3g-g001`–`n3g-g110` | 0 | 110 |
| Grammar PDF `n3g-g111`–`n3g-g174` | 64 | 64 |
| Tổng Grammar stable ID duy nhất | 64 | 174 |
| Ví dụ gắn trực tiếp với 110 Grammar gốc | 0 | 220 |
| Liên kết Grammar–ví dụ | 0 | 220 |
| Riêng nguồn `n3-grammar-examples` | 140 bị chặn | 140 vẫn bị chặn |
| Progress Grammar hiện hữu | 10 | 10, giữ nguyên |
| Study events Grammar hiện hữu | 19 | 19, giữ nguyên |

Importer được chạy qua queue và `claim_and_process_one`, không ghi trực tiếp vào bảng nội dung. Run `cdc8c092-86c4-4ed8-8c34-9ebd3eb5f28a` kết thúc `succeeded`: 110 Grammar, 220 examples và 15 lesson source mới; không thay hash của 64 Grammar cũ. 174/174 ID trong dải đã được kiểm tra, không thiếu hoặc trùng. 220 ví dụ gốc không có furigana trong nguồn (`furigana: null`), giữ nguyên như vậy; không tự bổ sung.

Sync worker duyệt toàn manifest Android. Run cũng ghi nhận pack metadata `n2-kanji` chưa có item có thể xuất bản do source chưa đủ điều kiện; không có Kanji/Vocabulary item nào được thêm hoặc thay đổi bởi run này. Đây không phải nguyên nhân hay điều kiện của việc nhập Grammar.

Không có migration mới. Alembic vẫn `0014`. Lần sync lại thành công `no_changes`; số item, example, stable IDs, content hash, Grammar progress và study events không đổi.

## Kiểm thử và hiển thị

- `backend/tests/test_n3_readonly_parity.py`: không cấp quyền vẫn chỉ thấy 64 source đã xác minh; cấp quyền cho đúng 110 source gốc tạo đủ 174 ID, 220 ví dụ, và vẫn chặn 140 example source độc lập.
- Backend tests liên quan sync/parity/study: 20 passed.
- Full `./scripts/check.sh`: backend 253 passed, 2 skipped; frontend 107 passed; extension 23 passed và build Chrome/Firefox; Playwright E2E 16 passed; Ruff, format check, mypy, ESLint, TypeScript và production build đều đạt. Hai skip backend là thiếu Tesseract `jpn` và OpenAI live test opt-in; không gọi OpenAI.
- API `GET /api/v1/learning-content/items?type=grammar` phân trang: total 174, 174 ID duy nhất; API lesson trả 25 lesson, tổng item 174.
- Trình duyệt Chromium trên `/learning`: 25 thẻ lesson Grammar, tổng số lượng hiển thị 174; trang chi tiết bài 1 hiển thị pattern, nghĩa/cách dùng và các ví dụ nguồn. Không có lỗi trình duyệt.

Android chỉ được đọc; không sửa, build, chạy Gradle hoặc ghi file. Không dùng OpenAI API/ChatGPT credential. Không reset database, xóa dữ liệu, commit hoặc push.
