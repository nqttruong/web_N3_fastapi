"use client";

import { keepPreviousData, useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";

import { CategoryBadge } from "@/components/badges";
import { PageHeader } from "@/components/page-header";
import { Pagination } from "@/components/pagination";
import { EmptyState, ErrorState, LoadingState } from "@/components/states";
import { Button } from "@/components/ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { api } from "@/lib/api/endpoints";
import { queryKeys } from "@/lib/api/keys";
import { formatDateTime, formatPercent } from "@/lib/format";
import { useLocale } from "@/lib/i18n";

const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export function AttemptList() {
  const { t, locale } = useLocale();
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const page = Math.max(1, Number(searchParams.get("page")) || 1);
  const rawExamId = searchParams.get("exam_id");
  const examId = rawExamId && UUID_RE.test(rawExamId) ? rawExamId : undefined;

  const params = { page, page_size: 20, exam_id: examId };
  const { data, error, isPending, refetch } = useQuery({
    queryKey: queryKeys.attempts(params),
    queryFn: () => api.listAttempts(params),
    placeholderData: keepPreviousData,
  });

  function goTo(p: number) {
    const next = new URLSearchParams(searchParams.toString());
    if (p > 1) next.set("page", String(p));
    else next.delete("page");
    const qs = next.toString();
    router.replace(qs ? `${pathname}?${qs}` : pathname, { scroll: false });
  }

  return (
    <>
      <PageHeader
        title={t("attemptsTitle")}
        description={t("attemptsDescription")}
        actions={
          examId ? (
            <Button asChild variant="outline">
              <Link href="/attempts">{t("viewAll")}</Link>
            </Button>
          ) : undefined
        }
      />
      {isPending ? (
        <LoadingState rows={5} />
      ) : error ? (
        <ErrorState error={error} onRetry={() => refetch()} />
      ) : data.data.length === 0 ? (
        <EmptyState
          title={t("noAttemptsTitle")}
          description={t("noAttemptsDescription")}
          action={
            <Button asChild size="sm" variant="outline">
              <Link href="/exams">{t("goToExamLibrary")}</Link>
            </Button>
          }
        />
      ) : (
        <>
          <div className="overflow-x-auto rounded-xl border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>{t("examTitle")}</TableHead>
                  <TableHead className="hidden md:table-cell">{t("category")}</TableHead>
                  <TableHead>{t("dateTime")}</TableHead>
                  <TableHead className="text-right">{t("correct")}</TableHead>
                  <TableHead className="text-right">{t("incorrect")}</TableHead>
                  <TableHead className="hidden text-right sm:table-cell">{t("accuracy")}</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data.data.map((a) => (
                  <TableRow key={a.id}>
                    <TableCell className="max-w-[18rem] whitespace-normal">
                      <Link href={`/attempts/${a.id}`} className="font-medium hover:underline">
                        {a.exam_title}
                      </Link>
                    </TableCell>
                    <TableCell className="hidden md:table-cell">
                      <CategoryBadge category={a.exam_category} />
                    </TableCell>
                    <TableCell className="text-muted-foreground">{formatDateTime(a.started_at, locale)}</TableCell>
                    <TableCell className="text-right tabular-nums">
                      {a.correct_count}/{a.total_questions}
                    </TableCell>
                    <TableCell className="text-right tabular-nums">{a.incorrect_count}</TableCell>
                    <TableCell className="hidden text-right tabular-nums sm:table-cell">{formatPercent(a.accuracy, locale)}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
          <Pagination meta={data.meta} onPage={goTo} />
        </>
      )}
    </>
  );
}
