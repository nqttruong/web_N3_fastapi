"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import Link from "next/link";
import { toast } from "sonner";

import { PageHeader } from "@/components/page-header";
import { ErrorState, errorMessage } from "@/components/states";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { api } from "@/lib/api/endpoints";
import type { SyncAdminDevice } from "@/lib/api/types";
import { QRPairingPanel } from "./qr-pairing-panel";
import { ExtensionCredentialPanel } from "./extension-credential-panel";

function date(value: string | null) {
  return value ? new Date(value).toLocaleString("vi-VN") : "Chưa ghi nhận";
}

function activity(device: SyncAdminDevice) {
  if (device.revoked_at) return <Badge variant="destructive">Đã thu hồi</Badge>;
  return <Badge variant="secondary">Đã ghép nối</Badge>;
}

export function SyncManagementView() {
  const client = useQueryClient();
  const [adminKey, setAdminKey] = useState("");
  const [pairingCode, setPairingCode] = useState<{ value: string; expiresAt: string } | null>(null);
  const devices = useQuery({
    queryKey: ["sync-admin-devices"],
    queryFn: () => api.listSyncDevices(adminKey || undefined),
    retry: false,
  });
  const createCode = useMutation({
    mutationFn: () => api.createSyncPairingCode(adminKey),
    onSuccess: (result) => {
      setPairingCode({ value: result.pairing_code, expiresAt: result.expires_at });
      toast.success("Đã tạo mã ghép nối. Thiết bị chưa được ghép nối cho đến khi nhập mã trong Android.");
      void client.invalidateQueries({ queryKey: ["sync-admin-devices"] });
    },
    onError: (error) => toast.error(errorMessage(error)),
  });
  const revoke = useMutation({
    mutationFn: (id: string) => api.revokeSyncDevice(id, adminKey || undefined),
    onSuccess: () => {
      toast.success("Đã thu hồi credential thiết bị.");
      void client.invalidateQueries({ queryKey: ["sync-admin-devices"] });
    },
    onError: (error) => toast.error(errorMessage(error)),
  });

  return (
    <>
      <PageHeader
        title="Đồng bộ Android"
        description="Ghép nối thiết bị vào một hồ sơ học tập cá nhân. Không cần email, mật khẩu hay tài khoản."
        actions={<Button asChild variant="outline"><Link href="/settings">Cài đặt nội dung</Link></Button>}
      />

      <div className="space-y-5">
        <Alert>
          <AlertDescription>
            Mã ghép nối chỉ dùng một lần, hết hạn sau 10 phút và thay mã cũ chưa dùng. Tạo mã không đồng bộ dữ liệu.
            Android chỉ kết nối HTTPS với chứng chỉ được hệ thống Android tin cậy.
          </AlertDescription>
        </Alert>

        <Card>
          <CardHeader>
            <CardTitle>Quản trị đồng bộ</CardTitle>
            <CardDescription>
              Trên máy local development, API chỉ cho phép máy chủ local. Nếu đã cấu hình SYNC_ADMIN_KEY, nhập khóa tại đây; khóa chỉ giữ trong bộ nhớ trang.
            </CardDescription>
          </CardHeader>
          <CardContent className="flex flex-col gap-3 sm:flex-row">
            <Input
              type="password"
              autoComplete="off"
              aria-label="Khóa quản trị đồng bộ"
              placeholder="SYNC_ADMIN_KEY (nếu máy chủ yêu cầu)"
              value={adminKey}
              onChange={(event) => setAdminKey(event.target.value)}
              className="max-w-lg"
            />
            <Button variant="outline" disabled={devices.isFetching} onClick={() => void devices.refetch()}>
              Tải danh sách thiết bị
            </Button>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Mã ghép nối Android</CardTitle>
            <CardDescription>
              Trong N3 Sensei mở Cài đặt → Đồng bộ JLPT AI Review, nhập URL HTTPS và mã này.
              Pairing thành công chỉ tạo device credential; cần bấm Đồng bộ ngay trong Android để pull/push dữ liệu.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            <Button disabled={createCode.isPending} onClick={() => createCode.mutate()}>
              {createCode.isPending ? "Đang tạo mã…" : "Tạo mã ghép nối"}
            </Button>
            {pairingCode ? (
              <div className="rounded-lg border bg-muted/30 p-4" data-testid="pairing-code-result">
                <div className="mb-2 flex flex-wrap items-center gap-2">
                  <Badge variant="outline">Đã tạo · chưa ghép nối</Badge>
                  <span className="text-sm text-muted-foreground">Hết hạn {date(pairingCode.expiresAt)}</span>
                </div>
                <code className="block break-all text-lg font-semibold" aria-label="Mã ghép nối">{pairingCode.value}</code>
                <Button
                  className="mt-3"
                  variant="outline"
                  onClick={() => void navigator.clipboard.writeText(pairingCode.value).then(() => toast.success("Đã sao chép mã."), () => toast.error("Không thể truy cập clipboard."))}
                >
                  Sao chép mã
                </Button>
              </div>
            ) : null}
          </CardContent>
        </Card>

        <QRPairingPanel adminKey={adminKey} />
        <ExtensionCredentialPanel adminKey={adminKey} />

        <Card>
          <CardHeader>
            <CardTitle>Thiết bị đã ghép nối</CardTitle>
            <CardDescription>
              “Đã ghép nối” không có nghĩa là thiết bị đang online hay đồng bộ hoàn tất. Backend chỉ hiển thị lần API, pull và push mà nó thực sự nhận được.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {devices.isPending ? <p role="status">Đang tải thiết bị…</p> : null}
            {devices.error ? <ErrorState error={devices.error} onRetry={() => void devices.refetch()} /> : null}
            {devices.data?.length === 0 ? <p className="text-sm text-muted-foreground">Chưa có thiết bị ghép nối. Tạo mã ở trên; trạng thái chỉ đổi sau khi Android ghép nối.</p> : null}
            {devices.data?.map((device) => (
              <div key={device.device_id} className="rounded-lg border p-4" data-testid="paired-device">
                <div className="flex flex-wrap items-center gap-2">
                  <h2 className="font-medium">{device.device_name}</h2>
                  {activity(device)}
                  <span className="text-xs text-muted-foreground">ID {device.device_id}</span>
                </div>
                <dl className="mt-3 grid gap-2 text-sm sm:grid-cols-2">
                  <div><dt className="text-muted-foreground">Ghép nối lúc</dt><dd>{date(device.paired_at)}</dd></div>
                  <div><dt className="text-muted-foreground">Request thiết bị gần nhất</dt><dd>{date(device.last_seen_at)}</dd></div>
                  <div><dt className="text-muted-foreground">Pull gần nhất</dt><dd>{date(device.last_pull_at)}</dd></div>
                  <div><dt className="text-muted-foreground">Push review event gần nhất</dt><dd>{date(device.last_push_at)}</dd></div>
                </dl>
                {!device.revoked_at ? (
                  <Button className="mt-3" variant="destructive" disabled={revoke.isPending} onClick={() => revoke.mutate(device.device_id)}>
                    Thu hồi thiết bị
                  </Button>
                ) : <p className="mt-3 text-sm text-muted-foreground">Đã thu hồi lúc {date(device.revoked_at)}.</p>}
              </div>
            ))}
          </CardContent>
        </Card>

        <Card>
          <CardHeader><CardTitle>Phạm vi dữ liệu</CardTitle></CardHeader>
          <CardContent className="grid gap-4 sm:grid-cols-2">
            <section>
              <h2 className="font-medium">Web → Android (pull)</h2>
              <p className="text-sm text-muted-foreground">Đề, passage, câu hỏi/đáp án verified, lời giải approved/current, attempt và answer mirror, knowledge item và metadata review item. Dữ liệu nằm trong các bảng `synced_*` riêng của Android.</p>
            </section>
            <section>
              <h2 className="font-medium">Android → Web (push)</h2>
              <p className="text-sm text-muted-foreground">Review events append-only (lịch sử review hiện có và JLPT offline review events), chống trùng bằng request ID. Đây không phải snapshot learning progress.</p>
            </section>
            <section>
              <h2 className="font-medium">Chưa đồng bộ từ Android</h2>
              <p className="text-sm text-muted-foreground">Room learning progress/SRS state, user saved words, exam attempts/answers do Android tạo, mistake notebook và analytics. Android client hiện chưa upload các entity này.</p>
            </section>
            <section>
              <h2 className="font-medium">Nguồn nội dung học</h2>
              <p className="text-sm text-muted-foreground">Content pack Git-tracked Android → Web là worker riêng. Nó không phải pull/push của thiết bị và không chuyển tiến độ.</p>
            </section>
          </CardContent>
        </Card>
      </div>
    </>
  );
}
