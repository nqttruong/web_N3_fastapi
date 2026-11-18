import { LearningSyncSettingsView } from "@/features/learning-content/learning-sync-settings-view";
import { ThemeSelector } from "@/features/settings/theme-selector";
import Link from "next/link";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";

export default function SettingsPage() {
  return (
    <>
      <div className="mb-5"><ThemeSelector /></div>
      <Card className="mb-5">
        <CardContent className="flex flex-wrap items-center justify-between gap-3 pt-4">
          <div>
            <h2 className="font-medium">N3 Sensei · ghép nối thiết bị</h2>
            <p className="text-sm text-muted-foreground">Tạo mã một lần, xem pull/push và thu hồi credential.</p>
          </div>
          <Button asChild variant="outline"><Link href="/settings/sync">Quản lý đồng bộ Android</Link></Button>
        </CardContent>
      </Card>
      <Card className="mb-5"><CardContent className="flex flex-wrap items-center justify-between gap-3 pt-4"><div><h2 className="font-medium">Quyền sử dụng nội dung học</h2><p className="text-sm text-muted-foreground">Khai báo riêng từng nguồn, kiểm tra mục còn bị chặn.</p></div><Button asChild variant="outline"><Link href="/settings/rights">Quản lý quyền nội dung</Link></Button></CardContent></Card>
      <Card className="mb-5"><CardContent className="flex flex-wrap items-center justify-between gap-3 pt-4"><div><h2 className="font-medium">Hướng dẫn sử dụng</h2><p className="text-sm text-muted-foreground">Học bài, flashcard, thi thử và đồng bộ.</p></div><Button asChild variant="outline"><Link href="/help">Mở hướng dẫn</Link></Button></CardContent></Card>
      <LearningSyncSettingsView />
    </>
  );
}
