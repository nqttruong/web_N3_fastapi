"use client";

import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import QRCode from "qrcode";
import Image from "next/image";
import { apiRequest } from "@/lib/api/client";
import { errorMessage } from "@/components/states";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";

type Session = { id: string; status: string; device_name: string | null; device_id: string | null; expires_at: string; qr_payload?: { version: number; base_url: string; session_id: string; challenge: string; expires_at: string } };
const auth = (key: string): Record<string, string> => key ? { "X-Sync-Admin-Key": key } : {};
const STATUS_LABEL: Record<string, string> = {
  CREATED: "Đang tạo phiên",
  WAITING_FOR_DEVICE: "Đang chờ thiết bị quét QR",
  CLAIMED: "Thiết bị đã nhận mã — chờ xác nhận",
  AWAITING_CONFIRMATION: "Chờ bạn xác nhận mã trên Android",
  PAIRED: "Ghép nối thành công",
  EXPIRED: "Mã QR đã hết hạn",
  REJECTED: "Đã từ chối thiết bị",
  CANCELLED: "Đã hủy phiên ghép nối",
  FAILED: "Ghép nối thất bại",
};
const TERMINAL = ["PAIRED", "EXPIRED", "REJECTED", "CANCELLED", "FAILED"];

export function QRPairingPanel({ adminKey }: { adminKey: string }) {
  const client = useQueryClient();
  const [created, setCreated] = useState<Session | null>(null);
  const [image, setImage] = useState("");
  const [code, setCode] = useState("");
  const create = useMutation({ mutationFn: () => apiRequest<{ data: Session }>("/sync/admin/qr-sessions", { method: "POST", headers: auth(adminKey) }).then(r => r.data), onSuccess: setCreated });
  const current = useQuery({ queryKey: ["qr-session", created?.id, adminKey], enabled: !!created, queryFn: () => apiRequest<{ data: Session }>(`/sync/admin/qr-sessions/${created?.id}`, { headers: auth(adminKey) }).then(r => r.data), refetchInterval: query => TERMINAL.includes(query.state.data?.status || "") ? false : 3000 });
  const confirm = useMutation({ mutationFn: () => apiRequest<{ data: Session }>(`/sync/admin/qr-sessions/${created?.id}/confirm`, { method: "POST", headers: auth(adminKey), body: { confirmation_code: code } }).then(r => r.data), onSuccess: () => { void current.refetch(); void client.invalidateQueries({ queryKey: ["sync-admin-devices"] }); } });
  const cancel = useMutation({ mutationFn: () => apiRequest<{ data: Session }>(`/sync/admin/qr-sessions/${created?.id}/cancel`, { method: "POST", headers: auth(adminKey) }).then(r => r.data), onSuccess: () => void current.refetch() });
  const reject = useMutation({ mutationFn: () => apiRequest<{ data: Session }>(`/sync/admin/qr-sessions/${created?.id}/reject`, { method: "POST", headers: auth(adminKey) }).then(r => r.data), onSuccess: () => void current.refetch() });
  useEffect(() => { if (!created?.qr_payload) return; let active = true; void QRCode.toDataURL(JSON.stringify(created.qr_payload), { width: 256, margin: 2, errorCorrectionLevel: "M" }).then(url => { if (active) setImage(url); }); return () => { active = false; }; }, [created]);
  const status = current.data?.status ?? created?.status;
  return <Card><CardHeader><CardTitle>Ghép nối QR (giao thức Web v1)</CardTitle><CardDescription>Android N3 Sensei hiện chưa có trình quét QR. Màn này dùng để kiểm thử với mock client và chuẩn bị cho bản Android sau. QR chỉ chứa phiên ngắn hạn; cần xác nhận mã hiển thị trên thiết bị trước khi credential có hiệu lực.</CardDescription></CardHeader><CardContent className="space-y-4">
    <Button disabled={create.isPending} onClick={() => create.mutate()}>Tạo mã QR</Button>
    {create.error && <p role="alert" className="text-sm text-destructive">{errorMessage(create.error)}. Cấu hình SYNC_PUBLIC_HTTPS_BASE_URL trỏ tới HTTPS hostname được Android tin cậy.</p>}
    {created && <div className="space-y-3 rounded-lg border p-4"><p role="status" aria-live="polite" className="text-sm">Trạng thái: <strong>{STATUS_LABEL[status || ""] || "Đang kiểm tra"}</strong> · hết hạn {new Date(created.expires_at).toLocaleString("vi-VN")}</p>{created.qr_payload && image && <Image unoptimized src={image} alt="Mã QR ghép nối Android, có hiệu lực trong 5 phút" width={256} height={256} className="rounded-md border bg-white p-2" />}
      {current.data?.device_name && <p className="text-sm">Thiết bị yêu cầu: {current.data.device_name}. Hãy đối chiếu tên và mã trên thiết bị.</p>}
      {status === "AWAITING_CONFIRMATION" && <form className="flex flex-wrap gap-2" onSubmit={event => { event.preventDefault(); confirm.mutate(); }}><Input aria-label="Mã xác nhận trên Android" inputMode="numeric" pattern="[0-9]{6}" maxLength={6} placeholder="Mã 6 số trên thiết bị" value={code} onChange={event => setCode(event.target.value)} className="w-56" /><Button type="submit" disabled={confirm.isPending || !/^[0-9]{6}$/.test(code)}>Xác nhận ghép nối</Button></form>}
      {status === "PAIRED" && <p role="status" className="text-sm">Đã ghép nối. Thiết bị cần gọi bootstrap/pull/push để thực sự đồng bộ dữ liệu.</p>}
      {status === "EXPIRED" && <p role="alert" className="text-sm text-muted-foreground">Hãy tạo phiên QR mới để ghép nối.</p>}
      {status === "FAILED" && <p role="alert" className="text-sm text-muted-foreground">Phiên đã bị khóa sau nhiều lần xác nhận sai. Hãy tạo phiên mới.</p>}
      {(status === "REJECTED" || status === "CANCELLED") && <p role="status" className="text-sm text-muted-foreground">Phiên này không thể tiếp tục. Tạo QR mới nếu bạn muốn thử lại.</p>}
      {status && !["PAIRED", "EXPIRED", "REJECTED", "CANCELLED", "FAILED"].includes(status) && <Button variant="outline" disabled={cancel.isPending} onClick={() => cancel.mutate()}>Hủy phiên QR</Button>}
      {(status === "CLAIMED" || status === "AWAITING_CONFIRMATION") && <Button variant="destructive" disabled={reject.isPending} onClick={() => reject.mutate()}>Từ chối thiết bị</Button>}
      {(confirm.error || cancel.error || reject.error || current.error) && <p role="alert" className="text-sm text-destructive">{errorMessage(confirm.error || cancel.error || reject.error || current.error)}</p>}
    </div>}
  </CardContent></Card>;
}
