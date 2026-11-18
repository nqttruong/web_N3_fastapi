"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, CheckCircle2, FileDown, FileUp, RefreshCw, Sparkles, XCircle } from "lucide-react";
import Link from "next/link";
import { useParams, useSearchParams } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";

import { PageHeader } from "@/components/page-header";
import { RichText } from "@/components/rich-text";
import { EmptyState, ErrorState, LoadingState, errorMessage } from "@/components/states";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { api } from "@/lib/api/endpoints";
import { queryKeys } from "@/lib/api/keys";
import type { Explanation } from "@/lib/api/types";
import { formatDateTime } from "@/lib/format";
import { questionTypeMessageKey } from "@/lib/localized-labels";
import { cn } from "@/lib/utils";
import { useLocale } from "@/lib/i18n";

import { ExplanationView } from "./explanation-view";

export function ExplanationStatusBadge({ explanation }: { explanation: Pick<Explanation, "status" | "stale"> }) {
  const { t } = useLocale();
  if (explanation.stale) return <Badge variant="outline" className="text-muted-foreground">{t("explanationStale")}</Badge>;
  const s = explanation.status;
  return (
    <Badge
      variant={s === "rejected" ? "destructive" : "outline"}
      className={cn(
        s === "approved" && "border-emerald-600/50 text-emerald-700 dark:text-emerald-400",
        (s === "generated" || s === "needs_review") && "border-amber-500/60 text-amber-700 dark:text-amber-400",
      )}
    >
      {s === "approved" ? t("statusReady") : s === "rejected" ? t("explanationRejected") : t("pendingApproval")}
    </Badge>
  );
}

