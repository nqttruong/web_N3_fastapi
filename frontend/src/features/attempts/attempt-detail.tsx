"use client";

import { useQuery } from "@tanstack/react-query";
import { ExternalLink } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";

import { RichText } from "@/components/rich-text";
import { ResultBadge } from "@/components/badges";
import { AiReviewPanel } from "@/features/explanations/ai-review-panel";
import { PageHeader } from "@/components/page-header";
import { ErrorState, LoadingState } from "@/components/states";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { api } from "@/lib/api/endpoints";
import { queryKeys } from "@/lib/api/keys";
import type { AttemptAnswer } from "@/lib/api/types";
import { formatDateTime, formatDuration, formatPercent } from "@/lib/format";
import { questionTypeMessageKey } from "@/lib/localized-labels";
import { cn } from "@/lib/utils";
import { useLocale } from "@/lib/i18n";

function Summary({ label, value, className }: { label: string; value: string | number; className?: string }) {
  return (
    <div className="rounded-xl border p-3">
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className={cn("text-xl font-semibold tabular-nums", className)} data-testid={`summary-${label}`}>
        {value}
      </p>
    </div>
  );
}

function AnswerRow({ answer, attemptId }: { answer: AttemptAnswer; attemptId: string }) {
  const { t } = useLocale();
  const answered = answer.selected_answer !== null;
  return (
    <li
      data-testid="attempt-answer"
      className={cn(
        "rounded-xl border p-4",
        answer.is_correct === true && "border-emerald-600/40",
        answer.is_correct === false && "border-destructive/40",
      )}
    >
      <div className="mb-2 flex flex-wrap items-center gap-2">
        <span className="font-semibold tabular-nums">{t("question")} {answer.question_number}</span>
        <span className="text-xs text-muted-foreground">{t(questionTypeMessageKey[answer.question_type])}</span>
        <span className="ml-auto flex items-center gap-2">
          <Link className="text-xs underline" href={`/questions/${answer.question_id}/explanation?attempt=${attemptId}`}>
            {t("fullExplanation")}
          </Link>
          <ResultBadge isCorrect={answer.is_correct} answered={answered} />
        </span>
      </div>
      <p lang="ja" className="mb-3 leading-relaxed whitespace-pre-wrap">
        <RichText text={answer.question_text} />
      </p>
      <ol className="grid gap-1.5 sm:grid-cols-2">
        {answer.options.map((option, i) => {
          const value = i + 1;
          const selected = answer.selected_answer === value;
          const key = answer.correct_answer === value;
          return (
            <li
              key={i}
              lang="ja"
              className={cn(
                "flex items-start gap-2 rounded-lg border px-3 py-2 text-sm",
                key && "border-emerald-600/50 bg-emerald-50 dark:bg-emerald-950/40",
                selected && !key && answer.is_correct === false && "border-destructive/50 bg-destructive/5",
                selected && answer.is_correct === null && "border-primary",
              )}
            >
              <span className="text-muted-foreground tabular-nums">{value}.</span>
              <RichText className="min-w-0 flex-1 break-words" text={option} />
              <span className="shrink-0 text-xs text-muted-foreground">
                {[selected ? t("answerSelected") : null, key ? t("answerKey") : null].filter(Boolean).join(" · ")}
              </span>
            </li>
          );
        })}
      </ol>
      {answered && answer.correct_answer === null ? (
        <p className="mt-2 text-xs text-amber-700 dark:text-amber-400">
          {t("answerSnapshotMissing")}
        </p>
      ) : null}
    </li>
  );
}

export function AttemptDetailView() {
  const { t, locale } = useLocale();
  const { id } = useParams<{ id: string }>();
  const { data, error, isPending, refetch } = useQuery({
    queryKey: queryKeys.attempt(id),
    queryFn: () => api.getAttempt(id),
  });

  if (isPending) return <LoadingState rows={5} />;
  if (error) return <ErrorState error={error} onRetry={() => refetch()} />;

  return (
    <>
      <PageHeader
        title={<span lang="ja">{data.exam_title}</span>}
        description={`${t("attemptTime")} ${formatDateTime(data.started_at, locale)} · ${t("duration")} ${formatDuration(data.started_at, data.completed_at, locale)}`}
        actions={
          <>
            <Button asChild variant="outline">
              <Link href={`/exams/${data.exam_id}`}>{t("viewExam")}</Link>
            </Button>
            {data.exam_source_url ? (
              <Button asChild variant="outline">
                <a href={data.exam_source_url} target="_blank" rel="noopener noreferrer">
                  {t("examSource")} <ExternalLink aria-hidden />
                </a>
              </Button>
            ) : null}
            <Button asChild>
              <Link href={`/exams/${data.exam_id}/practice`}>{t("retake")}</Link>
            </Button>
            <Button asChild variant="outline">
              <Link href={`/knowledge/extract?attempt=${data.id}`}>{t("extractKnowledge")}</Link>
            </Button>
          </>
        }
      />

      <Card className="mb-6">
        <CardContent>
          <section aria-label={t("attemptSummary")} className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
            <Summary label={t("questionCount")} value={data.total_questions} />
            <Summary label={t("correct")} value={data.correct_count} className="text-emerald-700 dark:text-emerald-400" />
            <Summary label={t("incorrect")} value={data.incorrect_count} className="text-destructive" />
            <Summary label={t("unanswered")} value={data.unanswered_count} />
            <Summary label={t("ungraded")} value={data.ungraded_count} />
            <Summary label={t("scoreAccuracy")} value={formatPercent(data.accuracy, locale)} />
            <Summary label={t("correctAllQuestions")} value={formatPercent(data.total_questions ? data.correct_count / data.total_questions : null, locale)} />
          </section>
          <p className="mt-3 text-xs text-muted-foreground">
            {t("resultFormula")}
          </p>
        </CardContent>
      </Card>

      <AiReviewPanel attemptId={data.id} />

      <h2 className="mb-3 text-lg font-semibold">{t("answerDetails")}</h2>
      <ol className="space-y-3">
        {data.answers.map((a) => (
          <AnswerRow key={a.question_id} answer={a} attemptId={data.id} />
        ))}
      </ol>
    </>
  );
}
