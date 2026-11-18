# V3 gap audit — 2026-11-17

Web worktree có nhiều thay đổi chưa commit từ các PR trước; tất cả được giữ nguyên. Alembic head/current `0011`. Dev PostgreSQL trước V3: 4 packs, 26 lessons, 457 items (393 Kanji, 64 grammar, 0 vocabulary), 1.271 examples; 4 Web study events và 1 saved item thuộc dữ liệu người dùng cần bảo toàn. Android HEAD `07f0d0b` và manifest SHA-256 `5a7555d8f1f6dbee344e77c967dfa16886cee161e5ef4f584932c0652a22b88e`, 49 entry worktree do người dùng tạo từ trước; chỉ đọc.

| Mục | Hiện trạng thực tế | Chênh lệch V3 |
|---|---|---|
| PDF Mimikara | File PDF 282.654 byte, 1 trang, text-based, 19 cột nhóm, STT 1–880; bảng có term, reading (41 ô trống), nghĩa Việt, không có ví dụ. Android JSON có cùng 880 số thứ tự theo 12 bài. | Cần parser tọa độ + preview/rights riêng PDF + import idempotent; không lấy ví dụ Android chưa được phê duyệt. Một số chữ PDF và Android JSON không trùng (ví dụ row 796). |
| Learning | `/learning` đã có lesson theo từng pack, flashcard, SRS, bookmark và global lookup. Android `domain/course/Course.kt` dùng chunks 24 Kanji/30 từ/7 ngữ pháp theo thứ tự mỗi list, không lưu course lesson riêng. | Bỏ global lookup; tạo view bài tổng hợp, giữ source mapping và tiến độ item. Tách bookmark học liệu với user-created My Words. |
| Extension | MV3 Chrome, chỉ có capture đề PR5; host permission localhost cố định, token import. | Dictionary/selection/TTS/My Words cần module và credential phạm vi riêng; Firefox build riêng. Không dùng import token cho lưu từ. |
| PWA | Không thấy manifest/service worker hay install guide. | Cần manifest, icons, install và offline fallback an toàn. |
| Theme/i18n | Một bảng màu CSS, Next Themes package nhưng chưa có provider; text UI phần lớn hardcode tiếng Việt. | Themes + no-flash SSR và i18n vi/en/ja xuyên các màn. |
| Navigation | Dashboard đang gộp Analytics; Sổ lỗi sai là menu riêng; `/analytics/jlpt` redirect `/`. | Tách Overview và Analytics, chuyển Mistakes thành tab Analytics; giữ route cũ. |
| QR sync | Backend có one-time pairing code, `/sync/pair`, bearer credential, feed/push/revoke; Android `AndroidSyncClient.kt` chỉ nhập URL HTTPS + code bằng tay, chưa quét QR. | QR Web versioned payload + claim/confirm state machine mới, giữ API cũ, mock-client test; Android update ở phiên khác. Không dùng localhost trong QR. |
| Android sync dữ liệu học | Android pull Web mirrors và push review events. | Không có push Android progress/saved words/attempts; không thể gọi sync hai chiều cho các loại này. |

Chỉ import PDF sau khi rights assertion riêng cho hash file hiện tại được lưu với private scope. Không suy ra quyền phát hành công khai. Các bản ghi PDF, Web user words và Android Room là ba namespace khác nhau.

**Read-only recheck:** During Web V3 work the Android repository changed outside this task from HEAD `07f0d0b` (49 status entries at baseline) to `e194a44` (6 status entries), with two commits dated 2026-11-17 13:10 +07. The commits add Kanji N2 and Contrast Lab planning; a read-only diff of `domain/course/Course.kt` confirms N3 CoursePlan still uses 30/7/24 while excluding N2 Kanji from the N3 course. This Web task did not run any Android write/build/test command. The initial whole-repository hash cannot be expected to match after those concurrent changes.
