"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useForm, useWatch } from "react-hook-form";

import { FormField } from "@/components/form-field";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { api } from "@/lib/api/endpoints";
import { textImportSchema, toImportMeta } from "@/lib/import-schemas";
import { useLocale } from "@/lib/i18n";
import { localizedFormMessage } from "@/lib/localized-form-message";

import { SourceFields } from "./source-fields";
import { useStartImport } from "./use-start-import";

type Values = { text: string; source_url: string; title: string; category: "" | "vocabulary" | "kanji" | "grammar" | "reading" };

export function TextImportForm({ maxChars }: { maxChars: number }) {
  const { t, locale } = useLocale();
  const form = useForm<Values>({
    resolver: zodResolver(textImportSchema(maxChars)),
    defaultValues: { text: "", source_url: "", title: "", category: "" },
  });
  const text = useWatch({ control: form.control, name: "text" });
  const start = useStartImport((v: Values) => api.importText({ ...toImportMeta(v), text: v.text }));
  const { errors } = form.formState;

  return (
    <form noValidate aria-label={t("importByText")} className="space-y-5" onSubmit={form.handleSubmit((v) => start.mutate(v))}>
      <ol className="list-decimal space-y-1 pl-5 text-sm text-muted-foreground">
        <li>{t("textImportInstruction1")}</li>
        <li>{t("textImportInstruction2")}</li>
        <li>{t("textImportInstruction3")}</li>
      </ol>
      <SourceFields prefix="text" control={form.control} register={form.register} errors={errors} />
      <FormField
        id="import-text"
        label={t("examContent")}
        required
        error={localizedFormMessage(errors.text?.message, t, locale)}
        hint={t("textImportHint").replace("{used}", text.length.toLocaleString(locale)).replace("{max}", maxChars.toLocaleString(locale))}
      >
        <Textarea id="import-text" lang="ja" rows={14} className="font-mono text-sm" aria-invalid={!!errors.text} {...form.register("text")} />
      </FormField>
      <div className="flex justify-end">
        <Button type="submit" disabled={start.isPending}>
          {start.isPending ? t("analyzing") : t("analyzePreview")}
        </Button>
      </div>
    </form>
  );
}
