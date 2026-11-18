"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiRequest } from "@/lib/api/client";
import { errorMessage } from "@/components/states";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";

type Credential = { id: string; label: string; created_at: string; revoked_at: string | null };
const headers = (key: string): Record<string, string> => key ? { "X-Sync-Admin-Key": key } : {};

export function ExtensionCredentialPanel({ adminKey }: { adminKey: string }) {
  const client = useQueryClient();
  const [label, setLabel] = useState("Trình duyệt cá nhân");
  const [token, setToken] = useState("");
  const list = useQuery({ queryKey: ["my-word-credentials", adminKey], queryFn: () => apiRequest<{ data: Credential[] }>("/my-words/credentials", { headers: headers(adminKey) }).then(r => r.data), retry: false });
  const create = useMutation({ mutationFn: () => apiRequest<{ data: { id: string; token: string } }>("/my-words/credentials", { method: "POST", headers: headers(adminKey), body: { label } }).then(r => r.data), onSuccess: data => { setToken(data.token); void client.invalidateQueries({ queryKey: ["my-word-credentials"] }); } });
  const revoke = useMutation({ mutationFn: (id: string) => apiRequest(`/my-words/credentials/${id}/revoke`, { method: "POST", headers: headers(adminKey) }), onSuccess: () => void client.invalidateQueries({ queryKey: ["my-word-credentials"] }) });
  return <Card><CardHeader><CardTitle>Credential tiện ích Từ của tôi</CardTitle><CardDescription>Token này chỉ lưu từ qua endpoint riêng; không dùng token nhập đề, Android hoặc ChatGPT. Web chỉ hiển thị một lần khi tạo.</CardDescription></CardHeader><CardContent className="space-y-3"><div className="flex flex-wrap gap-2"><Input aria-label="Tên trình duyệt" className="w-64" value={label} onChange={event => setLabel(event.target.value)} /><Button disabled={create.isPending || !label.trim()} onClick={() => create.mutate()}>Tạo credential</Button></div>
    {token && <div className="rounded-md border p-3"><p className="mb-1 text-sm">Sao chép vào Cài đặt extension → Credential Từ của tôi. Sau khi rời trang, Web không hiện lại token.</p><code className="block break-all text-xs">{token}</code><Button className="mt-2" size="sm" variant="outline" onClick={() => void navigator.clipboard.writeText(token)}>Sao chép</Button></div>}
    {list.data?.map(row => <div className="flex flex-wrap items-center justify-between gap-2 rounded-md border p-2 text-sm" key={row.id}><span>{row.label} · {row.revoked_at ? "Đã thu hồi" : "Đang hoạt động"}</span>{!row.revoked_at && <Button size="sm" variant="outline" disabled={revoke.isPending} onClick={() => revoke.mutate(row.id)}>Thu hồi</Button>}</div>)}
    {(list.error || create.error || revoke.error) && <p role="alert" className="text-sm text-destructive">{errorMessage(list.error || create.error || revoke.error)}</p>}
  </CardContent></Card>;
}
