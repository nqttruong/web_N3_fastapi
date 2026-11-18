"use client";

import { AlertCircle, Inbox, RefreshCw } from "lucide-react";
import type { ReactNode } from "react";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { ApiError } from "@/lib/api/client";
import { useLocale } from "@/lib/i18n";

export function LoadingState({ rows = 3, label }: { rows?: number; label?: string }) {
  const { t } = useLocale();
  return (
    <div role="status" aria-live="polite" className="space-y-3">
      <span className="sr-only">{label ?? t("loadingGeneric")}</span>
      {Array.from({ length: rows }, (_, i) => (
        <Skeleton key={i} className="h-14 w-full" />
      ))}
    </div>
  );
}

export function EmptyState({
  title,
  description,
  action,
}: {
  title: string;
  description?: ReactNode;
  action?: ReactNode;
}) {
  return (
    <div className="flex flex-col items-center justify-center rounded-xl border border-dashed px-6 py-12 text-center">
      <Inbox className="mb-3 size-8 text-muted-foreground" aria-hidden />
      <p className="font-medium">{title}</p>
      {description ? <p className="mt-1 max-w-md text-sm text-muted-foreground">{description}</p> : null}
      {action ? <div className="mt-4">{action}</div> : null}
    </div>
  );
}

export function errorMessage(error: unknown): string {
  if (error instanceof ApiError) return error.message;
  if (error instanceof Error) return error.message;
  return "Đã xảy ra lỗi không xác định.";
}

export function ErrorState({ error, onRetry, title, notFoundTitle, retryLabel, message }: { error: unknown; onRetry?: () => void; title?: string; notFoundTitle?: string; retryLabel?: string; message?: string }) {
  const { t } = useLocale();
  const notFound = error instanceof ApiError && error.status === 404;
  return (
    <Alert variant="destructive" role="alert">
      <AlertCircle aria-hidden />
      <AlertTitle>{notFound ? notFoundTitle ?? t("notFoundGeneric") : title ?? t("loadErrorGeneric")}</AlertTitle>
      <AlertDescription>
        <p>{message ?? t("requestFailedMessage")}</p>
        {!message && error != null ? (
          <details className="mt-2 text-xs">
            <summary className="cursor-pointer">{t("errorDetails")}</summary>
            <pre className="mt-1 whitespace-pre-wrap font-sans">{errorMessage(error)}</pre>
          </details>
        ) : null}
        {onRetry && !notFound ? (
          <Button variant="outline" size="sm" className="mt-3" onClick={onRetry}>
            <RefreshCw aria-hidden /> {retryLabel ?? t("retry")}
          </Button>
        ) : null}
      </AlertDescription>
    </Alert>
  );
}
