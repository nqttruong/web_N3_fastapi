"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";

import { PageHeader } from "@/components/page-header";
import { EmptyState, ErrorState, LoadingState } from "@/components/states";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { api } from "@/lib/api/endpoints";
import { queryKeys } from "@/lib/api/keys";
import { formatPercent } from "@/lib/format";
import { knowledgeTypeLabels, priorityLabels } from "@/lib/labels";

const WINDOWS = [
  { value: "all", label: "Toàn bộ" },
  { value: "30d", label: "30 ngày" },
  { value: "7d", label: "7 ngày" },
];

export function KnowledgeView() {
  const [window, setWindow] = useState("30d");
  const knowledge = useQuery({
    queryKey: queryKeys.knowledgeList({ status: "active" }),
    queryFn: () => api.listKnowledge({ status: "active" }),
  });
  const report = useQuery({
    queryKey: queryKeys.weaknesses(window),
    queryFn: () => api.weaknesses(window),
  });

  return (
    <>
      <PageHeader
        title="Kho kiến thức"
        description="Tri thức được trích từ lời giải ChatGPT đã duyệt và còn hiện hành. Lịch sử câu sai được xem tại từng đề."
        actions={<Button asChild><Link href="/exams">Mở Kho đề</Link></Button>}
      />

      <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-lg font-semibold">Điểm yếu</h2>
        <label className="flex items-center gap-2 text-sm">
          <span>Khoảng thời gian</span>
          <select aria-label="Khoảng thời gian" className="h-8 rounded-md border bg-background px-2" value={window} onChange={(e) => setWindow(e.target.value)}>
            {WINDOWS.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}
          </select>
        </label>
      </div>
      {report.isPending ? <LoadingState rows={2} /> : report.error ? <ErrorState error={report.error} onRetry={() => report.refetch()} /> : (
        <div className="mb-8 grid gap-3 sm:grid-cols-2 lg:grid-cols-4" data-testid="weakness-summary">
          {Object.entries(report.data.categories).map(([category, stats]) => (
            <Card key={category}>
              <CardHeader><CardTitle className="capitalize">{category === "grammar" ? "Ngữ pháp" : category === "vocabulary" ? "Từ vựng" : category === "kanji" ? "Kanji" : "Đọc hiểu"}</CardTitle></CardHeader>
              <CardContent className="space-y-1">
                <p className="text-2xl font-semibold">{formatPercent(stats.error_rate)}</p>
                <p className="text-xs text-muted-foreground">Tỷ lệ sai · {stats.incorrect}/{stats.correct + stats.incorrect} câu đã chấm</p>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {report.data?.top_knowledge.length ? (
        <Card className="mb-8">
          <CardHeader><CardTitle>Kiến thức cần chú ý</CardTitle></CardHeader>
          <CardContent className="space-y-3">
            {report.data.top_knowledge.map((item) => (
              <div key={item.knowledge_id} className="flex flex-wrap items-center gap-2 rounded-lg border p-3">
                <Badge variant="secondary">{knowledgeTypeLabels[item.knowledge_type]}</Badge>
                <span lang="ja" className="font-medium">{item.title}</span>
                <span className="text-sm text-muted-foreground">{formatPercent(item.error_rate)} sai · {item.incorrect}/{item.correct + item.incorrect} câu</span>
                <Badge variant={item.priority === "review_now" ? "destructive" : "outline"} className="ml-auto">{priorityLabels[item.priority]}</Badge>
              </div>
            ))}
          </CardContent>
        </Card>
      ) : null}

      <h2 className="mb-3 text-lg font-semibold">Các mục đã xác nhận</h2>
      {knowledge.isPending ? <LoadingState rows={4} /> : knowledge.error ? <ErrorState error={knowledge.error} onRetry={() => knowledge.refetch()} /> : knowledge.data.length === 0 ? (
        <EmptyState title="Chưa có kiến thức được lưu" description="Duyệt lời giải trước, sau đó mở bài làm và chọn trích xuất kiến thức." />
      ) : (
        <div className="space-y-3" data-testid="knowledge-list">
          {knowledge.data.map((item) => (
            <Card key={item.id}>
              <CardContent className="flex flex-wrap items-start gap-2">
                <Badge variant="secondary">{knowledgeTypeLabels[item.knowledge_type]}</Badge>
                <div className="min-w-0 flex-1">
                  <p lang="ja" className="font-medium">{item.title}</p>
                  <p className="mt-1 text-sm text-muted-foreground">{item.content || "Chưa có mô tả"}</p>
                  <p className="mt-2 text-xs text-muted-foreground">{item.question_count} câu liên quan · {item.stats.incorrect} lần sai</p>
                </div>
                <Badge variant={item.stats.priority === "review_now" ? "destructive" : "outline"}>{priorityLabels[item.stats.priority]}</Badge>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </>
  );
}
