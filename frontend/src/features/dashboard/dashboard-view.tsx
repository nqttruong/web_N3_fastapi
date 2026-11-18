"use client";

import { useQuery } from "@tanstack/react-query";
import { BookOpenCheck, Bookmark, RotateCcw } from "lucide-react";
import type { ComponentType } from "react";

import { PageHeader } from "@/components/page-header";
import { ErrorState, LoadingState } from "@/components/states";
import { Card, CardContent } from "@/components/ui/card";
import { formatDateTime } from "@/lib/format";
import { useLocale } from "@/lib/i18n";
import { studyApi, type StudyOverview, type StudyType } from "@/features/learning-content/study-api";
import { JapaneseQuote } from "./japanese-quote";

const CONTENT_TYPES: { type: StudyType; icon: ComponentType<{ className?: string }> }[] = [
  { type: "vocabulary", icon: BookOpenCheck },
  { type: "kanji", icon: BookOpenCheck },
  { type: "grammar", icon: BookOpenCheck },
];

function Metric({ label, value, icon: Icon }: { label: string; value: number; icon: ComponentType<{ className?: string }> }) {
  return (
    <Card size="sm">
      <CardContent className="flex min-h-24 items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-sm text-muted-foreground">{label}</p>
          <p className="mt-1 text-2xl font-semibold tabular-nums">{value}</p>
        </div>
        <Icon aria-hidden className="size-5 shrink-0 text-muted-foreground" />
      </CardContent>
    </Card>
  );
}

function LearningSnapshot({ data }: { data: StudyOverview }) {
  const { t, locale } = useLocale();
  return (
    <div className="space-y-6">
      <section aria-label={t("learningOverview")} className="grid gap-3 sm:grid-cols-3">
        <Metric label={t("learned")} value={data.learned} icon={BookOpenCheck} />
        <Metric label={t("dueToday")} value={data.due} icon={RotateCcw} />
        <Metric label={t("saved")} value={data.saved} icon={Bookmark} />
      </section>

      <section aria-labelledby="overview-content-progress" className="space-y-3">
        <h2 id="overview-content-progress" className="text-lg font-semibold">{t("contentProgress")}</h2>
        <div className="grid gap-3 sm:grid-cols-3">
          {CONTENT_TYPES.map(({ type, icon: Icon }) => {
            const total = data.content_counts[type] ?? 0;
            const learned = data.learned_by_type[type] ?? 0;
            const value = total > 0 ? Math.min(100, Math.round((learned / total) * 100)) : 0;
            return (
              <Card key={type}>
                <CardContent className="space-y-3">
                  <div className="flex items-center justify-between gap-3">
                    <h3 className="flex min-w-0 items-center gap-2 font-medium"><Icon aria-hidden className="size-4 shrink-0 text-primary" />{t(type)}</h3>
                    <span className="shrink-0 text-sm tabular-nums text-muted-foreground">{learned}/{total}</span>
                  </div>
                  <div
                    role="progressbar"
                    aria-label={`${t(type)} · ${t("learned")}`}
                    aria-valuemin={0}
                    aria-valuemax={total}
                    aria-valuenow={Math.min(learned, total)}
                    className="h-2 overflow-hidden rounded-full bg-muted"
                  >
                    <div className="h-full rounded-full bg-primary transition-[width]" style={{ width: `${value}%` }} />
                  </div>
                  <p className="text-xs text-muted-foreground">{value}%</p>
                </CardContent>
              </Card>
            );
          })}
        </div>
      </section>

      <section aria-labelledby="overview-recent-activity" className="space-y-3">
        <h2 id="overview-recent-activity" className="text-lg font-semibold">{t("recentActivity")}</h2>
        {data.recent_activity.length ? (
          <Card>
            <CardContent>
              <ul className="divide-y">
                {data.recent_activity.slice(0, 5).map((activity) => (
                  <li key={`${activity.item_id}-${activity.reviewed_at}`} className="flex flex-wrap items-center justify-between gap-x-4 gap-y-1 py-3 first:pt-0 last:pb-0">
                    <div className="min-w-0">
                      <p lang={activity.item_type === "vocabulary" || activity.item_type === "kanji" || activity.item_type === "grammar" ? "ja" : undefined} className="break-words font-medium">{activity.title}</p>
                      <p className="text-xs text-muted-foreground">{t(activity.item_type)}</p>
                    </div>
                    <time dateTime={activity.reviewed_at} className="text-xs text-muted-foreground">{formatDateTime(activity.reviewed_at, locale)}</time>
                  </li>
                ))}
              </ul>
            </CardContent>
          </Card>
        ) : (
          <Card><CardContent><p className="text-sm text-muted-foreground">{t("noStudyActivity")}</p></CardContent></Card>
        )}
      </section>
    </div>
  );
}

export function DashboardView() {
  const { t } = useLocale();
  const overview = useQuery({ queryKey: ["study-overview"], queryFn: studyApi.overview });

  return (
    <>
      <PageHeader title={t("overview")} description={t("welcome")} />
      <div className="mb-6"><JapaneseQuote /></div>
      {overview.isPending ? <LoadingState rows={4} /> : overview.error ? <ErrorState error={overview.error} onRetry={() => overview.refetch()} /> : <LearningSnapshot data={overview.data} />}
    </>
  );
}
