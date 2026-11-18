"use client";

import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { Search } from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useEffect, useRef, useState } from "react";

import { CategoryBadge, StatusBadge } from "@/components/badges";
import { PageHeader } from "@/components/page-header";
import { Pagination } from "@/components/pagination";
import { EmptyState, ErrorState, LoadingState } from "@/components/states";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ImportList } from "@/features/imports/import-list";
import { api } from "@/lib/api/endpoints";
import { queryKeys } from "@/lib/api/keys";
import { EXAM_CATEGORIES, type ExamCategory } from "@/lib/api/types";
import { formatDateTime, formatPercent } from "@/lib/format";
import { examCategoryMessageKey } from "@/lib/localized-labels";
import { cn } from "@/lib/utils";
import { useLocale } from "@/lib/i18n";

const PAGE_SIZE = 20;

function parseCategory(value: string | null): ExamCategory | undefined {
  return EXAM_CATEGORIES.find((c) => c === value);
}

export function ExamLibrary() {
  const { t, locale } = useLocale();
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();

  const q = searchParams.get("q") ?? "";
  const category = parseCategory(searchParams.get("category"));
  const page = Math.max(1, Number(searchParams.get("page")) || 1);
  const tab = searchParams.get("tab") === "drafts" ? "drafts" : "saved";

  // Local input state; re-synced when the URL changes (e.g. back/forward navigation).
  const [searchText, setSearchText] = useState(q);
  const [syncedQ, setSyncedQ] = useState(q);
  if (q !== syncedQ) {
    setSyncedQ(q);
    setSearchText(q);
  }
  const debounce = useRef<ReturnType<typeof setTimeout>>(undefined);
  useEffect(() => () => clearTimeout(debounce.current), []);

  function updateParams(next: Record<string, string | undefined>) {
    // Read the live URL so a debounced update never overwrites a newer filter change.
    const params = new URLSearchParams(window.location.search);
    for (const [key, value] of Object.entries(next)) {
      if (value) params.set(key, value);
      else params.delete(key);
    }
    const qs = params.toString();
    router.replace(qs ? `${pathname}?${qs}` : pathname, { scroll: false });
  }

  function onSearchChange(value: string) {
    setSearchText(value);
    clearTimeout(debounce.current);
    debounce.current = setTimeout(() => updateParams({ q: value.trim() || undefined, page: undefined }), 300);
  }

  const params = { page, page_size: PAGE_SIZE, q: q || undefined, category };
  const { data, error, isPending, isFetching, refetch } = useQuery({
    queryKey: queryKeys.exams(params),
    queryFn: () => api.listExams(params),
    placeholderData: keepPreviousData,
  });

  const filtered = Boolean(q || category);

  return (
    <>
      <PageHeader
        title={t("examLibraryTitle")}
        description={t("examLibraryDescription")}
        actions={
          <details className="relative">
            <summary className="flex h-9 cursor-pointer list-none items-center rounded-md bg-primary px-4 text-sm font-medium text-primary-foreground hover:bg-primary/90 focus-visible:outline-2 focus-visible:outline-offset-2">
              {t("addExam")}
            </summary>
            <div className="absolute right-0 z-20 mt-2 grid min-w-52 gap-1 rounded-lg border bg-popover p-2 text-popover-foreground shadow-lg">
              <Link className="rounded px-3 py-2 text-sm hover:bg-muted" href="/exams/new?tab=manual">{t("createExamManual")}</Link>
              <Link className="rounded px-3 py-2 text-sm hover:bg-muted" href="/exams/new?tab=text">{t("importText")}</Link>
              <Link className="rounded px-3 py-2 text-sm hover:bg-muted" href="/exams/new?tab=html">{t("importHtml")}</Link>
              <Link className="rounded px-3 py-2 text-sm hover:bg-muted" href="/exams/new?tab=images">{t("importImage")}</Link>
              <Link className="rounded px-3 py-2 text-sm hover:bg-muted" href="/exams?tab=drafts">
                {t("extensionCapture")}
                <span className="mt-0.5 block text-xs text-muted-foreground">{t("extensionDraftHint")}</span>
              </Link>
            </div>
          </details>
        }
      />

      <Tabs value={tab} onValueChange={(value) => updateParams({ tab: value === "drafts" ? value : undefined, page: undefined })}>
        <TabsList className="mb-4 w-full sm:w-auto">
          <TabsTrigger value="saved">{t("savedExams")}</TabsTrigger>
          <TabsTrigger value="drafts">{t("importDrafts")}</TabsTrigger>
        </TabsList>
        <TabsContent value="drafts"><ImportList embedded /></TabsContent>
        <TabsContent value="saved">
      <div className="mb-4 flex flex-col gap-3 lg:flex-row lg:items-center">
        <div className="relative lg:w-80">
          <Search className="pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-muted-foreground" aria-hidden />
          <Input
            type="search"
            aria-label={t("searchExams")}
            placeholder={t("searchExamPlaceholder")}
            className="pl-8"
            value={searchText}
            onChange={(e) => onSearchChange(e.target.value)}
          />
        </div>
        <div role="group" aria-label={t("filterExamCategory")} className="flex flex-wrap gap-1.5">
          {[undefined, ...EXAM_CATEGORIES].map((value) => {
            const active = category === value;
            return (
              <Button
                key={value ?? "all"}
                size="sm"
                variant={active ? "default" : "outline"}
                aria-pressed={active}
                onClick={() => updateParams({ category: value, page: undefined })}
              >
                {value ? t(examCategoryMessageKey[value]) : t("all")}
              </Button>
            );
          })}
        </div>
      </div>

      {isPending ? (
        <LoadingState rows={5} />
      ) : error ? (
        <ErrorState error={error} onRetry={() => refetch()} />
      ) : data.data.length === 0 ? (
        filtered ? (
          <EmptyState title={t("noMatchingExam")} description={t("refineExamSearch")} />
        ) : (
          <EmptyState
            title={t("emptyExamLibrary")}
            description={t("emptyExamLibraryHint")}
            action={
              <Button asChild size="sm">
                <Link href="/exams/new">{t("addExam")}</Link>
              </Button>
            }
          />
        )
      ) : (
        <div className={cn("transition-opacity", isFetching && "opacity-60")}>
          <div className="overflow-x-auto rounded-xl border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>{t("examTitle")}</TableHead>
                  <TableHead>{t("category")}</TableHead>
                  <TableHead className="text-right">{t("questionCount")}</TableHead>
                  <TableHead className="text-right">{t("attemptCount")}</TableHead>
                  <TableHead className="hidden md:table-cell">{t("latestResult")}</TableHead>
                  <TableHead className="hidden lg:table-cell">{t("chatgptExplanations")}</TableHead>
                  <TableHead className="hidden text-right md:table-cell">{t("verifiedAnswers")}</TableHead>
                  <TableHead>{t("status")}</TableHead>
                  <TableHead className="hidden lg:table-cell">{t("createdAt")}</TableHead>
                  <TableHead>{t("actions")}</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data.data.map((exam) => (
                  <TableRow key={exam.id}>
                    <TableCell className="max-w-[20rem] whitespace-normal">
                      <Link href={`/exams/${exam.id}`} className="font-medium hover:underline">
                        {exam.title}
                      </Link>
                      <span className="ml-2 text-xs text-muted-foreground">{exam.level}</span>
                    </TableCell>
                    <TableCell>
                      <CategoryBadge category={exam.category} />
                    </TableCell>
                    <TableCell className="text-right tabular-nums">{exam.question_count}</TableCell>
                    <TableCell className="text-right tabular-nums">{exam.attempt_count ?? 0}</TableCell>
                    <TableCell className="hidden md:table-cell">
                        {exam.latest_attempt_started_at ? <span>{exam.latest_attempt_accuracy === null ? t("ungraded") : formatPercent(exam.latest_attempt_accuracy, locale)} · {formatDateTime(exam.latest_attempt_started_at, locale)}</span> : <span className="text-muted-foreground">{t("notTaken")}</span>}
                    </TableCell>
                    <TableCell className="hidden lg:table-cell">
                      {(exam.approved_explanation_count ?? 0) > 0 ? `${exam.approved_explanation_count} ${t("approvedCount")}` : <span className="text-muted-foreground">{t("none")}</span>}
                    </TableCell>
                    <TableCell className="hidden text-right tabular-nums md:table-cell">
                      {exam.verified_answer_count}/{exam.question_count}
                    </TableCell>
                    <TableCell>
                      <StatusBadge status={exam.status} />
                    </TableCell>
                    <TableCell className="hidden text-muted-foreground lg:table-cell">
                      {formatDateTime(exam.created_at, locale)}
                    </TableCell>
                    <TableCell>
                      <div className="flex flex-wrap gap-1">
                        <Button size="sm" variant="outline" asChild><Link href={`/exams/${exam.id}`}>{t("viewExam")}</Link></Button>
                        {exam.status !== "archived" && exam.question_count > 0 ? <Button size="sm" asChild><Link href={`/exams/${exam.id}/practice`}>{t("takeExam")}</Link></Button> : null}
                        <Button size="sm" variant="ghost" asChild><Link href={`/exams/${exam.id}#history`}>{t("history")}</Link></Button>
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
          <Pagination meta={data.meta} onPage={(p) => updateParams({ page: p > 1 ? String(p) : undefined })} />
        </div>
      )}
        </TabsContent>
      </Tabs>
    </>
  );
}
