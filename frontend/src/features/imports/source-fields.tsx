"use client";

import { Controller, type Control, type FieldErrors, type UseFormRegister } from "react-hook-form";

import { FormField } from "@/components/form-field";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { EXAM_CATEGORIES } from "@/lib/api/types";
import type { ImportMetaValues } from "@/lib/import-schemas";
import { useLocale } from "@/lib/i18n";
import { localizedFormMessage } from "@/lib/localized-form-message";

const AUTO = "__auto__";

/** Source info shared by every import tab. The URL is stored only — never fetched. */
export function SourceFields<T extends ImportMetaValues>({
  prefix,
  control,
  register,
  errors,
}: {
  prefix: string;
  control: Control<T>;
  register: UseFormRegister<T>;
  errors: FieldErrors<ImportMetaValues>;
}) {
  const { t, locale } = useLocale();
  const c = control as unknown as Control<ImportMetaValues>;
  const r = register as unknown as UseFormRegister<ImportMetaValues>;
  return (
    <div className="grid gap-4 md:grid-cols-[minmax(0,2fr)_minmax(0,2fr)_12rem]">
      <FormField
        id={`${prefix}-source_url`}
        label={t("sourceExamUrl")}
        error={localizedFormMessage(errors.source_url?.message, t, locale)}
        hint={t("sourceUrlReferenceHint")}
      >
        <Input
          id={`${prefix}-source_url`}
          type="url"
          inputMode="url"
          placeholder="https://dethitiengnhat.com/jlpt/N3/…"
          aria-invalid={!!errors.source_url}
          {...r("source_url")}
        />
      </FormField>
      <FormField id={`${prefix}-title`} label={t("optionalExamName")} error={localizedFormMessage(errors.title?.message, t, locale)} hint={t("detectedTitleHint")}>
        <Input id={`${prefix}-title`} aria-invalid={!!errors.title} {...r("title")} />
      </FormField>
      <FormField id={`${prefix}-category`} label={t("examType")}>
        <Controller
          control={c}
          name="category"
          render={({ field }) => (
            <Select value={field.value || AUTO} onValueChange={(v) => field.onChange(v === AUTO ? "" : v)}>
              <SelectTrigger id={`${prefix}-category`} className="w-full">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value={AUTO}>{t("autoDetect")}</SelectItem>
                {EXAM_CATEGORIES.map((cat) => (
                  <SelectItem key={cat} value={cat}>
                    {cat === "vocabulary" ? t("vocabulary") : cat === "kanji" ? t("kanji") : cat === "grammar" ? t("grammar") : t("reading")}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          )}
        />
      </FormField>
    </div>
  );
}
