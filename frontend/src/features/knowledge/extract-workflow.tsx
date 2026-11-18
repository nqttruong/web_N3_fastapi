"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";

import { PageHeader } from "@/components/page-header";
import { EmptyState, ErrorState, LoadingState, errorMessage } from "@/components/states";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { api } from "@/lib/api/endpoints";
import { queryKeys } from "@/lib/api/keys";
import type { ConfirmItemInput, ConfirmResult, KnowledgeCandidate, KnowledgeRole } from "@/lib/api/types";
import { knowledgeTypeLabels, roleLabels } from "@/lib/labels";

type Action = ConfirmItemInput["action"];

interface Draft {
  candidate: KnowledgeCandidate;
  title: string;
  summary: string;
  role: KnowledgeRole;
  action: Action;
  skill: string | null;
}

const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

function initialAction(c: KnowledgeCandidate): Action {
  if (!c.selected) return "skip";
  if (c.action === "link") return "link";
  if (c.action === "needs_decision") return "skip"; // never merge ambiguous items silently
  return "create";
}

const actionLabels: Record<Action, string> = {
  create: "Tạo mục mới",
  link: "Gộp vào mục đã có",
  create_new_sense: "Tạo nghĩa/chức năng riêng",
  skip: "Bỏ qua",
};

