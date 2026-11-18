"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";

import { errorMessage } from "@/components/states";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { ApiError } from "@/lib/api/client";
import { api } from "@/lib/api/endpoints";
import { queryKeys } from "@/lib/api/keys";
import type { ImportDraft } from "@/lib/api/types";
import { useLocale } from "@/lib/i18n";

interface Candidate {
  exam_id: string;
  title: string;
  reason: string;
}

const REASONS = {
  duplicate_source_url: "duplicate_source_url",
  duplicate_exam: "duplicate_exam",
  questions_in_other_exam: "questions_in_other_exam",
} as const;

export function candidatesFrom(draft: ImportDraft): Candidate[] {
  const seen = new Map<string, Candidate>();
  for (const issue of draft.issues) {
    const examId = issue.data?.exam_id;
    if (typeof examId !== "string" || !(issue.code in REASONS) || seen.has(examId)) continue;
    seen.set(examId, { exam_id: examId, title: String(issue.data?.title ?? examId), reason: REASONS[issue.code as keyof typeof REASONS]! });
  }
  return [...seen.values()];
}

export function CommitDialog({ draft, onClose }: { draft: ImportDraft; onClose: () => void }) {
  const { t } = useLocale();
  const router = useRouter();
  const queryClient = useQueryClient();
  const candidates = candidatesFrom(draft);
  const urlDuplicate = draft.issues.some((i) => i.code === "duplicate_source_url");
  const [target, setTarget] = useState<string>(urlDuplicate && candidates[0] ? candidates[0].exam_id : "new");
  const [conflicts, setConflicts] = useState<string[]>([]);

  const included = draft.content.questions.filter((q) => q.include);
  const verified = included.filter((q) => q.correct_answer !== null && q.answer_confirmed).length;
  const unverified = included.filter((q) => q.correct_answer !== null && !q.answer_confirmed).length;
  const missing = included.filter((q) => q.correct_answer === null).length;

  const commit = useMutation({
    mutationFn: () =>
      api.commitImport(draft.id, target === "new" ? { target: "new" } : { target: "existing", existing_exam_id: target }),
    onSuccess: (result) => {
      for (const key of [queryKeys.examsRoot, queryKeys.dashboard, queryKeys.attemptsRoot, queryKeys.importsRoot]) {
        queryClient.invalidateQueries({ queryKey: key });
      }
      toast.success(
        result.already_committed
          ? t("alreadyCommittedToast")
          : t("commitCountsToast").replace("{created}", String(result.created_questions)).replace("{reused}", String(result.reused_questions)) + (result.attempt_id ? ` · ${t("viewCreatedAttempt")}` : ""),
      );
      for (const w of result.warnings) toast.warning(w.message);
      router.push(`/exams/${result.exam_id}`);
    },
    onError: (e) => {
      if (e instanceof ApiError && e.status === 409) {
        const details = e.details as { conflicts?: { question_number: number; reason: string }[] } | null;
        setConflicts(
          details?.conflicts?.map(
            (c) => `${t("question")} ${c.question_number}: ${c.reason === "number_taken" ? t("numberAlreadyUsed") : t("similarQuestionExists")}`,
          ) ?? [e.message],
        );
      }
      toast.error(errorMessage(e));
    },
  });

  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>{t("commitImportTitle")}</DialogTitle>
          <DialogDescription>
            {included.length} {t("commitImportSummary")} {verified} {t("verifiedAnswersShort")}, {unverified} {t("unverifiedAnswersShort")}, {missing} {t("missingAnswersShort")}.
            {draft.content.attempt.create ? ` ${t("attemptWillBeCreated")}` : ""}
          </DialogDescription>
        </DialogHeader>
        <fieldset className="space-y-2" aria-label={t("saveToExam")}>
          <label className="flex items-start gap-2 rounded-lg border p-3 text-sm">
            <input type="radio" name="target" className="mt-1" checked={target === "new"} onChange={() => setTarget("new")} />
            <span>
              <span className="font-medium">{t("createNewExam")}</span>
              {urlDuplicate ? (
                <span className="block text-xs text-destructive">{t("duplicateUrlPrevention")}</span>
              ) : null}
            </span>
          </label>
          {candidates.map((c) => (
            <label key={c.exam_id} className="flex items-start gap-2 rounded-lg border p-3 text-sm">
              <input type="radio" name="target" className="mt-1" checked={target === c.exam_id} onChange={() => setTarget(c.exam_id)} />
              <span>
                <span className="font-medium">{t("useExistingExam")}: {c.title}</span>
                <span className="block text-xs text-muted-foreground">
                  {t("suggestedReason")}: {c.reason === "duplicate_source_url" ? t("duplicateSourceUrl") : c.reason === "duplicate_exam" ? t("duplicateSameQuestions") : t("duplicatePartialQuestions")}. {t("reuseAndAppend")}
                </span>
              </span>
            </label>
          ))}
        </fieldset>
        {conflicts.length > 0 ? (
          <ul role="alert" className="list-disc pl-5 text-sm text-destructive">
            {conflicts.map((c) => (
              <li key={c}>{c}</li>
            ))}
          </ul>
        ) : null}
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>
            {t("cancel")}
          </Button>
          <Button disabled={commit.isPending} onClick={() => commit.mutate()}>
            {commit.isPending ? t("saving") : t("confirmSave")}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
