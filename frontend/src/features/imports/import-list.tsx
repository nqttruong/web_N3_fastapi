"use client";

import { keepPreviousData, useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";

import { PageHeader } from "@/components/page-header";
import { Pagination } from "@/components/pagination";
import { EmptyState, ErrorState, LoadingState } from "@/components/states";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api/endpoints";
import { queryKeys } from "@/lib/api/keys";
import { formatDateTime } from "@/lib/format";
import { useLocale } from "@/lib/i18n";

export function ImportList({ embedded = false }: { embedded?: boolean }) {
  const { t, locale } = useLocale();
  const [page, setPage] = useState(1);
  const params = { page, page_size: 20 };
  const { data, error, isPending, refetch } = useQuery({
    queryKey: queryKeys.imports(params),
    queryFn: () => api.listImports(params),
    placeholderData: keepPreviousData,
  });
  return (
    <>
      {!embedded ? <PageHeader
        title={t("importDrafts")}
        description={t("importDraftsDescription")}
        actions={
          <Button asChild>
            <Link href="/exams/new">{t("newImport")}</Link>
          </Button>
        }
      /> : null}
      {isPending ? (
        <LoadingState rows={4} />
      ) : error ? (
        <ErrorState error={error} onRetry={() => refetch()} />
      ) : data.data.length === 0 ? (
        <EmptyState title={t("noImportDrafts")} description={t("noImportDraftsHint")} />
      ) : (
        <>
          <div className="space-y-3" data-testid="import-drafts">
            {data.data.map((d) => (
              <article key={d.id} className="rounded-xl border p-4">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div className="min-w-0">
                    <Link href={`/imports/${d.id}`} className="font-medium hover:underline" lang="ja">
                      {d.title || d.source_url || t("untitledDraft")}
                    </Link>
                    <p className="mt-1 text-sm text-muted-foreground">
                      {(d.method === "text" ? t("importText") : d.method === "html" ? t("importHtml") : d.method === "images" ? t("importImage") : t("extensionCapture"))} · {d.question_count} {t("recognizedQuestions")} · {t("importedAt")} {formatDateTime(d.created_at, locale)}
                    </p>
                    {d.source_url && d.title ? <p className="mt-1 truncate text-xs text-muted-foreground">{t("source")}: {d.source_url}</p> : null}
                  </div>
                  <Badge variant={d.status === "committed" ? "default" : d.status === "failed" ? "destructive" : "outline"}>
                    {d.status === "uploaded" ? t("importUploaded") : d.status === "parsing" ? t("importParsing") : d.status === "needs_review" ? t("importNeedsReview") : d.status === "ready" ? t("importReady") : d.status === "committed" ? t("importCommitted") : t("importFailed")}
                  </Badge>
                </div>
                {d.error_message ? (
                  <details className="mt-3 text-sm text-destructive">
                    <summary className="cursor-pointer">{t("importFailed")} · {t("errorDetails")}</summary>
                    <p className="mt-1 whitespace-pre-wrap">{d.error_message}</p>
                  </details>
                ) : null}
                {d.issues.length ? (
                  <details className="mt-3 text-sm text-amber-700 dark:text-amber-400">
                    <summary className="cursor-pointer">{t("issuesToReview")} ({d.issues.length}) · {t("errorDetails")}</summary>
                    <ul className="mt-1 list-inside list-disc space-y-1" aria-label={t("issuesToReview")}>
                      {d.issues.slice(0, 3).map((issue, index) => <li key={`${issue.code}-${index}`}>{issue.message}</li>)}
                      {d.issues.length > 3 ? <li>{t("moreImportIssues").replace("{count}", String(d.issues.length - 3))}</li> : null}
                    </ul>
                  </details>
                ) : !d.error_message ? <p className="mt-3 text-sm text-muted-foreground">{t("noRecentValidationIssues")}</p> : null}
                <div className="mt-4 flex flex-wrap gap-2">
                  <Button size="sm" asChild><Link href={`/imports/${d.id}`}>{t("preview")}</Link></Button>
                  <Button size="sm" variant="outline" asChild><Link href={`/imports/${d.id}`}>{t("edit")}</Link></Button>
                  {d.status === "ready" ? <Button size="sm" variant="outline" asChild><Link href={`/imports/${d.id}`}>{t("previewToSave")}</Link></Button> : null}
                  {d.exam_id ? <Button size="sm" variant="ghost" asChild><Link href={`/exams/${d.exam_id}`}>{t("openSavedExam")}</Link></Button> : null}
                </div>
              </article>
            ))}
          </div>
          <Pagination meta={data.meta} onPage={setPage} />
        </>
      )}
    </>
  );
}