export function QuestionExplanationPage() {
  const { t, locale } = useLocale();
  const { id } = useParams<{ id: string }>();
  const params = useSearchParams();
  const attemptId = params.get("attempt") ?? undefined;
  const answerId = params.get("answer") ?? undefined;
  const queryClient = useQueryClient();
  const [selectedVersion, setSelectedVersion] = useState<string | null>(null);

  const question = useQuery({ queryKey: queryKeys.question(id), queryFn: () => api.getQuestion(id) });
  const passages = useQuery({
    queryKey: queryKeys.passages(question.data?.exam_id ?? ""),
    queryFn: () => api.listPassages(question.data!.exam_id),
    enabled: !!question.data?.passage_id,
  });
  const attempt = useQuery({
    queryKey: queryKeys.attempt(attemptId ?? ""),
    queryFn: () => api.getAttempt(attemptId!),
    enabled: !!attemptId,
  });
  const caps = useQuery({ queryKey: queryKeys.aiCapabilities, queryFn: api.aiCapabilities });
  const explanations = useQuery({
    queryKey: queryKeys.questionExplanations(id, answerId),
    queryFn: () => api.questionExplanations(id, answerId),
  });

  const refresh = () => {
    queryClient.invalidateQueries({ queryKey: queryKeys.explanationsRoot });
  };
  const generate = useMutation({
    mutationFn: (force: boolean) => api.generateExplanation({ question_id: id, attempt_answer_id: answerId, force }),
    onSuccess: (r) => {
      refresh();
      setSelectedVersion(null);
      toast.success(r.outcome === "cached" ? t("cachedExplanation") : t("generatedExplanationReview"));
    },
    onError: (e) => toast.error(errorMessage(e)),
  });
  const approve = useMutation({
    mutationFn: (expId: string) => api.approveExplanation(expId),
    onSuccess: () => {
      refresh();
      toast.success(t("approvedExplanationToast"));
    },
    onError: (e) => toast.error(errorMessage(e)),
  });
  const reject = useMutation({
    mutationFn: ({ expId, note }: { expId: string; note?: string }) => api.rejectExplanation(expId, note),
    onSuccess: () => {
      refresh();
      toast.success(t("rejectedExplanationToast"));
    },
    onError: (e) => toast.error(errorMessage(e)),
  });

  if (question.isPending || explanations.isPending) return <LoadingState rows={5} />;
  const error = question.error ?? explanations.error;
  if (error) return <ErrorState error={error} onRetry={() => { question.refetch(); explanations.refetch(); }} />;

  const q = question.data!;
  const data = explanations.data!;
  const passage = passages.data?.find((p) => p.id === q.passage_id);
  const selectedAnswer = attempt.data?.answers.find((a) => a.question_id === id)?.selected_answer ?? null;
  const shown =
    data.versions.find((v) => v.id === selectedVersion) ??
    data.versions.find((v) => v.id === data.current_id) ??
    null;
  const apiAvailable = caps.data?.api_available ?? false;
  const manualHref = `/explanations/manual?q=${id}${attemptId ? `&attempt=${attemptId}` : ""}`;
  const pendingReview = shown && !shown.stale && (shown.status === "generated" || shown.status === "needs_review");

  return (
    <>
      <PageHeader
        title={t("explanationTitle").replace("{number}", String(q.question_number))}
        description={t(questionTypeMessageKey[q.question_type])}
        actions={
          <>
            {attemptId ? (
              <Button asChild variant="outline">
                <Link href={`/attempts/${attemptId}`}>{t("backToAttempt")}</Link>
              </Button>
            ) : null}
            <Button asChild variant="outline">
              <Link href={`/exams/${q.exam_id}`}>{t("backToExam")}</Link>
            </Button>
          </>
        }
      />

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_20rem]">
        <div className="min-w-0 space-y-6">
          <Card>
            <CardContent className="space-y-3">
              {passage ? (
                <div className="rounded-lg bg-muted/40 p-3 text-sm leading-relaxed whitespace-pre-wrap">
                  <RichText text={passage.content} />
                </div>
              ) : null}
              <p className="text-base leading-relaxed whitespace-pre-wrap">
                <RichText text={q.question_text} />
              </p>
              <ol className="grid gap-1.5 sm:grid-cols-2">
                {q.options.map((opt, i) => (
                  <li
                    key={i}
                    className={cn(
                      "rounded-lg border px-3 py-2 text-sm",
                      q.answer_status === "verified" && q.correct_answer === i + 1 && "border-emerald-600/50 bg-emerald-50 dark:bg-emerald-950/40",
                      selectedAnswer === i + 1 && q.correct_answer !== i + 1 && "border-destructive/50",
                    )}
                  >
                    <span className="text-muted-foreground">{i + 1}. </span>
                    <RichText text={opt} />
                    {selectedAnswer === i + 1 ? <span className="ml-2 text-xs text-muted-foreground">{t("selectedByYou")}</span> : null}
                  </li>
                ))}
              </ol>
            </CardContent>
          </Card>

          {!data.eligible ? (
            <Alert>
              <AlertTriangle aria-hidden />
              <AlertTitle>{t("cannotReviewQuestion")}</AlertTitle>
              <AlertDescription>
                <p>{data.ineligible_code === "answer_not_verified" ? t("answerNeedsVerification") : data.ineligible_code === "missing_passage" ? t("missingPassage") : t("cannotReviewQuestion")}</p>
                {data.ineligible_message ? <details className="mt-2 text-xs"><summary className="cursor-pointer">{t("errorDetails")}</summary><p className="mt-1">{data.ineligible_message}</p></details> : null}
                {data.ineligible_code === "answer_not_verified" ? (
                  <Link className="underline" href={`/exams/${q.exam_id}`}>
                    {t("verifyAnswerOnExam")}
                  </Link>
                ) : null}
              </AlertDescription>
            </Alert>
          ) : null}

          {shown?.flagged_answer_concern && !shown.stale ? (
            <Alert variant="destructive">
              <AlertTriangle aria-hidden />
              <AlertTitle>{t("aiAnswerConcern")}</AlertTitle>
              <AlertDescription>
                {shown.payload?.quality.source_answer_concern} {t("verifiedAnswerUnchanged")}
              </AlertDescription>
            </Alert>
          ) : null}

          {shown ? (
            <Card>
              <CardHeader>
                <CardTitle className="flex flex-wrap items-center gap-2">
                  {t("explanationLabel")} <ExplanationStatusBadge explanation={shown} />
                  {!shown.is_current && !shown.stale ? <Badge variant="outline">{t("oldVersion")}</Badge> : null}
                </CardTitle>
                <CardDescription>
                  {shown.origin === "manual" ? t("manualFromChatgpt") : `${shown.provider} · ${shown.model}`} ·{" "}
                  {formatDateTime(shown.created_at, locale)} · {t("promptVersionLabel")} {shown.prompt_version}
                  {shown.stale ? ` · ${t("questionOrAnswerChanged")}` : ""}
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                {pendingReview ? (
                  <Alert>
                    <AlertTitle>{t("awaitingYourApproval")}</AlertTitle>
                    <AlertDescription>
                      {t("formatCheckPassedWithWarning")}{shown.status === "needs_review" ? ` ${t("butWarnings")}` : ""}. {t("reviewExplanationCarefully")}
                    </AlertDescription>
                  </Alert>
                ) : null}
                {shown.validation_issues.filter((f) => f.option_index === null).length ? (
                  <ul className="space-y-1 text-xs" aria-label={t("validationResults")}>
                    {shown.validation_issues
                      .filter((f) => f.option_index === null)
                      .map((f, i) => (
                        <li key={`${f.code}-${i}`} className={f.severity === "warning" ? "text-amber-700 dark:text-amber-400" : "text-muted-foreground"}>
                          <details>
                            <summary className="cursor-pointer">{t("validation")} · {t(f.severity === "error" ? "severityError" : f.severity === "warning" ? "severityWarning" : "severityInfo")}</summary>
                            <p className="mt-1">{f.message}</p>
                          </details>
                        </li>
                      ))}
                  </ul>
                ) : null}
                {shown.payload ? (
                  <ExplanationView
                    payload={shown.payload}
                    learner={shown.learner_error_analysis}
                    selectedAnswer={selectedAnswer}
                    findings={shown.validation_issues}
                  />
                ) : (
                  <p className="text-sm text-muted-foreground">{t("oldExplanationFormat")}</p>
                )}
                {shown.review_note ? <p className="text-sm">{t("note")}: {shown.review_note}</p> : null}
                {!shown.stale && shown.status !== "rejected" ? (
                  <div className="flex flex-wrap gap-2 border-t pt-4">
                    {shown.status !== "approved" ? (
                      <Button disabled={approve.isPending} onClick={() => approve.mutate(shown.id)}>
                        <CheckCircle2 aria-hidden /> {t("approveExplanation")}
                      </Button>
                    ) : null}
                    <Button
                      variant="outline"
                      disabled={reject.isPending}
                      onClick={() => {
                        const note = window.prompt(t("whereWrongOptional")) ?? undefined;
                        reject.mutate({ expId: shown.id, note });
                      }}
                    >
                      <XCircle aria-hidden /> {t("markIncorrect")}
                    </Button>
                  </div>
                ) : null}
              </CardContent>
            </Card>
          ) : data.eligible ? (
            <EmptyState
              title={t("noExplanationForQuestion")}
              description={apiAvailable ? t("useAiOrChatgpt") : t("noApiUseManual")}
            />
          ) : null}
        </div>

        <aside className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>{t("reviewPanelTitle")}</CardTitle>
              <CardDescription>
                {apiAvailable ? `AI: ${caps.data?.provider} · ${caps.data?.model}` : t("checkingAiConfig")}
              </CardDescription>
            </CardHeader>
            <CardContent className="flex flex-col gap-2">
              {apiAvailable && data.eligible ? (
                data.current_id ? (
                  <Button
                    variant="outline"
                    disabled={generate.isPending}
                    onClick={() => window.confirm(t("regenerateCostConfirm")) && generate.mutate(true)}
                  >
                    <RefreshCw aria-hidden /> {generate.isPending ? t("generating") : t("regenerateExplanation")}
                  </Button>
                ) : (
                  <Button disabled={generate.isPending} onClick={() => generate.mutate(false)}>
                    <Sparkles aria-hidden /> {generate.isPending ? t("aiWorking") : t("reviewWithAi")}
                  </Button>
                )
              ) : null}
              {data.eligible ? (
                <>
                  <Button asChild variant="outline">
                    <Link href={manualHref}>
                      <FileDown aria-hidden /> {t("exportPrompt")}
                    </Link>
                  </Button>
                  <Button asChild variant="outline">
                    <Link href={`${manualHref}&step=import`}>
                      <FileUp aria-hidden /> {t("importExplanationJson")}
                    </Link>
                  </Button>
                </>
              ) : null}
            </CardContent>
          </Card>

          {data.versions.length > 0 ? (
            <Card>
              <CardHeader>
                <CardTitle>{t("versions")} ({data.versions.length})</CardTitle>
              </CardHeader>
              <CardContent>
                <ul className="space-y-2 text-sm">
                  {data.versions.map((v) => (
                    <li key={v.id}>
                      <button
                        type="button"
                        onClick={() => setSelectedVersion(v.id)}
                        className={cn("w-full rounded-lg border p-2 text-left hover:bg-muted/50", shown?.id === v.id && "border-primary")}
                      >
                        <div className="flex items-center gap-2">
                          <ExplanationStatusBadge explanation={v} />
                          {v.is_current ? <Badge variant="secondary">{t("currentVersion")}</Badge> : null}
                        </div>
                        <p className="mt-1 text-xs text-muted-foreground">
                          {v.origin === "manual" ? t("manual") : v.model} · {formatDateTime(v.created_at, locale)}
                        </p>
                      </button>
                    </li>
                  ))}
                </ul>
              </CardContent>
            </Card>
          ) : null}
        </aside>
      </div>
    </>
  );
}
