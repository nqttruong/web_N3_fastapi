"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";

import { EmptyState, ErrorState, LoadingState } from "@/components/states";
import { PageHeader } from "@/components/page-header";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { api } from "@/lib/api/endpoints";
import { formatDateTime, formatPercent } from "@/lib/format";
import { useLocale } from "@/lib/i18n";

export function JlptAnalyticsView({ embedded = false }: { embedded?: boolean }) {
  const { t, locale } = useLocale();
  const result = useQuery({ queryKey: ["analytics", "jlpt"], queryFn: api.jlptAnalytics });
  if (result.isPending) return <LoadingState rows={5} />;
  if (result.error) return <ErrorState error={result.error} onRetry={() => result.refetch()} />;
  const data = result.data;
  return <>
    {!embedded && <PageHeader title={t("analytics")} description={t("jlptAnalyticsDescription")} actions={<Button asChild variant="outline"><Link href="/exams">{t("openExamLibraryButton")}</Link></Button>} />}
    {data.attempt_count === 0 ? <EmptyState title={t("noExamAnalytics")} description={t("noExamAnalyticsHint")} action={<Button asChild><Link href="/exams">{t("chooseExam")}</Link></Button>} /> : <>
      {!embedded && <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Stat title={t("examCount")} value={data.attempt_count} />
        <Stat title={t("gradedAccuracy")} value={formatPercent(data.accuracy, locale)} />
        <Stat title={t("correctWrong")} value={data.correct + " / " + data.incorrect} />
        <Stat title={t("averageDuration")} value={data.average_duration_seconds === null ? t("unavailable") : Math.floor(data.average_duration_seconds / 60) + " " + t("minutes")} />
      </div>}
      <p className="mt-3 text-sm text-muted-foreground">{t("scoreDefinitions")}{formatPercent(data.correct_over_all, locale)}. {t("unansweredLabel")} ({data.unanswered}) · {t("ungradedLabel")} ({data.ungraded}).</p>
      <div className="mt-6 grid gap-5 lg:grid-cols-2">
        <Card>
          <CardHeader><CardTitle>{t("skillResults")}</CardTitle></CardHeader>
          <CardContent className="space-y-3">
            {Object.entries(data.skill_results).map(([skill, stats]) => <div key={skill} className="flex items-center justify-between gap-3 border-b pb-2 last:border-0">
              <span>{skill === "vocabulary" ? t("vocabulary") : skill === "kanji" ? t("kanji") : skill === "grammar" ? t("grammar") : skill === "reading" ? t("reading") : skill}</span>
              <span className="text-sm tabular-nums text-muted-foreground">{stats.correct} {t("correct")} · {stats.incorrect} {t("incorrect")} · {stats.unanswered} {t("unanswered")} · {stats.ungraded} {t("ungraded")}</span>
            </div>)}
            <p className="text-xs text-muted-foreground">{t("androidSkillGap")}</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader><CardTitle>{t("weeklyTrend")}</CardTitle></CardHeader>
          <CardContent>
            {data.trend.length === 0 ? <p className="text-sm text-muted-foreground">{t("noTrend")}</p> : <div className="overflow-x-auto"><table className="w-full text-sm"><thead><tr className="border-b text-left"><th className="py-2 pr-3">{t("week")}</th><th className="py-2 pr-3">{t("examCount")}</th><th className="py-2 pr-3">{t("correct")}</th><th className="py-2">{t("incorrect")}</th></tr></thead><tbody>{data.trend.map((point) => <tr key={point.week} className="border-b last:border-0"><td className="py-2 pr-3">{point.week}</td><td className="py-2 pr-3">{point.attempts}</td><td className="py-2 pr-3">{point.correct}</td><td className="py-2">{point.incorrect}</td></tr>)}</tbody></table></div>}
          </CardContent>
        </Card>
        <Card>
          <CardHeader><CardTitle>{t("examRepetitions")}</CardTitle></CardHeader>
          <CardContent>
            {data.repeated_exams.length === 0 ? <p className="text-sm text-muted-foreground">{t("noAnalyticsData")}</p> : <ul className="divide-y">{data.repeated_exams.map((exam) => <li key={exam.exam_id} className="flex items-center justify-between gap-3 py-3"><Link className="min-w-0 truncate font-medium hover:underline" href={"/exams/" + exam.exam_id}>{exam.exam_title}</Link><span className="shrink-0 text-sm text-muted-foreground">{exam.attempts} {t("repetitions")} · {formatDateTime(exam.latest_at, locale)}</span></li>)}</ul>}
          </CardContent>
        </Card>
        <Card>
          <CardHeader><CardTitle>{t("dataSources")}</CardTitle></CardHeader>
          <CardContent className="space-y-2 text-sm">
            {Object.entries(data.sources).map(([source, count]) => <p key={source}>{source === "import" ? t("importedAttempt") : t("webAttempt")}: {count}</p>)}
            <p className="text-muted-foreground">{t("androidAttemptSyncGap")}</p>
          </CardContent>
        </Card>
      </div>
    </>}
  </>;
}

function Stat({ title, value }: { title: string; value: string | number }) {
  return <Card size="sm"><CardContent><p className="text-sm text-muted-foreground">{title}</p><p className="mt-1 text-2xl font-semibold tabular-nums">{value}</p></CardContent></Card>;
}
