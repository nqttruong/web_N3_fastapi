"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { toast } from "sonner";

import { PageHeader } from "@/components/page-header";
import { ErrorState, LoadingState, errorMessage } from "@/components/states";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { api } from "@/lib/api/endpoints";

const COUNT_LABELS: Record<string, string> = {
  new_vocabulary: "Từ mới", changed_vocabulary: "Từ đã đổi", archived_vocabulary: "Từ lưu trữ",
  new_kanji: "Kanji mới", changed_kanji: "Kanji đã đổi", archived_kanji: "Kanji lưu trữ",
  new_grammar: "Ngữ pháp mới", changed_grammar: "Ngữ pháp đã đổi", archived_grammar: "Ngữ pháp lưu trữ",
  new_lessons: "Bài học mới", changed_lessons: "Bài học đã đổi", archived_lessons: "Bài học lưu trữ",
  license_blocked: "Mục bị chặn do quyền chưa xác minh",
};

function date(value: string | null | undefined) {
  return value ? new Date(value).toLocaleString("vi-VN") : "Chưa có";
}

export function LearningSyncSettingsView() {
  const queryClient = useQueryClient();
  const [token, setToken] = useState("");
  const status = useQuery({
    queryKey: ["learning-content-sync-status"],
    queryFn: api.learningContentStatus,
    refetchInterval: (query) => ["queued", "running"].includes(query.state.data?.last_run?.status ?? "") ? 4000 : false,
  });
  const sync = useMutation({
    mutationFn: () => api.requestLearningContentSync(token || undefined),
    onSuccess: (result) => {
      toast.success(result.message);
      queryClient.invalidateQueries({ queryKey: ["learning-content-sync-status"] });
    },
    onError: (error) => toast.error(errorMessage(error)),
  });

  return (
    <>
      <PageHeader title="Cài đặt đồng bộ bài học" description="Scanner chỉ đọc JSON content pack được Git track. Nó không chạy script Android, fetch remote hay đọc Room trên thiết bị." />
      {status.isPending ? <LoadingState rows={3} /> : status.error ? <ErrorState error={status.error} onRetry={() => status.refetch()} /> : (
        <div className="space-y-5">
          {!status.data.source_available ? <Alert><AlertDescription>Chưa truy cập được Android source. Cấu hình `ANDROID_LEARNING_SOURCE_DIR` trỏ tới Git root N3 Sensei rồi khởi động sync worker.</AlertDescription></Alert> : null}
          <Card>
            <CardHeader><CardTitle>Trạng thái nguồn</CardTitle></CardHeader>
            <CardContent className="grid gap-3 sm:grid-cols-2">
              <p><span className="text-muted-foreground">Nguồn:</span> {status.data.source_description}</p>
              <p><span className="text-muted-foreground">Quét định kỳ:</span> mỗi {status.data.interval_minutes} phút</p>
              <p><span className="text-muted-foreground">Lần kiểm tra gần nhất:</span> {date(status.data.last_checked_at)}</p>
              <p><span className="text-muted-foreground">Lần cập nhật thành công:</span> {date(status.data.last_success_at)}</p>
            </CardContent>
          </Card>
          <Card>
            <CardHeader><CardTitle>Phiên bản content pack hiện tại</CardTitle></CardHeader>
            <CardContent className="space-y-2">
              {status.data.current_versions.length === 0 ? <p className="text-sm text-muted-foreground">Chưa có pack được đồng bộ.</p> : status.data.current_versions.map((pack) => (
                <div key={pack.id} className="flex flex-wrap items-center gap-2 rounded-lg border p-3">
                  <span className="min-w-0 flex-1 font-medium">{pack.title}</span>
                  <Badge variant="secondary">{pack.jlpt_level} · v{pack.source_version}</Badge>
                  <span className="text-xs text-muted-foreground">{pack.active_item_count} mục · commit {pack.source_commit_sha?.slice(0, 8) ?? "—"}</span>
                  {pack.license_blocked_count > 0 ? <Badge variant="outline">{pack.license_blocked_count} mục bị chặn</Badge> : null}
                </div>
              ))}
            </CardContent>
          </Card>
          {status.data.last_run ? (
            <Card>
              <CardHeader><CardTitle>Lần kiểm tra gần nhất</CardTitle></CardHeader>
              <CardContent className="space-y-3">
                <div className="flex flex-wrap gap-2">
                  <Badge>{status.data.last_run.status}</Badge>
                  <span className="text-sm text-muted-foreground">Kích hoạt: {status.data.last_run.trigger} · bắt đầu {date(status.data.last_run.started_at)} · kết thúc {date(status.data.last_run.finished_at)}</span>
                </div>
                <div className="flex flex-wrap gap-2">
                  {Object.entries(status.data.last_run.counts).map(([key, value]) => value ? <Badge key={key} variant="outline">{COUNT_LABELS[key] ?? key}: {value}</Badge> : null)}
                </div>
                {status.data.last_run.error ? <Alert variant="destructive"><AlertDescription>{status.data.last_run.error}</AlertDescription></Alert> : null}
                {status.data.last_run.status === "queued" ? <p className="text-sm text-muted-foreground">Yêu cầu đang chờ worker. Khởi động `python -m app.learning_content.worker` nếu chưa chạy worker.</p> : null}
              </CardContent>
            </Card>
          ) : null}
          <Card>
            <CardHeader><CardTitle>Kiểm tra cập nhật bài học</CardTitle></CardHeader>
            <CardContent className="space-y-3">
              <p className="text-sm text-muted-foreground">Lệnh này chỉ xếp hàng tác vụ; import chạy trong worker riêng, có transaction, retry và audit. Các mục không có quyền phân phối được xác minh sẽ không xuất bản.</p>
              <Input type="password" autoComplete="new-password" value={token} onChange={(event) => setToken(event.target.value)} placeholder="Sync token (chỉ khi máy chủ yêu cầu)" aria-label="Learning sync token" className="max-w-lg" />
              <Button disabled={sync.isPending || !status.data.source_available} onClick={() => sync.mutate()}>
                {sync.isPending ? "Đang xếp hàng…" : "Kiểm tra cập nhật bài học"}
              </Button>
            </CardContent>
          </Card>
        </div>
      )}
    </>
  );
}