export function ExtractWorkflow() {
  const params = useSearchParams();
  const attemptId = params.get("attempt");
  const questionIds = (params.get("q") ?? "").split(",").filter((s) => UUID_RE.test(s));
  const queryClient = useQueryClient();
  const [drafts, setDrafts] = useState<Record<string, Draft> | null>(null);
  const [relations, setRelations] = useState<Record<string, boolean>>({});
  const [result, setResult] = useState<ConfirmResult | null>(null);

  const enabled = !!attemptId || questionIds.length > 0;
  const extraction = useQuery({
    queryKey: ["knowledge", "extract", attemptId, questionIds.join(",")],
    queryFn: () => api.extractKnowledge(attemptId ? { attempt_id: attemptId } : { question_ids: questionIds }),
    enabled,
    staleTime: Infinity,
  });

  const data = extraction.data;
  if (data && drafts === null) {
    const next: Record<string, Draft> = {};
    const rel: Record<string, boolean> = {};
    for (const q of data.questions) {
      for (const c of q.candidates) {
        next[c.ref] = {
          candidate: c,
          title: c.title,
          summary: c.summary,
          role: c.role,
          action: initialAction(c),
          skill: (c.details.skill as string | null) ?? null,
        };
      }
      for (const r of q.relations) rel[`${r.source_ref}>${r.target_ref}`] = true;
    }
    setDrafts(next);
    setRelations(rel);
  }

  const confirm = useMutation({
    mutationFn: () => {
      const items: ConfirmItemInput[] = Object.values(drafts ?? {}).map((d) => {
        const c = d.candidate;
        const details = c.knowledge_type === "reading_skill" ? { ...c.details, skill: d.skill } : c.details;
        return {
          ref: c.ref,
          question_id: c.question_id,
          explanation_id: c.explanation_id,
          knowledge_type: c.knowledge_type,
          title: c.knowledge_type === "reading_skill" && d.skill ? data!.reading_skills[d.skill]! : d.title,
          summary: d.summary,
          details,
          role: d.role,
          action: d.action,
          ...(d.action === "link" ? { target_knowledge_id: c.match?.knowledge_id } : {}),
        };
      });
      const rels = Object.entries(relations)
        .filter(([, on]) => on)
        .map(([k]) => {
          const [source_ref, target_ref] = k.split(">");
          return { source_ref: source_ref!, target_ref: target_ref!, relation_type: "confused_with" };
        });
      return api.confirmKnowledge({ items, relations: rels, create_reviews: true });
    },
    onSuccess: (r) => {
      setResult(r);
      for (const key of [queryKeys.knowledgeRoot, queryKeys.reviewsRoot]) queryClient.invalidateQueries({ queryKey: key });
      toast.success(`Đã lưu: ${r.created} mục mới, ${r.linked} mục gộp vào mục đã có.`);
    },
    onError: (e) => toast.error(errorMessage(e)),
  });

  if (!enabled) return <EmptyState title="Chưa chọn câu hỏi" description="Mở một bài làm và chọn “Trích xuất kiến thức”." />;
  if (extraction.isPending) return <LoadingState rows={5} />;
  if (extraction.error) return <ErrorState error={extraction.error} onRetry={() => extraction.refetch()} />;
  if (!data || !drafts) return <LoadingState rows={3} />;

  const update = (ref: string, patch: Partial<Draft>) => setDrafts({ ...drafts, [ref]: { ...drafts[ref]!, ...patch } });
  const chosen = Object.values(drafts).filter((d) => d.action !== "skip");
  const missingSkill = chosen.some((d) => d.candidate.knowledge_type === "reading_skill" && !d.skill);
  const usable = data.questions.filter((q) => !q.skipped_code);

  return (
    <>
      <PageHeader
        title="Trích xuất kiến thức"
        description="Chỉ dùng lời giải AI đã được bạn xác nhận và còn hiện hành. Xem lại, sửa nhãn rồi xác nhận — không có gì được lưu trước bước này."
        actions={
          attemptId ? (
            <Button asChild variant="outline">
              <Link href={`/attempts/${attemptId}`}>Về bài làm</Link>
            </Button>
          ) : undefined
        }
      />

      {result ? (
        <Alert className="mb-6">
          <AlertTitle>Đã lưu vào kho kiến thức</AlertTitle>
          <AlertDescription>
            <p>
              {result.created} mục mới · {result.linked} mục gộp vào mục đã có · {result.skipped} bỏ qua · {result.relations_created} quan hệ dễ nhầm.
            </p>
            <div className="mt-2 flex gap-2">
              <Button asChild size="sm" variant="outline">
                <Link href="/knowledge">Kho kiến thức</Link>
              </Button>
            </div>
          </AlertDescription>
        </Alert>
      ) : null}

      <div className="space-y-4">
        {data.questions.map((q) => (
          <Card key={q.question_id} data-testid="extract-question">
            <CardHeader>
              <CardTitle className="flex flex-wrap items-center gap-2 text-base">
                Câu {q.question_number}
                {q.skipped_code ? <Badge variant="outline">Bỏ qua</Badge> : <Badge variant="secondary">{q.candidates.length} gợi ý</Badge>}
                <Link className="text-xs font-normal underline" href={`/questions/${q.question_id}/explanation`}>
                  Lời giải
                </Link>
              </CardTitle>
              {q.skipped_code ? <CardDescription>{q.skipped_message}</CardDescription> : null}
            </CardHeader>
            {q.candidates.length ? (
              <CardContent className="space-y-3">
                {q.candidates.map((c) => {
                  const d = drafts[c.ref]!;
                  const actions: Action[] = ["create", ...(c.match ? (["link", "create_new_sense"] as Action[]) : []), "skip"];
                  return (
                    <div key={c.ref} className="space-y-2 rounded-lg border p-3 text-sm" data-testid="candidate">
                      <div className="flex flex-wrap items-center gap-2">
                        <Badge variant="secondary">{knowledgeTypeLabels[c.knowledge_type]}</Badge>
                        <code className="text-xs text-muted-foreground">{c.canonical_key}</code>
                        {c.action === "needs_decision" ? (
                          <Badge variant="outline" className="border-amber-500/60 text-amber-700 dark:text-amber-400">
                            Cần bạn quyết định
                          </Badge>
                        ) : null}
                      </div>
                      <div className="grid gap-2 md:grid-cols-[minmax(0,1fr)_minmax(0,2fr)_10rem_12rem]">
                        {c.knowledge_type === "reading_skill" ? (
                          <Select value={d.skill ?? ""} onValueChange={(v) => update(c.ref, { skill: v })}>
                            <SelectTrigger aria-label="Kỹ năng đọc" className="w-full">
                              <SelectValue placeholder="Chọn kỹ năng" />
                            </SelectTrigger>
                            <SelectContent>
                              {Object.entries(data.reading_skills).map(([k, label]) => (
                                <SelectItem key={k} value={k}>
                                  {label}
                                </SelectItem>
                              ))}
                            </SelectContent>
                          </Select>
                        ) : (
                          <Input lang="ja" aria-label="Nhãn kiến thức" value={d.title} onChange={(e) => update(c.ref, { title: e.target.value })} />
                        )}
                        <Input aria-label="Tóm tắt" value={d.summary} onChange={(e) => update(c.ref, { summary: e.target.value })} />
                        <Select value={d.role} onValueChange={(v) => update(c.ref, { role: v as KnowledgeRole })}>
                          <SelectTrigger aria-label="Vai trò" className="w-full">
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent>
                            {(["tests", "distractor", "context"] as const).map((r) => (
                              <SelectItem key={r} value={r}>
                                {roleLabels[r]}
                              </SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                        <Select value={d.action} onValueChange={(v) => update(c.ref, { action: v as Action })}>
                          <SelectTrigger aria-label="Thao tác" className="w-full">
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent>
                            {actions.map((a) => (
                              <SelectItem key={a} value={a}>
                                {actionLabels[a]}
                              </SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                      </div>
                      {c.match ? (
                        <p className="text-xs text-muted-foreground">
                          Mục đã có: <span lang="ja">{c.match.title}</span> — {c.match.content || "(chưa có tóm tắt)"} ·{" "}
                          {c.match.reason === "same_key" ? "trùng khoá" : "tên gần giống"} · độ giống nghĩa{" "}
                          {Math.round(c.match.meaning_similarity * 100)}%
                        </p>
                      ) : null}
                      {c.warnings.map((w) => (
                        <p key={w} className="text-xs text-amber-700 dark:text-amber-400">
                          {w}
                        </p>
                      ))}
                    </div>
                  );
                })}
                {q.relations.length ? (
                  <div className="space-y-1 text-sm">
                    <p className="font-medium">Quan hệ dễ nhầm</p>
                    {q.relations.map((r) => {
                      const key = `${r.source_ref}>${r.target_ref}`;
                      return (
                        <label key={key} className="flex items-center gap-2">
                          <Checkbox checked={relations[key] ?? false} onCheckedChange={(v) => setRelations({ ...relations, [key]: v === true })} />
                          <span lang="ja">
                            {drafts[r.source_ref]?.title} ⇄ {drafts[r.target_ref]?.title}
                          </span>
                        </label>
                      );
                    })}
                  </div>
                ) : null}
              </CardContent>
            ) : null}
          </Card>
        ))}
      </div>

      {usable.length ? (
        <div className="sticky bottom-0 mt-6 flex flex-wrap items-center justify-end gap-3 border-t bg-background/95 py-3 backdrop-blur">
          <div className="flex items-center gap-3">
            {missingSkill ? <span className="text-xs text-destructive">Chọn kỹ năng đọc cho mục đọc hiểu trước khi lưu.</span> : null}
            <Button disabled={!chosen.length || missingSkill || confirm.isPending || !!result} onClick={() => confirm.mutate()}>
              {confirm.isPending ? "Đang lưu…" : `Xác nhận ${chosen.length} mục`}
            </Button>
          </div>
        </div>
      ) : (
        <p className="mt-4 text-sm text-muted-foreground">Không có lời giải đã duyệt nào để trích xuất. Hãy duyệt lời giải AI trước.</p>
      )}
    </>
  );
}
