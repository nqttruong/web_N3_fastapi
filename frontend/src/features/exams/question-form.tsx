"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Controller, useForm, useWatch } from "react-hook-form";
import { toast } from "sonner";

import { FormField } from "@/components/form-field";
import { errorMessage } from "@/components/states";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { ApiError } from "@/lib/api/client";
import { api } from "@/lib/api/endpoints";
import { queryKeys } from "@/lib/api/keys";
import { QUESTION_TYPES, type ExamCategory, type Passage, type QuestionType } from "@/lib/api/types";
import { questionTypeMessageKey } from "@/lib/localized-labels";
import { useLocale } from "@/lib/i18n";
import { localizedFormMessage } from "@/lib/localized-form-message";
import {
  MAX_OPTIONS,
  questionFormSchema,
  toQuestionInput,
  type QuestionFormInput,
  type QuestionFormValues,
} from "@/lib/schemas";

const DEFAULT_TYPE: Record<ExamCategory, QuestionType> = {
  vocabulary: "contextual_definition",
  kanji: "kanji_reading",
  grammar: "grammar_form",
  reading: "reading_short",
};
const NO_PASSAGE = "__none__";

function emptyValues(nextNumber: number, category: ExamCategory): QuestionFormInput {
  return {
    question_number: nextNumber,
    question_type: DEFAULT_TYPE[category],
    question_text: "",
    options: Array.from({ length: MAX_OPTIONS }, () => ""),
    correct_answer: "",
    verified: true,
    passage_id: "",
  };
}

