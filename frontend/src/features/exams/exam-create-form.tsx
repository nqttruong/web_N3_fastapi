"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { Controller, useForm } from "react-hook-form";
import { toast } from "sonner";

import { FormField } from "@/components/form-field";
import { PageHeader } from "@/components/page-header";
import { errorMessage } from "@/components/states";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { ApiError } from "@/lib/api/client";
import { api } from "@/lib/api/endpoints";
import { queryKeys } from "@/lib/api/keys";
import { EXAM_CATEGORIES, EXAM_STATUSES } from "@/lib/api/types";
import { examCategoryMessageKey, examStatusMessageKey } from "@/lib/localized-labels";
import { examFormSchema, toExamInput, type ExamFormValues } from "@/lib/schemas";
import { useLocale } from "@/lib/i18n";
import { localizedFormMessage } from "@/lib/localized-form-message";

const FIELDS = ["title", "category", "source_url", "description", "status"] as const;

export function ExamCreateForm({ embedded = false }: { embedded?: boolean }) {
  const { t, locale } = useLocale();
  const router = useRouter();
  const queryClient = useQueryClient();
  const form = useForm<ExamFormValues>({
    resolver: zodResolver(examFormSchema),
    defaultValues: { title: "", level: "N3", category: undefined, source_url: "", description: "", status: "draft" },
  });
  const { errors } = form.formState;

  const mutation = useMutation({
    mutationFn: (values: ExamFormValues) => api.createExam(toExamInput(values)),
    onSuccess: (exam) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.examsRoot });
      queryClient.invalidateQueries({ queryKey: queryKeys.dashboard });
      toast.success(t("createdExamToast"));
      router.push(`/exams/${exam.id}`);
    },
    onError: (error) => {
      if (error instanceof ApiError) {
        const fields = error.fieldErrors();
        for (const name of FIELDS) {
          if (fields[name]) form.setError(name, { message: fields[name] });
        }
        if (error.status === 409) form.setError("source_url", { message: error.message });
      }
      toast.error(errorMessage(error));
    },
  });

  return (
    <>
      {embedded ? null : (
        <PageHeader title={t("examCreatePageTitle")} description={t("examCreatePageDescription")} />
      )}

      <div className="grid gap-6">
        <Card>
          <CardHeader>
            <CardTitle>{t("examInfo")}</CardTitle>
            <CardDescription>{t("requiredFields")}</CardDescription>
          </CardHeader>
          <CardContent>
            <form noValidate className="space-y-5" onSubmit={form.handleSubmit((values) => mutation.mutate(values))}>
              <FormField id="title" label={t("examName")} required error={localizedFormMessage(errors.title?.message, t, locale)}>
                <Input id="title" aria-invalid={!!errors.title} {...form.register("title")} />
              </FormField>

              <div className="grid gap-5 sm:grid-cols-3">
                <FormField id="level" label={t("level")} hint={t("n3Only")}>
                  <Input id="level" value="N3" readOnly aria-readonly className="bg-muted" />
                </FormField>
                <FormField id="category" label={t("examType")} required error={localizedFormMessage(errors.category?.message, t, locale)}>
                  <Controller
                    control={form.control}
                    name="category"
                    render={({ field }) => (
                      <Select value={field.value ?? ""} onValueChange={field.onChange}>
                        <SelectTrigger id="category" aria-invalid={!!errors.category} className="w-full">
                          <SelectValue placeholder={t("selectExamType")} />
                        </SelectTrigger>
                        <SelectContent>
                          {EXAM_CATEGORIES.map((c) => (
                            <SelectItem key={c} value={c}>
                              {t(examCategoryMessageKey[c])}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    )}
                  />
                </FormField>
                <FormField id="status" label={t("status")}>
                  <Controller
                    control={form.control}
                    name="status"
                    render={({ field }) => (
                      <Select value={field.value} onValueChange={field.onChange}>
                        <SelectTrigger id="status" className="w-full">
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          {EXAM_STATUSES.filter((s) => s !== "archived").map((s) => (
                            <SelectItem key={s} value={s}>
                              {t(examStatusMessageKey[s])}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    )}
                  />
                </FormField>
              </div>

              <FormField
                id="source_url"
                label={t("sourceUrl")}
                error={localizedFormMessage(errors.source_url?.message, t, locale)}
                hint={t("sourceUrlHint")}
              >
                <Input
                  id="source_url"
                  type="url"
                  inputMode="url"
                  aria-invalid={!!errors.source_url}
                  placeholder="https://…"
                  {...form.register("source_url")}
                />
              </FormField>

              <FormField id="description" label={t("description")} error={localizedFormMessage(errors.description?.message, t, locale)}>
                <Textarea id="description" rows={3} {...form.register("description")} />
              </FormField>

              <div className="flex justify-end gap-2">
                <Button type="button" variant="outline" onClick={() => router.back()}>
                  {t("cancel")}
                </Button>
                <Button type="submit" disabled={mutation.isPending}>
                  {mutation.isPending ? t("saving") : t("create")}
                </Button>
              </div>
            </form>
          </CardContent>
        </Card>

      </div>
    </>
  );
}
