"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { PageHeader } from "@/components/page-header";
import { ErrorState, LoadingState, errorMessage } from "@/components/states";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { studyApi, type SourceRight } from "./study-api";

export function RightsView() {
  const client = useQueryClient();
  const sources = useQuery({ queryKey: ["learning-source-rights"], queryFn: studyApi.sources });
  const [selected, setSelected] = useState<SourceRight | null>(null);
  const pdfPreview = useQuery({ queryKey: ["mimikara-pdf-preview", selected?.source_content_hash], enabled: !!selected?.source_content_hash, queryFn: studyApi.pdfPreview });
  const [holder, setHolder] = useState("");
  const [basis, setBasis] = useState("");
  const [usage, setUsage] = useState("");
  const [attribution, setAttribution] = useState("");
  const [approved, setApproved] = useState(false);
  const declaration = useMutation({ mutationFn: studyApi.declareRights, onSuccess: () => { void client.invalidateQueries({ queryKey: ["learning-source-rights"] }); void client.invalidateQueries({ queryKey: ["learning-content-sync-status"] }); } });
  function select(source: SourceRight) { setSelected(source); setHolder(source.declaration?.rights_holder ?? ""); setBasis(source.declaration?.rights_basis ?? ""); setUsage(source.declaration?.allowed_usage ?? "Sử dụng cá nhân trong JLPT AI Review Web"); setAttribution(source.declaration?.attribution ?? ""); setApproved(source.declaration?.approved ?? false); }
  return <div className="space-y-5"><PageHeader title="Quyền sử dụng nội dung" description="Khai báo theo từng source. Quyền dùng bản sao cá nhân không mặc nhiên là quyền phân phối công khai." />
    {sources.isPending ? <LoadingState rows={3} /> : sources.error ? <ErrorState error={sources.error} onRetry={() => void sources.refetch()} /> : <div className="grid gap-4 lg:grid-cols-2"><div className="max-h-[70vh] space-y-2 overflow-auto">{sources.data.filter(s => !s.license_verified || s.declaration).map(source => <button type="button" key={`${source.pack_id}:${source.source_id}`} className="w-full rounded-lg border p-3 text-left hover:bg-muted focus-visible:outline-2 focus-visible:outline-ring" onClick={() => select(source)}><span className="block font-medium">{source.source_name}</span><span className="block text-xs text-muted-foreground">{source.pack_id} · {source.source_id} · {source.declaration?.approved ? "Đã khai báo quyền riêng tư" : "Chưa phê duyệt"}</span></button>)}</div>
      <Card><CardHeader><CardTitle>{selected ? `Nguồn ${selected.source_id}` : "Chọn nguồn cần khai báo"}</CardTitle></CardHeader>{selected && <CardContent className="space-y-3"><p className="text-sm text-muted-foreground">Metadata nguồn: {selected.source_license}</p>{selected.source_content_hash && <><p className="break-all text-xs text-muted-foreground">PDF: {selected.row_count} mục · SHA-256 {selected.source_content_hash}. Xác nhận chỉ áp dụng cho đúng tệp này.</p>{pdfPreview.isPending ? <p className="text-sm">Đang đọc mẫu PDF…</p> : pdfPreview.error ? <p role="alert" className="text-sm text-destructive">Không đọc được mẫu PDF: {errorMessage(pdfPreview.error)}</p> : pdfPreview.data && <div className="max-h-64 overflow-auto rounded-md border p-2 text-xs"><p className="font-medium">Mẫu đầu, giữa, cuối PDF · {pdfPreview.data.row_count} mục</p>{pdfPreview.data.source_content_hash !== selected.source_content_hash && <p role="alert" className="text-destructive">Tệp PDF đã thay đổi; tải lại danh sách nguồn trước khi duyệt.</p>}{pdfPreview.data.samples.map(row => <p key={row.number} lang="ja" className="border-b py-1 last:border-0">#{row.number} · {row.expression} · {row.reading || "chưa có cách đọc"} · {row.meaning_vi} · trang {row.source_page}</p>)}</div>}</>}<label className="block text-sm">Chủ quyền / bên cấp phép<Input value={holder} onChange={e => setHolder(e.target.value)} /></label><label className="block text-sm">Căn cứ quyền sử dụng<Input value={basis} onChange={e => setBasis(e.target.value)} /></label><label className="block text-sm">Phạm vi sử dụng được phép<Input value={usage} onChange={e => setUsage(e.target.value)} /></label><label className="block text-sm">Yêu cầu ghi nguồn<Input value={attribution} onChange={e => setAttribution(e.target.value)} /></label><label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={approved} onChange={e => setApproved(e.target.checked)} />Tôi xác nhận có căn cứ phù hợp để nhập source này cho ứng dụng cá nhân</label><Button disabled={declaration.isPending || holder.trim().length < 2 || basis.trim().length < 10 || usage.trim().length < 10 || !!(selected.source_content_hash && (!pdfPreview.data || pdfPreview.data.source_content_hash !== selected.source_content_hash))} onClick={() => declaration.mutate({ pack_id: selected.pack_id, source_id: selected.source_id, rights_holder: holder, rights_basis: basis, allowed_usage: usage, attribution: attribution || null, scope: "private", approved, source_content_hash: selected.source_content_hash })}>Lưu khai báo và xếp hàng kiểm tra nội dung</Button>{declaration.isSuccess && <p role="status" className="text-sm">Đã lưu. Worker sẽ kiểm tra source và cập nhật nội dung đủ điều kiện.</p>}{declaration.error && <p role="alert" className="text-sm text-destructive">{errorMessage(declaration.error)}</p>}</CardContent>}</Card>
    </div>}
  </div>;
}