export function QuestionForm({
  examId,
  category,
  nextNumber,
  passages,
}: {
  examId: string;
  category: ExamCategory;
  nextNumber: number;
  passages: Passage[];
}) {
  const { t, locale } = useLocale();
  const queryClient = useQueryClient();
  const form = useForm<QuestionFormInput, unknown, QuestionFormValues>({
    resolver: zodResolver(questionFormSchema),
    defaultValues: emptyValues(nextNumber, category),
  });
  const { errors } = form.formState;
  const options = useWatch({ control: form.control, name: "options" });

  const mutation = useMutation({
    mutationFn: (values: QuestionFormValues) => api.createQuestion(examId, toQuestionInput(values)),
    onSuccess: (question) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.exam(examId) });
      queryClient.invalidateQueries({ queryKey: queryKeys.examsRoot });
      queryClient.invalidateQueries({ queryKey: queryKeys.dashboard });
      toast.success(t("questionAddSuccess").replace("{number}", String(question.question_number)));
      form.reset(emptyValues(question.question_number + 1, category));
    },
    onError: (error) => {
      if (error instanceof ApiError) {
        const fields = error.fieldErrors();
        if (fields.question_number) form.setError("question_number", { message: fields.question_number });
        if (error.status === 409) {
          const field = (error.details as { field?: string } | null)?.field;
          form.setError(field === "question_number" ? "question_number" : "question_text", {
            message: error.message,
          });
        }
      }
      toast.error(errorMessage(error));
    },
  });

  return (
    <form
      noValidate
      aria-label={t("addQuestionForm")}
      className="space-y-5"
      onSubmit={form.handleSubmit((values) => mutation.mutate(values))}
    >
      <div className="grid gap-5 sm:grid-cols-[8rem_minmax(0,1fr)]">
        <FormField id="question_number" label={t("questionNumber")} required error={localizedFormMessage(errors.question_number?.message, t, locale)}>
          <Input
            id="question_number"
            type="number"
            min={1}
            max={999}
            aria-invalid={!!errors.question_number}
            {...form.register("question_number")}
          />
        </FormField>
        <FormField id="question_type" label={t("questionType")} required>
          <Controller
            control={form.control}
            name="question_type"
            render={({ field }) => (
              <Select value={field.value} onValueChange={field.onChange}>
                <SelectTrigger id="question_type" className="w-full">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {QUESTION_TYPES.map((questionType) => (
                    <SelectItem key={questionType} value={questionType}>
                      {t(questionTypeMessageKey[questionType])}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            )}
          />
        </FormField>
      </div>

      {passages.length > 0 ? (
        <FormField id="passage_id" label={t("relatedPassage")}>
          <Controller
            control={form.control}
            name="passage_id"
            render={({ field }) => (
              <Select
                value={field.value || NO_PASSAGE}
                onValueChange={(v) => field.onChange(v === NO_PASSAGE ? "" : v)}
              >
                <SelectTrigger id="passage_id" className="w-full">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value={NO_PASSAGE}>{t("noPassageLinked")}</SelectItem>
                  {passages.map((p, i) => (
                    <SelectItem key={p.id} value={p.id}>
                      {t("passageNumber")} {i + 1}: {p.content.slice(0, 30)}…
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            )}
          />
        </FormField>
      ) : null}

      <FormField id="question_text" label={t("questionText")} required error={localizedFormMessage(errors.question_text?.message, t, locale)}>
        <Textarea
          id="question_text"
          lang="ja"
          rows={3}
          aria-invalid={!!errors.question_text}
          {...form.register("question_text")}
        />
      </FormField>

      <fieldset className="space-y-2">
        <legend className="text-sm font-medium">
          {t("optionsTitle")} <span className="text-muted-foreground">({t("optionsHint")})</span>
        </legend>
        <Controller
          control={form.control}
          name="correct_answer"
          render={({ field }) => (
            <div role="radiogroup" aria-label={t("correctAnswer")} className="space-y-2">
              {options.map((_, index) => {
                const value = String(index + 1);
                const filled = (options[index] ?? "").trim() !== "";
                return (
                  <div key={index} className="flex items-center gap-2">
                    <input
                      type="radio"
                      name="correct_answer"
                      value={value}
                      aria-label={`${t("correctAnswer")} · ${t("choice").replace("{number}", value)}`}
                      checked={field.value === value}
                      disabled={!filled}
                      onChange={() => field.onChange(value)}
                      className="size-4 accent-primary"
                    />
                    <span className="w-5 text-sm text-muted-foreground tabular-nums">{value}.</span>
                    <Input
                      lang="ja"
                      aria-label={t("choice").replace("{number}", value)}
                      aria-invalid={!!errors.options}
                      {...form.register(`options.${index}` as const)}
                    />
                  </div>
                );
              })}
              <div className="flex items-center gap-2 pt-1">
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  disabled={field.value === ""}
                  onClick={() => field.onChange("")}
                >
                  {t("clearCorrectAnswer")}
                </Button>
                <span className="text-xs text-muted-foreground">{t("answerCanBeAddedLater")}</span>
              </div>
            </div>
          )}
        />
        {errors.options?.message || errors.options?.root?.message ? (
          <p role="alert" className="text-sm text-destructive">
            {localizedFormMessage(errors.options?.message ?? errors.options?.root?.message, t, locale)}
          </p>
        ) : null}
        {errors.correct_answer?.message ? (
          <p role="alert" className="text-sm text-destructive">
            {localizedFormMessage(errors.correct_answer.message, t, locale)}
          </p>
        ) : null}
      </fieldset>

      <Controller
        control={form.control}
        name="verified"
        render={({ field }) => (
          <div className="flex items-start gap-2">
            <Checkbox
              id="verified"
              checked={field.value}
              onCheckedChange={(v) => field.onChange(v === true)}
              className="mt-0.5"
            />
            <div className="space-y-0.5">
              <Label htmlFor="verified">{t("officialAnswerConfirmed")}</Label>
              <p className="text-xs text-muted-foreground">
                {t("verifiedAnswerUsage")}
              </p>
              {errors.verified?.message ? (
                <p role="alert" className="text-sm text-destructive">
                  {localizedFormMessage(errors.verified.message, t, locale)}
                </p>
              ) : null}
            </div>
          </div>
        )}
      />

      <div className="flex justify-end">
        <Button type="submit" disabled={mutation.isPending}>
          {mutation.isPending ? t("saving") : t("addQuestionForm")}
        </Button>
      </div>
    </form>
  );
}
