import Link from "next/link";

import { PageHeader } from "@/components/page-header";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

const guides = [
  { title: "Bắt đầu học N3", href: "/learning", text: "Mở Học tập, chọn Bài học tổng hợp hoặc từng mục Từ vựng, Kanji, Ngữ pháp. Nội dung và ví dụ chỉ xuất hiện khi nguồn đã được phép nhập. Bài tổng hợp có tối đa 30 từ, 7 ngữ pháp và 24 Kanji, theo thứ tự nguồn." },
  { title: "Flashcard và ôn bài", href: "/learning", text: "Trong bài học chọn Học bằng flashcard. Nhấn Space để lật; sau đó nhấn 1/2/3/4 hoặc chọn Quên, Khó, Tốt, Dễ. Kết quả được lưu trên Web sau mỗi thẻ. Quay lại phiên đang học từ nút Tiếp tục học. Đến hạn ôn xuất hiện ở Học tập." },
  { title: "Nội dung đã lưu", href: "/learning/saved", text: "Lưu từ vựng, Kanji và ngữ pháp của bài học để xem lại. Đây là bookmark học liệu, tách khỏi kho Từ của tôi do bạn tự thêm." },
  { title: "Từ của tôi", href: "/learning/my-words", text: "Thêm từ thủ công cùng ngôn ngữ, nhiều nghĩa, cách đọc hoặc IPA nếu bạn biết. Có thể tìm kiếm, sửa, bỏ lưu, lật thẻ, nghe bằng giọng của trình duyệt và ôn lại." },
  { title: "Extension tra từ", href: "/settings/sync", text: "Nạp bản dist cho Chrome/Edge hoặc dist-firefox cho Firefox. Tạo credential Từ của tôi ở Cài đặt đồng bộ rồi dán vào Options. Bật helper riêng cho website, bôi đen tối đa 200 ký tự và nhấn biểu tượng 訳 hoặc menu chuột phải. Nghĩa/cách đọc xác minh chỉ có cho mục Nhật khớp chính xác nguồn học đã duyệt; có thể sửa trước khi lưu. Khi offline, extension giữ bản nháp và chỉ retry khi kiểm tra kết nối." },
  { title: "Enable Text Selection và nghe", href: "/learning/my-words", text: "Tùy chọn chọn văn bản mặc định tắt; bật theo từng site được phép và tắt để khôi phục CSS. Không hoạt động trên trang nội bộ trình duyệt hoặc nội dung có kiểm soát truy cập. Nút loa cần voice phù hợp trên trình duyệt; không có voice thì không phát." },
  { title: "Theme, ngôn ngữ và PWA", href: "/settings", text: "Trong Cài đặt chọn 5 bảng màu và sáng/tối/theo hệ thống; đổi vi/en/ja ở Header. Bản dịch giao diện hiện chưa bao phủ mọi trang. PWA có manifest và fallback offline, không cache dữ liệu cá nhân." },
  { title: "Thi thử và lịch sử", href: "/exams", text: "Chọn đề trong Kho đề, mở chi tiết rồi Làm bài. Sau khi nộp, xem kết quả và lịch sử các lần làm ngay trong chi tiết đề." },
  { title: "Nhập đề", href: "/exams?tab=drafts", text: "Tại Kho đề chọn Thêm đề; có thể tạo thủ công, dán text/HTML, dùng ảnh OCR hoặc Chrome Extension. Kiểm tra draft và xác nhận đáp án trước khi lưu." },
  { title: "Phân tích và Sổ lỗi sai", href: "/analytics/jlpt?tab=mistakes", text: "Phân tích JLPT có tab Thống kê và Sổ lỗi sai. Sổ chỉ lấy các câu đã được chấm sai; câu chưa chấm và câu bỏ trống được giữ riêng." },
  { title: "Chữa bài bằng ChatGPT", href: "/exams", text: "Từ chi tiết đề mở attempt, chọn Chữa bằng ChatGPT. Sao chép prompt, mở ChatGPT thủ công, dán JSON lời giải trở lại Web, kiểm tra và duyệt trước khi lưu." },
  { title: "Đồng bộ Android và QR", href: "/settings/sync", text: "Android hiện dùng mã ghép nối thủ công qua HTTPS có chứng chỉ được tin cậy. Web đã có QR protocol và mock test, nhưng app Android gốc chưa quét QR. Pairing không đồng nghĩa dữ liệu đã pull/push. Android chưa upload tiến độ học hoặc lịch sử thi local." },
  { title: "Khi nội dung chưa xuất hiện", href: "/settings/rights", text: "Kiểm tra trạng thái sync worker và quyền từng nguồn trong Cài đặt. PDF đổi nội dung cần kiểm tra và duyệt SHA-256 mới. Nguồn chưa đủ căn cứ quyền bị chặn; nội dung đã duyệt cần worker xử lý hàng đợi." },
];

export default function HelpPage() {
  return <div className="space-y-6"><PageHeader title="Hướng dẫn sử dụng" description="Các thao tác đang hoạt động trong JLPT AI Review Web." /><div className="grid gap-4 md:grid-cols-2">{guides.map(guide => <Card key={guide.title}><CardHeader><CardTitle>{guide.title}</CardTitle></CardHeader><CardContent className="space-y-3"><p className="text-sm leading-relaxed text-muted-foreground">{guide.text}</p><Link className="font-medium text-primary underline-offset-4 hover:underline" href={guide.href}>Mở chức năng →</Link></CardContent></Card>)}</div></div>;
}
