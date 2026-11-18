"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";

import { RichText } from "@/components/rich-text";
import { PageHeader } from "@/components/page-header";
import { EmptyState, ErrorState, LoadingState, errorMessage } from "@/components/states";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api/endpoints";
import { queryKeys } from "@/lib/api/keys";
import { questionTypeMessageKey } from "@/lib/localized-labels";
import { cn } from "@/lib/utils";
import { useLocale } from "@/lib/i18n";

export function PracticeView() {
  const { t } = useLocale();
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const queryClient = useQueryClient();
  const [startedAt] = useState(() => new Date().toISOString());
  const [answers, setAnswers] = useState<Record<string, number>>({});
  const [questionIndex, setQuestionIndex] = useState(0);

  const exam = useQuery({ queryKey: queryKeys.exam(id), queryFn: () => api.getExam(id) });
  // Practice mode never downloads the answer key.
  const questions = useQuery({
    queryKey: queryKeys.questions(id, false),
    queryFn: () => api.listQuestions(id, { includeAnswers: false }),
  });
  const passages = useQuery({ queryKey: queryKeys.passages(id), queryFn: () => api.listPassages(id) });

  const submit = useMutation({
    mutationFn: () =>
      api.createAttempt({
        exam_id: id,
        started_at: startedAt,
        completed_at: new Date().toISOString(),
        answers: (questions.data?.data ?? []).map((q) => ({
          question_id: q.id,
          selected_answer: answers[q.id] ?? null,
        })),
      }),
    onSuccess: (attempt) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.attemptsRoot });
      queryClient.invalidateQueries({ queryKey: queryKeys.dashboard });
      queryClient.setQueryData(queryKeys.attempt(attempt.id), attempt);
      toast.success(t("examSaved"));
      router.push(`/attempts/${attempt.id}`);
    },
    onError: (e) => toast.error(errorMessage(e)),
  });

  const error = exam.error ?? questions.error ?? passages.error;
  if (error) {
    const retry = () => {
      exam.refetch();
      questions.refetch();
      passages.refetch();
    };
    return <ErrorState error={error} onRetry={retry} />;
  }
  const examData = exam.data;
  if (!examData || !questions.data || !passages.data) return <LoadingState rows={5} />;

  const list = questions.data.data;
  const passageById = new Map(passages.data.map((p, i) => [p.id, { ...p, index: i }]));
  const answered = list.filter((q) => answers[q.id] !== undefined).length;

  if (examData.status === "archived") {
    return (
      <EmptyState
        title={t("takeArchivedExam")}
        description={t("archivedExamHint")}
        action={<Button asChild variant="outline"><Link href={`/exams/${id}`}>{t("viewExam")}</Link></Button>}
      />
    );
  }
  if (list.length === 0) {
    return (
      <EmptyState
        title={t("noQuestions")}
        action={<Button asChild variant="outline"><Link href={`/exams/${id}`}>{t("addQuestion")}</Link></Button>}
      />
    );
  }

  const currentQuestion = list[Math.min(questionIndex, list.length - 1)];
  const currentPassage = currentQuestion.passage_id
    ? passageById.get(currentQuestion.passage_id)
    : undefined;

  return (
    <>
      <PageHeader
        title={<span lang="ja">{examData.title}</span>}
      description={`${t("examAttempt")} · ${list.length} ${t("questionCount").toLocaleLowerCase()}. ${t("takeExamDescription")}`}
        actions={
          <Button asChild variant="outline">
            <Link href={`/exams/${id}`}>{t("exit")}</Link>
          </Button>
        }
      />
      {examData.verified_answer_count < examData.question_count ? (
        <Alert className="mb-6">
          <AlertDescription>
            {examData.question_count - examData.verified_answer_count} {t("unverifiedAnswerWarning")}
          </AlertDescription>
        </Alert>
      ) : null}

      <form
        aria-label={t("examAttempt")}
        onSubmit={(e) => {
          e.preventDefault();
          const missing = list.length - answered;
          if (missing > 0 && !window.confirm(`${missing} ${t("unansweredConfirm")}`)) return;
          submit.mutate();
        }}
        className="space-y-4"
      >
        <div className="space-y-3">
          {currentPassage ? (
            <div className="rounded-xl border bg-muted/30 p-4">
              <p className="mb-1 text-xs font-medium text-muted-foreground">{t("passageNumber")} {currentPassage.index + 1}</p>
              <p lang="ja" className="leading-relaxed whitespace-pre-wrap"><RichText text={currentPassage.content} /></p>
            </div>
          ) : null}
          <fieldset className="rounded-xl border p-4" data-testid="practice-question">
            <legend className="sr-only">{t("question")} {currentQuestion.question_number}</legend>
            <p className="mb-1 text-xs text-muted-foreground">
              {t("question")} {currentQuestion.question_number} · {t(questionTypeMessageKey[currentQuestion.question_type])}
            </p>
            <p lang="ja" className="mb-3 text-base leading-relaxed whitespace-pre-wrap"><RichText text={currentQuestion.question_text} /></p>
            <div className="grid gap-2 sm:grid-cols-2">
              {currentQuestion.options.map((option, i) => {
                const value = i + 1;
                const checked = answers[currentQuestion.id] === value;
                return (
                  <label
                    key={i}
                    className={cn(
                      "flex cursor-pointer items-start gap-2 rounded-lg border px-3 py-2 text-sm transition-colors hover:bg-muted/50",
                      checked && "border-primary bg-primary/5",
                    )}
                  >
                    <input
                      type="radio"
                      name={`q-${currentQuestion.id}`}
                      value={value}
                      checked={checked}
                      onChange={() => setAnswers((prev) => ({ ...prev, [currentQuestion.id]: value }))}
                      className="mt-0.5 size-4 accent-primary"
                    />
                    <span className="text-muted-foreground tabular-nums">{value}.</span>
                    <RichText className="min-w-0 break-words" text={option} />
                  </label>
                );
              })}
            </div>
          </fieldset>
        </div>

        <div className="sticky bottom-0 -mx-4 flex items-center justify-between gap-3 border-t bg-background/95 px-4 py-3 backdrop-blur md:mx-0 md:rounded-xl md:border">
          <span className="text-sm text-muted-foreground tabular-nums">
            {t("question")} {questionIndex + 1}/{list.length} · {t("answered")} {answered}/{list.length}
          </span>
          <div className="flex items-center gap-2">
            <Button
              type="button"
              variant="outline"
              disabled={questionIndex === 0 || submit.isPending}
              onClick={() => setQuestionIndex((index) => Math.max(0, index - 1))}
            >
              {t("previousQuestion")}
            </Button>
            {questionIndex < list.length - 1 ? (
              <Button type="button" disabled={submit.isPending} onClick={() => setQuestionIndex((index) => Math.min(list.length - 1, index + 1))}>
                {t("nextQuestion")}
              </Button>
            ) : (
              <Button type="submit" disabled={submit.isPending}>
                {submit.isPending ? t("submitting") : t("submitExam")}
              </Button>
            )}
          </div>
        </div>
      </form>
    </>
  );
}
