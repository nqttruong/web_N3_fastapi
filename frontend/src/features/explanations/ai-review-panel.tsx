"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FileDown, RefreshCw, Sparkles, Square } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { toast } from "sonner";

import { errorMessage } from "@/components/states";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { api } from "@/lib/api/endpoints";
import { queryKeys } from "@/lib/api/keys";
import type { AttemptExplanationOverview, JobItem } from "@/lib/api/types";
import { cn } from "@/lib/utils";
import { useLocale } from "@/lib/i18n";

const ACTIVE = new Set(["pending", "running"]);

function Stat({ id, label, value }: { id: string; label: string; value: number | string }) {
  return (
    <div className="rounded-lg border p-2">
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className="text-lg font-semibold tabular-nums" data-testid={`ai-stat-${id}`}>
        {value}
      </p>
    </div>
  );
}

export function AiReviewPanel({ attemptId }: { attemptId: string }) {
  const { t } = useLocale();
  const queryClient = useQueryClient();
  const caps = useQuery({ queryKey: queryKeys.aiCapabilities, queryFn: api.aiCapabilities });
  const overview = useQuery({
    queryKey: queryKeys.attemptExplanations(attemptId),
    queryFn: () => api.attemptExplanations(attemptId),
    // Poll only while a job is active; progress is read from the DB, so it survives reloads.
    refetchInterval: (q) => (q.state.data?.latest_job && ACTIVE.has(q.state.data.latest_job.status) ? 1500 : false),
  });
  const [selected, setSelected] = useState<Set<string> | null>(null);
  const [scope, setScope] = useState<"wrong" | "all">("wrong");

  const invalidate = () => queryClient.invalidateQueries({ queryKey: queryKeys.attemptExplanations(attemptId) });
  const start = useMutation({
    mutationFn: (args: { ids: string[]; force: boolean }) =>
      api.startBatch({ attempt_id: attemptId, question_ids: args.ids, force: args.force }),
    onSuccess: (job) => {
      invalidate();
      toast.success(`${job.counts.total} ${t("questionsQueuedForReview")}`);
    },
    onError: (e) => toast.error(errorMessage(e)),
  });
  const retry = useMutation({
    mutationFn: (jobId: string) => api.retryJob(jobId),
    onSuccess: invalidate,
    onError: (e) => toast.error(errorMessage(e)),
  });
  const cancel = useMutation({
    mutationFn: (jobId: string) => api.cancelJob(jobId),
    onSuccess: invalidate,
    onError: (e) => toast.error(errorMessage(e)),
  });

  if (overview.isPending || caps.isPending) {
    return <Card><CardContent className="text-sm text-muted-foreground">{t("loadingReviewStatus")}</CardContent></Card>;
  }
  if (overview.error || !overview.data) {
    return <Card><CardContent className="text-sm text-destructive">{errorMessage(overview.error)}</CardContent></Card>;
  }
  const data: AttemptExplanationOverview = overview.data;
  const wrong = data.items.filter((i) => i.is_correct === false);
  const eligibleWrong = wrong.filter((i) => i.eligible);
  const eligibleAll = data.items.filter((i) => i.eligible);
  const visibleItems = scope === "all" ? data.items : wrong;
  const chosen = selected ?? new Set(eligibleWrong.filter((i) => !i.explanation_id).map((i) => i.question_id));
  const job = data.latest_job;
  const jobActive = !!job && ACTIVE.has(job.status);
  const itemByQuestion = new Map<string, JobItem>((job?.items ?? []).map((i) => [i.question_id, i]));
  const apiAvailable = caps.data?.api_available ?? false;
  const done = job ? job.counts.total - (job.counts.pending ?? 0) - (job.counts.running ?? 0) : 0;
  const manualIds = [...chosen];

  const toggle = (qid: string, on: boolean) => {
    const next = new Set(chosen);
    if (on) next.add(qid);
    else next.delete(qid);
    setSelected(next);
  };

  return (
    <Card id="ai-review" className="mb-6 scroll-mt-4" aria-labelledby="ai-review-title">
      <CardHeader>
        <CardTitle id="ai-review-title">{t("reviewChatgpt")}</CardTitle>
        <CardDescription>
          {apiAvailable
            ? `${t("aiModelLabel")} (${caps.data?.model}) · ${t("aiReviewVerifiedNote")}`
            : t("noApiUseManual")}
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
          <Stat id="incorrect" label={t("incorrect")} value={data.wrong_count} />
          <Stat id="explained" label={t("explainedQuestions")} value={data.explained_wrong_count} />
          <Stat id="pending" label={t("pendingApproval")} value={data.needs_review_count} />
          <Stat id="not-eligible" label={t("notEligible")} value={wrong.length - eligibleWrong.length} />
        </div>

        <div role="group" aria-label={t("reviewScope")} className="flex flex-wrap gap-2">
          <Button
            size="sm"
            variant={scope === "wrong" ? "default" : "outline"}
            aria-pressed={scope === "wrong"}
            onClick={() => { setScope("wrong"); setSelected(null); }}
          >
            {t("incorrect")}
          </Button>
          <Button
            size="sm"
            variant={scope === "all" ? "default" : "outline"}
            aria-pressed={scope === "all"}
            onClick={() => { setScope("all"); setSelected(new Set(eligibleAll.map((i) => i.question_id))); }}
          >
            {t("allExamQuestions")}
          </Button>
        </div>

        {job ? (
          <div className="space-y-2 rounded-lg border p-3" aria-live="polite">
            <div className="flex flex-wrap items-center gap-2 text-sm">
              <span className="font-medium">{t("latestJob")}:</span>
              <Badge variant={job.status === "failed" ? "destructive" : "outline"} data-testid="job-status">
                {job.status === "pending" ? t("jobPending") : job.status === "running" ? t("jobRunning") : job.status === "completed" ? t("jobCompleted") : job.status === "partial_failed" ? t("jobPartialFailed") : job.status === "failed" ? t("jobFailed") : t("jobCancelled")}
              </Badge>
              <span className="text-muted-foreground tabular-nums">
                {done}/{job.counts.total} {t("questionCount")} · {job.counts.succeeded ?? 0} {t("newItems")} · {job.counts.cached ?? 0} {t("alreadyAvailable")} ·{" "}
                {job.counts.failed ?? 0} {t("errorCount")} · {job.counts.skipped ?? 0} {t("skippedCount")}
              </span>
            </div>
            <div className="h-2 overflow-hidden rounded-full bg-muted" role="progressbar" aria-valuemin={0} aria-valuemax={job.counts.total} aria-valuenow={done}>
              <div className="h-full bg-primary transition-all" style={{ width: `${job.counts.total ? (done / job.counts.total) * 100 : 0}%` }} />
            </div>
            <div className="flex flex-wrap gap-2">
              {jobActive ? (
                <Button size="sm" variant="outline" disabled={cancel.isPending} onClick={() => cancel.mutate(job.id)}>
                  <Square aria-hidden /> {t("cancelPendingQuestions")}
                </Button>
              ) : null}
              {!jobActive && (job.counts.failed ?? 0) > 0 && apiAvailable ? (
                <Button size="sm" variant="outline" disabled={retry.isPending} onClick={() => retry.mutate(job.id)}>
                  <RefreshCw aria-hidden /> {t("retryFailedCount").replace("{count}", String(job.counts.failed))}
                </Button>
              ) : null}
            </div>
          </div>
        ) : null}

        {visibleItems.length === 0 ? (
          <p className="text-sm text-muted-foreground">{scope === "all" ? t("attemptNoQuestions") : t("attemptNoGradedWrongQuestions")}</p>
        ) : (
          <ul className="divide-y rounded-lg border" aria-label={scope === "all" ? t("allExamQuestions") : t("incorrectQuestions")}>
            {visibleItems.map((item) => {
              const jobItem = itemByQuestion.get(item.question_id);
              return (
                <li key={item.question_id} className="flex flex-wrap items-center gap-2 px-3 py-2 text-sm">
                  <Checkbox
                    aria-label={`${t("selectQuestion")} ${item.question_number}`}
                    disabled={!item.eligible || jobActive}
                    checked={item.eligible && chosen.has(item.question_id)}
                    onCheckedChange={(v) => toggle(item.question_id, v === true)}
                  />
                  <span className="font-medium tabular-nums">{t("question")} {item.question_number}</span>
                  {!item.eligible ? (
                    <Badge variant="outline" className="text-muted-foreground">
                      {item.ineligible_code === "answer_not_verified" ? t("answerNeedsVerification") : t("missingPassage")}
                    </Badge>
                  ) : item.explanation_status ? (
                    <Badge
                      variant="outline"
                      className={cn(item.explanation_status === "approved" ? "border-emerald-600/50 text-emerald-700 dark:text-emerald-400" : "border-amber-500/60 text-amber-700 dark:text-amber-400")}
                    >
                      {item.explanation_status === "approved" ? t("statusReady") : item.explanation_status === "rejected" ? t("explanationRejected") : t("pendingApproval")}
                    </Badge>
                  ) : null}
                  {jobItem && (jobActive || jobItem.status === "failed") ? (
                    <Badge variant={jobItem.status === "failed" ? "destructive" : "secondary"} title={jobItem.status === "failed" ? t("jobFailed") : undefined}>
                      {jobItem.status === "pending" ? t("jobPending") : jobItem.status === "running" ? t("jobRunning") : jobItem.status === "cached" ? t("alreadyAvailable") : jobItem.status === "succeeded" ? t("jobCompleted") : jobItem.status === "failed" ? t("jobFailed") : t("skippedCount")}
                    </Badge>
                  ) : null}
                  {jobItem?.status === "failed" && jobItem.error_message ? (
                    <details className="text-xs text-destructive">
                      <summary className="cursor-pointer">{t("jobFailed")} · {t("errorDetails")}</summary>
                      <p className="mt-1 whitespace-pre-wrap">{jobItem.error_message}</p>
                    </details>
                  ) : null}
                  <Link
                    className="ml-auto text-xs underline"
                    href={`/questions/${item.question_id}/explanation?attempt=${attemptId}&answer=${item.attempt_answer_id}`}
                  >
                    {item.explanation_id ? t("fullExplanation") : t("openQuestion")}
                  </Link>
                </li>
              );
            })}
          </ul>
        )}

        <div className="flex flex-wrap gap-2">
          {apiAvailable && scope === "wrong" ? (
            <>
              <Button
                disabled={jobActive || start.isPending || chosen.size === 0}
                onClick={() => start.mutate({ ids: [...chosen], force: false })}
              >
                <Sparkles aria-hidden /> {t("aiReviewWrong")} ({chosen.size})
              </Button>
              <Button
                variant="outline"
                disabled={jobActive || start.isPending || chosen.size === 0}
                onClick={() =>
                  window.confirm(t("regenerateExplanations").replace("{count}", String(chosen.size))) &&
                  start.mutate({ ids: [...chosen], force: true })
                }
              >
                <RefreshCw aria-hidden /> {t("reviewAgain")}
              </Button>
            </>
          ) : null}
          <Button asChild variant={apiAvailable ? "ghost" : "default"} aria-disabled={manualIds.length === 0}>
            <Link href={manualIds.length ? `/explanations/manual?q=${manualIds.join(",")}&attempt=${attemptId}` : "#"}>
              <FileDown aria-hidden /> {t("exportChatgptPrompt")} ({manualIds.length})
            </Link>
          </Button>
        </div>
        <p className="text-xs text-muted-foreground">
          {t("promptEligibilityNote")}
        </p>
      </CardContent>
    </Card>
  );
}
