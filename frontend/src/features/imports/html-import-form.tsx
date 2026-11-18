"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";

import { FormField } from "@/components/form-field";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { api } from "@/lib/api/endpoints";
import { htmlImportSchema, toImportMeta } from "@/lib/import-schemas";
import { useLocale } from "@/lib/i18n";
import { localizedFormMessage } from "@/lib/localized-form-message";

import { SourceFields } from "./source-fields";
import { useStartImport } from "./use-start-import";

type Values = { html: string; source_url: string; title: string; category: "" | "vocabulary" | "kanji" | "grammar" | "reading" };

export function HtmlImportForm({ maxBytes }: { maxBytes: number }) {
  const { t, locale } = useLocale();
  const form = useForm<Values>({
    resolver: zodResolver(htmlImportSchema(maxBytes)),
    defaultValues: { html: "", source_url: "", title: "", category: "" },
  });
  const start = useStartImport((v: Values) => api.importHtml({ ...toImportMeta(v), html: v.html }));
  const { errors } = form.formState;

  return (
    <form noValidate aria-label={t("importByHtml")} className="space-y-5" onSubmit={form.handleSubmit((v) => start.mutate(v))}>
      <ol className="list-decimal space-y-1 pl-5 text-sm text-muted-foreground">
        <li>{t("htmlImportInstruction1")}</li>
        <li>{t("htmlImportInstruction2")}</li>
        <li>{t("htmlSafetyNote")}</li>
      </ol>
      <SourceFields prefix="html" control={form.control} register={form.register} errors={errors} />
      <FormField id="import-html" label={t("htmlCode")} required error={localizedFormMessage(errors.html?.message, t, locale)}>
        <Textarea
          id="import-html"
          rows={14}
          spellCheck={false}
          className="font-mono text-xs"
          aria-invalid={!!errors.html}
          placeholder="<html>…</html>"
          {...form.register("html")}
        />
      </FormField>
      <div className="flex justify-end">
        <Button type="submit" disabled={start.isPending}>
          {start.isPending ? t("analyzing") : t("analyzePreview")}
        </Button>
      </div>
    </form>
  );
}
