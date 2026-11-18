import Link from "next/link";

export default function OfflinePage() {
  return <main className="mx-auto max-w-lg space-y-4 p-8"><h1 className="text-2xl font-semibold">Bạn đang offline</h1><p>Trang này cần kết nối tới máy chủ JLPT AI Review để đọc dữ liệu cá nhân. Kết quả đã lưu trên máy chủ không bị thay đổi.</p><Link className="text-primary underline" href="/">Thử lại</Link></main>;
}
