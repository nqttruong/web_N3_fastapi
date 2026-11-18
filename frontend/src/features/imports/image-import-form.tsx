"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { ArrowDown, ArrowUp, ImagePlus, Info, X } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { useForm } from "react-hook-form";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { api } from "@/lib/api/endpoints";
import type { ImportCapabilities } from "@/lib/api/types";
import { useLocale } from "@/lib/i18n";
import { checkImages, IMAGE_TYPES, importMetaSchema, toImportMeta, type ImportMetaValues } from "@/lib/import-schemas";
import { localizedFormMessage } from "@/lib/localized-form-message";

import { SourceFields } from "./source-fields";
import { useStartImport } from "./use-start-import";

export function ImageImportForm({ capabilities }: { capabilities: ImportCapabilities }) {
  const { t, locale } = useLocale();
  const { ocr, limits } = capabilities;
  const [files, setFiles] = useState<File[]>([]);
  const [fileErrors, setFileErrors] = useState<string[]>([]);
  const previews = useMemo(() => files.map((f) => URL.createObjectURL(f)), [files]);
  useEffect(() => () => previews.forEach((u) => URL.revokeObjectURL(u)), [previews]);

  const form = useForm<ImportMetaValues>({
    resolver: zodResolver(importMetaSchema),
    defaultValues: { source_url: "", title: "", category: "" },
  });
  const start = useStartImport((v: ImportMetaValues) => api.importImages(files, toImportMeta(v)));

  function addFiles(list: FileList | null) {
    if (!list) return;
    const { ok, errors } = checkImages([...files, ...Array.from(list)], {
      maxImages: limits.max_images,
      maxBytes: limits.max_image_bytes,
    });
    setFiles(ok.slice(0, limits.max_images));
    setFileErrors(errors);
  }

  function move(index: number, delta: number) {
    setFiles((prev) => {
      const next = [...prev];
      const [item] = next.splice(index, 1);
      next.splice(index + delta, 0, item!);
      return next;
    });
  }

  return (
    <form
      noValidate
      aria-label={t("importImage")}
      className="space-y-5"
      onSubmit={form.handleSubmit((v) => {
        if (files.length === 0) return setFileErrors([t("imageNotSelected")]);
        start.mutate(v);
      })}
    >
      {ocr.available ? (
        <Alert>
          <Info aria-hidden />
          <AlertTitle>{t("ocrAvailable")} ({ocr.engine}, {ocr.languages.join(", ")})</AlertTitle>
          <AlertDescription>{t("ocrReviewCaveat")}</AlertDescription>
        </Alert>
      ) : (
        <Alert variant="destructive">
          <Info aria-hidden />
          <AlertTitle>{t("ocrUnavailable")}</AlertTitle>
          <AlertDescription>
            <p>{ocr.reason}</p>
            <p className="mt-1">{t("imageFallbackTabs")}</p>
          </AlertDescription>
        </Alert>
      )}

      <SourceFields prefix="img" control={form.control} register={form.register} errors={form.formState.errors} />

      <div className="space-y-2">
        <Label htmlFor="import-images">{t("imageByReadingOrder")}</Label>
        <label
          htmlFor="import-images"
          className="flex cursor-pointer flex-col items-center justify-center gap-2 rounded-xl border border-dashed px-4 py-8 text-center text-sm text-muted-foreground hover:bg-muted/40"
        >
          <ImagePlus className="size-6" aria-hidden />
          <span>
            {t("chooseImagesHint").replace("{count}", String(limits.max_images)).replace("{size}", String(Math.round(limits.max_image_bytes / 1024 / 1024)))}
          </span>
          <input
            id="import-images"
            type="file"
            multiple
            accept={IMAGE_TYPES.join(",")}
            className="sr-only"
            disabled={!ocr.available}
            onChange={(e) => {
              addFiles(e.target.files);
              e.target.value = "";
            }}
          />
        </label>
        {fileErrors.length > 0 ? (
          <ul role="alert" className="list-disc pl-5 text-sm text-destructive">
            {fileErrors.map((e) => (
              <li key={e}>{localizedFormMessage(e, t, locale)}</li>
            ))}
          </ul>
        ) : null}
        {files.length > 0 ? (
          <ol className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3" aria-label={t("selectedImages")}>
            {files.map((file, i) => (
              <li key={`${file.name}-${i}`} className="flex gap-3 rounded-lg border p-2">
                {/* eslint-disable-next-line @next/next/no-img-element -- local object URL preview */}
                <img src={previews[i]} alt={`${t("selectedImages")} ${i + 1}`} className="h-20 w-16 shrink-0 rounded object-cover object-top" />
                <div className="min-w-0 flex-1 text-xs">
                  <p className="font-medium">#{i + 1}</p>
                  <p className="truncate text-muted-foreground">{file.name}</p>
                  <p className="text-muted-foreground">{Math.round(file.size / 1024)} KB</p>
                  <div className="mt-1 flex gap-1">
                    <Button type="button" size="icon-xs" variant="outline" aria-label={`${t("moveImageUp")} ${i + 1}`} disabled={i === 0} onClick={() => move(i, -1)}>
                      <ArrowUp />
                    </Button>
                    <Button type="button" size="icon-xs" variant="outline" aria-label={`${t("moveImageDown")} ${i + 1}`} disabled={i === files.length - 1} onClick={() => move(i, 1)}>
                      <ArrowDown />
                    </Button>
                    <Button type="button" size="icon-xs" variant="ghost" aria-label={`${t("removeImage")} ${i + 1}`} onClick={() => setFiles((p) => p.filter((_, j) => j !== i))}>
                      <X />
                    </Button>
                  </div>
                </div>
              </li>
            ))}
          </ol>
        ) : null}
      </div>

      <div className="flex justify-end">
        <Button type="submit" disabled={!ocr.available || start.isPending || files.length === 0}>
          {start.isPending ? t("recognizingText") : t("uploadRecognize")}
        </Button>
      </div>
    </form>
  );
}
