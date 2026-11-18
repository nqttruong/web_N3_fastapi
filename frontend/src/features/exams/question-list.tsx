"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, Trash2 } from "lucide-react";
import Link from "next/link";
import { toast } from "sonner";

import { RichText } from "@/components/rich-text";
import { AnswerStatusBadge } from "@/components/badges";
import { errorMessage } from "@/components/states";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api/endpoints";
import { queryKeys } from "@/lib/api/keys";
import type { Passage, Question } from "@/lib/api/types";
import { questionTypeMessageKey } from "@/lib/localized-labels";
import { cn } from "@/lib/utils";
import { useLocale } from "@/lib/i18n";

function QuestionItem({ question, passageIndex }: { question: Question; passageIndex: number | null }) {
  const { t } = useLocale();
  const queryClient = useQueryClient();
  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: queryKeys.exam(question.exam_id) });
    queryClient.invalidateQueries({ queryKey: queryKeys.examsRoot });
    queryClient.invalidateQueries({ queryKey: queryKeys.dashboard });
  };

  const verify = useMutation({
    mutationFn: () => api.updateQuestion(question.id, { answer_status: "verified" }),
    onSuccess: () => {
      invalidate();
      toast.success(t("confirmAnswerSuccess").replace("{number}", String(question.question_number)));
    },
    onError: (e) => toast.error(errorMessage(e)),
  });
  const remove = useMutation({
    mutationFn: () => api.deleteQuestion(question.id),
    onSuccess: () => {
      invalidate();
      toast.success(t("deleteQuestionSuccess").replace("{number}", String(question.question_number)));
    },
    onError: (e) => toast.error(errorMessage(e)),
  });

  const verified = question.answer_status === "verified";
  const showKey = question.correct_answer !== null;

  return (
    <li className="rounded-xl border p-4" data-testid="question-item">
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <span className="font-semibold tabular-nums">{t("question")} {question.question_number}</span>
        <Badge variant="secondary">{t(questionTypeMessageKey[question.question_type])}</Badge>
        {passageIndex !== null ? <Badge variant="outline">{t("passageNumber")} {passageIndex + 1}</Badge> : null}
        <AnswerStatusBadge status={question.answer_status} />
        <div className="ml-auto flex items-center gap-1">
          <Button asChild size="sm" variant="ghost">
            <Link href={`/questions/${question.id}/explanation`}>{t("fullExplanation")}</Link>
          </Button>
          {question.answer_status === "unverified" ? (
            <Button size="sm" variant="outline" disabled={verify.isPending} onClick={() => verify.mutate()}>
              <CheckCircle2 aria-hidden /> {t("verifyAnswer")}
            </Button>
          ) : null}
          <Button
            size="sm"
            variant="ghost"
            aria-label={`${t("deleteQuestionLabel")} ${question.question_number}`}
            disabled={remove.isPending}
            onClick={() => {
              if (window.confirm(`${t("deleteQuestionConfirm")} ${question.question_number}? ${t("cannotDeleteAttemptQuestion")}`)) {
                remove.mutate();
              }
            }}
          >
            <Trash2 aria-hidden />
          </Button>
        </div>
      </div>
      <p lang="ja" className="mb-3 text-base leading-relaxed whitespace-pre-wrap">
        <RichText text={question.question_text} />
      </p>
      <ol className="grid gap-1.5 sm:grid-cols-2">
        {question.options.map((option, i) => {
          const isKey = showKey && question.correct_answer === i + 1;
          return (
            <li
              key={i}
              lang="ja"
              className={cn(
                "flex items-start gap-2 rounded-lg border px-3 py-2 text-sm",
                isKey && verified && "border-emerald-600/50 bg-emerald-50 dark:bg-emerald-950/40",
                isKey && !verified && "border-dashed border-amber-500/60",
              )}
            >
              <span className="text-muted-foreground tabular-nums">{i + 1}.</span>
              <RichText className="min-w-0 flex-1 break-words" text={option} />
              {isKey ? (
                <span className={cn("shrink-0 text-xs", verified ? "text-emerald-700 dark:text-emerald-400" : "text-amber-700 dark:text-amber-400")}>
                  {verified ? t("verifiedAnswer") : t("provisionalAnswer")}
                </span>
              ) : null}
            </li>
          );
        })}
      </ol>
    </li>
  );
}

export function QuestionList({ questions, passages }: { questions: Question[]; passages: Passage[] }) {
  const passageIndex = new Map(passages.map((p, i) => [p.id, i]));
  return (
    <ol className="space-y-3">
      {questions.map((q) => (
        <QuestionItem key={q.id} question={q} passageIndex={q.passage_id ? (passageIndex.get(q.passage_id) ?? null) : null} />
      ))}
    </ol>
  );
}
