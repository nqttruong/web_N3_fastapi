"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";

import { PageHeader } from "@/components/page-header";
import { JapaneseText } from "@/components/japanese-text";
import { EmptyState, ErrorState, LoadingState } from "@/components/states";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { api } from "@/lib/api/endpoints";
import { useLocale } from "@/lib/i18n";

const TYPES = [
  { id: "vocabulary", label: "Từ vựng" },
  { id: "kanji", label: "Kanji" },
  { id: "grammar", label: "Ngữ pháp" },
];

function itemTitle(item: { item_type: string; payload: Record<string, unknown> }) {
  const key = item.item_type === "vocabulary" ? "expression" : item.item_type === "kanji" ? "character" : "pattern";
  return String(item.payload[key] ?? "");
}

export function LearningContentView({ embedded = false }: { embedded?: boolean }) {
  const { t } = useLocale();
  const [type, setType] = useState("");
  const [q, setQ] = useState("");
  const [page, setPage] = useState(1);
  const items = useQuery({
    queryKey: ["learning-content", type, q, page],
    queryFn: () => api.listLearningContent({ type: type || undefined, q: q || undefined, page, page_size: 60 }),
  });
  const status = useQuery({ queryKey: ["learning-content-sync-status"], queryFn: api.learningContentStatus });

  return (
    <>
      {!embedded && <PageHeader
        title="Học tập"
        description="Từ vựng, Kanji và ngữ pháp từ những content pack Android có nguồn được xác minh. Tiến độ học trên thiết bị không được nhập cùng nội dung."
        actions={<Button variant="outline" onClick={() => status.refetch()}>Làm mới trạng thái</Button>}
      />}
      {status.data ? (
        <div className="mb-5 flex flex-wrap gap-2" aria-label="Số nội dung đã đồng bộ">
          <Badge variant="secondary">Từ vựng {status.data.active_counts.vocabulary ?? 0}</Badge>
          <Badge variant="secondary">Kanji {status.data.active_counts.kanji ?? 0}</Badge>
          <Badge variant="secondary">Ngữ pháp {status.data.active_counts.grammar ?? 0}</Badge>
          <span className="self-center text-xs text-muted-foreground">
            {status.data.last_success_at ? `Cập nhật ${new Date(status.data.last_success_at).toLocaleString("vi-VN")}` : "Chưa đồng bộ nội dung"}
          </span>
        </div>
      ) : null}
      <div className="mb-4 flex flex-wrap items-center gap-2">
        <Button asChild variant="outline"><Link href="/learning#composite-lessons">{t("compositeCourse")}</Link></Button>
        {TYPES.map((option) => (
          <Button key={option.id} variant={type === option.id ? "default" : "outline"} onClick={() => { setType(option.id); setPage(1); }}>
            {option.label}
          </Button>
        ))}
        <Input className="ml-auto w-full sm:max-w-xs" value={q} onChange={(event) => { setQ(event.target.value); setPage(1); }} placeholder="Tìm từ, Kanji, mẫu ngữ pháp…" aria-label="Tìm nội dung học" />
      </div>
      {items.isPending ? <LoadingState rows={5} /> : items.error ? <ErrorState error={items.error} onRetry={() => items.refetch()} /> : items.data.items.length === 0 ? (
        <EmptyState
          title="Chưa có nội dung học được cấp phép để hiển thị"
          description="Kiểm tra trạng thái đồng bộ trong Cài đặt. Nội dung có quyền phân phối chưa xác minh sẽ không được đưa lên Web."
        />
      ) : (
        <div className="space-y-3" data-testid="learning-content-list">
          {items.data.items.map((item) => (
            <Card key={item.stable_source_id}>
              <CardHeader className="pb-2">
                <div className="flex flex-wrap items-start gap-2">
                  <CardTitle lang="ja" className="min-w-0 flex-1">{itemTitle(item)}</CardTitle>
                  <Badge variant="secondary">{item.jlpt_level}</Badge>
                  <Badge variant="outline">Bài {item.lesson_number}</Badge>
                </div>
              </CardHeader>
              <CardContent className="space-y-2">
                {item.item_type === "vocabulary" ? (
                  <>
                    <p lang="ja" className="text-sm text-muted-foreground">{String(item.payload.furigana ?? item.payload.reading ?? "")}</p>
                    <p>{String(item.payload.meaningVi ?? "")}</p>
                    {item.payload.partOfSpeech ? <p className="text-sm text-muted-foreground">{String(item.payload.partOfSpeech)}</p> : null}
                  </>
                ) : item.item_type === "kanji" ? (
                  <>
                    <p>{String(item.payload.meaningVi ?? "")}{item.payload.hanViet ? ` · ${String(item.payload.hanViet)}` : ""}</p>
                    <p lang="ja" className="text-sm text-muted-foreground">On: {Array.isArray(item.payload.onReadings) ? item.payload.onReadings.join("、") : "—"} · Kun: {Array.isArray(item.payload.kunReadings) ? item.payload.kunReadings.join("、") : "—"}</p>
                  </>
                ) : (
                  <>
                    <p>{String(item.payload.meaningVi ?? "")}</p>
                    {item.payload.structure ? <p lang="ja" className="text-sm text-muted-foreground">{String(item.payload.structure)}</p> : null}
                    {item.payload.usage ? <p className="text-sm">{String(item.payload.usage)}</p> : null}
                  </>
                )}
                {item.examples.map((example, index) => (
                  <div key={`${item.id}-example-${index}`} className="rounded-lg bg-muted/40 p-3">
                    <p className="font-medium"><JapaneseText value={example.furigana || example.japanese} /></p>
                    {example.translationVi ? <p className="mt-1 text-sm text-muted-foreground">{example.translationVi}</p> : null}
                  </div>
                ))}
                <p className="pt-1 text-xs text-muted-foreground">{item.lesson_title} · phiên bản {item.source_version} · {item.source_name}</p>
              </CardContent>
            </Card>
          ))}
          <div className="flex items-center justify-center gap-3 py-2 text-sm"><Button variant="outline" disabled={page === 1} onClick={() => setPage(page - 1)}>Trang trước</Button><span>Trang {page} · {items.data.total} mục</span><Button variant="outline" disabled={page * 60 >= items.data.total} onClick={() => setPage(page + 1)}>Trang sau</Button></div>
        </div>
      )}
    </>
  );
}
