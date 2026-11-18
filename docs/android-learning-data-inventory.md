# Kiểm kê nguồn nội dung học N3 Sensei

Audit source Android chỉ đọc ngày 2026-11-16. Repository ở commit `07f0d0bfd84086cc322d30b8bd4ce89b59222a92`, branch `main`, có remote `origin`; worktree có thay đổi người dùng chưa commit. Không chạy Gradle, Room migration, build hay script Android.

## Nguồn thực tế

Android học từ content pack JSON UTF-8 trong `app/src/main/assets/content/`. `AndroidContentImportRepository` đọc các asset được khai báo sẵn và `ContentPackImporter` kiểm tra pack version trước khi cài vào Room. Room là bản dữ liệu runtime và có cả tiến độ cá nhân; Web không đọc database đó. Người dùng cũng có thể import JSON content pack riêng vào Android qua Settings, nhưng file riêng của họ không nằm trong Git repo và không tự xuất hiện ở Web.

`docs/CONTENT_FORMAT.md` mô tả wire format `n3sensei-content-pack` v1: stable pack/item/lesson/example IDs, lesson order, vocabulary, Kanji, grammar/exercises, furigana, sources và `licenseVerified`. Tools trong `tools/content/` tạo một số pack từ source materials; Web chỉ đọc output JSON, tuyệt đối không chạy các script đó.

| Android source | Git tracking tại audit | Pack/version | Nội dung khai báo | Quyền nguồn | Kết quả Web |
|---|---|---|---|---|---|
| `app/src/main/assets/content/n3-kanji.json` | tracked | `n3-kanji` v3 | 448 Kanji, 1.279 examples | 3/4 sources verified; 393 Kanji và 1.272 examples gắn nguồn verified | Chỉ phần verified được nhập; phần còn lại giữ blocked |
| `app/src/main/assets/content/n3-grammar.json` | tracked | `n3-grammar` v4 | 174 grammar, 360 examples | 64 source entries verified; default source và phần lớn examples chưa verified | 64 grammar có nguồn verified; không xuất bản examples chưa rõ quyền |
| `app/src/main/assets/content/mimikara-n3-vocab.json` | tracked | `mimikara-n3-vocab` v2 | 880 vocabulary, 870 examples | 0/2 sources verified; file ghi rõ sách thương mại/chưa có quyền phân phối | Chặn toàn bộ |
| `app/src/main/assets/content/n3sensei-illustration.json` | tracked | `n3sensei-illustration` v1 | pack minh họa tự soạn | `licenseVerified=false`, còn chưa qua chuyên môn | Chặn toàn bộ |
| `app/src/main/assets/content/n2-kanji.json` | **untracked tại audit** | `n2-kanji` v1 | 448 Kanji | Quyền tái sử dụng deck chưa xác minh | Scanner bỏ qua vì chỉ quét Git-tracked assets; không tự nhập |
| `app/src/main/assets/content/proverbs.json` | tracked | Không theo content-pack format | Dữ liệu tục ngữ | Không phải nguồn trong format học hiện tại | Bỏ qua |
| SQLite/Room trên thiết bị | Runtime/user data | N3Database schema 15 | Nội dung cài đặt, edits, learning progress, reviews, attempts | Có dữ liệu cá nhân | Không truy cập, không đồng bộ bằng scanner |

Scanner thực tế chỉ đọc 4 pack Git-tracked, ghi nhận commit Android `07f0d0bfd84086cc322d30b8bd4ce89b59222a92` và manifest hash `745d4e3356e2f8c69f02f8a626c0802f9ecf501f8d024e33fec5b44cb460fab0`. Source có **64 grammar, 393 Kanji, 1.272 examples** đủ license metadata. Importer giữ 1.271 examples được tham chiếu bởi item; `n3k-x-10-002` là ví dụ không có item liên kết nên không được lưu. Sau lần import production-like/dev ngày 2026-11-16, database có 4 packs, 26 lessons, 457 items và 1.271 linked examples; API/UI thật đã xác minh. Vocabulary vẫn 0 do source hiện tại là nội dung Mimikara không được phân phối.

## Server/API

Trong Android source đã kiểm tra không có API server làm nguồn chính để tải các pack học này. Các file tĩnh ở checkout local là nguồn có thể scanner truy cập. Remote Git `origin` được cấu hình nhưng Web không fetch, pull, checkout, hoặc đọc private credential; remote commit chỉ được nhận sau khi checkout nguồn được cập nhật riêng. Tiến độ, edits, user words, review records, widget settings và dữ liệu backup là dữ liệu runtime/riêng tư, không phải content source.
