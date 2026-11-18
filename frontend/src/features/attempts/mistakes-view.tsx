"use client";

import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import Link from "next/link";

import { EmptyState, ErrorState, LoadingState } from "@/components/states";
import { PageHeader } from "@/components/page-header";
import { Pagination } from "@/components/pagination";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { api } from "@/lib/api/endpoints";
import { formatDateTime } from "@/lib/format";
import { questionTypeMessageKey } from "@/lib/localized-labels";
import type { Mistake } from "@/lib/api/types";
import { useLocale } from "@/lib/i18n";

function ApprovedExplanation({ mistake }: { mistake: Mistake }) {
  const { t } = useLocale();
  const result = useQuery({
    queryKey: ["mistake-explanation", mistake.question_id, mistake.latest_attempt_answer_id],
    queryFn: () => api.questionExplanations(mistake.question_id, mistake.latest_attempt_answer_id),
  });
  const approved = result.data?.versions.find(
    (item) => item.id === result.data?.current_id && item.status === "approved" && item.is_current && !item.stale,
  );
  if (result.isPending) return <p className="text-xs text-muted-foreground">{t("loadingApprovedExplanation")}</p>;
  if (result.error) return <p className="text-xs text-muted-foreground">{t("explanationStatusLoadError")}</p>;
  return approved?.payload ? (
    <div className="rounded-lg bg-muted/40 p-3 text-sm">
      <p className="mb-1 font-medium">{t("approvedChatgptExplanation")}</p>
      <p className="whitespace-pre-wrap">{approved.payload.correct_explanation}</p>
      <Button asChild size="sm" variant="link" className="px-0">
        <Link href={"/questions/" + mistake.question_id + "/explanation"}>{t("fullExplanation")}</Link>
      </Button>
    </div>
  ) : <p className="text-xs text-muted-foreground">{t("noCurrentApprovedExplanation")}</p>;
}

export function MistakesView() {
  const { t, locale } = useLocale();
  const [page, setPage] = useState(1);
  const [skill, setSkill] = useState("all");
  const [examId, setExamId] = useState("all");
  const [search, setSearch] = useState("");
  const [query, setQuery] = useState("");
  const exams = useQuery({ queryKey: ["mistake-exams"], queryFn: () => api.listExams({ page_size: 100 }) });
  const result = useQuery({
    queryKey: ["mistakes", page, skill, examId, query],
    queryFn: () => api.listMistakes({
      page, page_size: 20,
      ...(skill !== "all" ? { skill } : {}),
      ...(examId !== "all" ? { exam_id: examId } : {}),
      ...(query ? { q: query } : {}),
    }),
  });

  return <>
    <PageHeader title={t("mistakesTitle")} description={t("mistakesDescription")} />
    <form className="mb-5 grid gap-3 sm:grid-cols-[minmax(12rem,1fr)_12rem_12rem_auto]" onSubmit={(event) => { event.preventDefault(); setPage(1); setQuery(search.trim()); }}>
      <Input aria-label={t("searchQuestionOrExam")} placeholder={t("searchQuestionOrExam")} value={search} onChange={(event) => setSearch(event.target.value)} />
      <Select value={skill} onValueChange={(value) => { setSkill(value); setPage(1); }}>
        <SelectTrigger aria-label={t("filterSkill")}><SelectValue placeholder={t("allSkills")} /></SelectTrigger>
        <SelectContent><SelectItem value="all">{t("allSkills")}</SelectItem><SelectItem value="vocabulary">{t("vocabulary")}</SelectItem><SelectItem value="kanji">{t("kanji")}</SelectItem><SelectItem value="grammar">{t("grammar")}</SelectItem><SelectItem value="reading">{t("reading")}</SelectItem></SelectContent>
      </Select>
      <Select value={examId} onValueChange={(value) => { setExamId(value); setPage(1); }}>
        <SelectTrigger aria-label={t("filterByExam")}><SelectValue placeholder={t("allExams")} /></SelectTrigger>
        <SelectContent><SelectItem value="all">{t("allExams")}</SelectItem>{(exams.data?.data ?? []).map((exam) => <SelectItem key={exam.id} value={exam.id}>{exam.title}</SelectItem>)}</SelectContent>
      </Select>
      <Button type="submit" variant="outline">{t("searchButton")}</Button>
    </form>
    {result.isPending ? <LoadingState rows={4} /> : result.error ? <ErrorState error={result.error} onRetry={() => result.refetch()} /> : result.data.data.length === 0 ? (
      <EmptyState title={t("noGradedMistakes")} description={t("noGradedMistakesHint")} action={<Button asChild variant="outline"><Link href="/exams">{t("openExamLibrary")}</Link></Button>} />
    ) : <>
      <p className="mb-3 text-sm text-muted-foreground">{result.data.meta.total} {t("distinctWrongQuestions")}</p>
      <div className="space-y-3">
        {result.data.data.map((mistake) => <Card key={mistake.question_id} data-testid="mistake-card">
          <CardContent className="space-y-3">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div className="min-w-0">
                <p className="text-sm text-muted-foreground">{mistake.exam_title} · {t("question")} {mistake.question_number} · {t(questionTypeMessageKey[mistake.question_type])}</p>
                <p className="mt-1 whitespace-pre-wrap font-medium" lang="ja">{mistake.question_text}</p>
                <p className="mt-1 text-sm text-muted-foreground">{t("incorrect")} {mistake.occurrences} {t("wrongOccurrences")} · {t("latestWrong")} {formatDateTime(mistake.last_wrong_at, locale)}</p>
              </div>
              <span className="rounded-full border px-2 py-1 text-xs">{t("aggregatedMistake")}</span>
            </div>
            <div className="grid gap-2 sm:grid-cols-2">
              {mistake.options.map((option, index) => <p key={index} className={"rounded-md border px-3 py-2 text-sm " + (index + 1 === mistake.latest_selected_answer ? "border-destructive bg-destructive/5 " : "") + (index + 1 === mistake.correct_answer_at_submission ? "border-primary bg-primary/5" : "")}>
                {index + 1}. {option}{index + 1 === mistake.latest_selected_answer ? ` · ${t("latestSelection")}` : ""}{index + 1 === mistake.correct_answer_at_submission ? ` · ${t("gradedAnswer")}` : ""}
              </p>)}
            </div>
            {mistake.correct_answer_at_submission === null ? <p className="text-sm text-muted-foreground">{t("noVerifiedAnswerSnapshot")}</p> : null}
            <ApprovedExplanation mistake={mistake} />
            <div className="flex flex-wrap gap-2">
              <Button asChild size="sm" variant="outline"><Link href={"/attempts/" + mistake.latest_attempt_id}>{t("openSourceAttempt")}</Link></Button>
              <Button asChild size="sm"><Link href={"/attempts/" + mistake.latest_attempt_id + "#ai-review"}>{t("chatgptCorrectMistake")}</Link></Button>
            </div>
          </CardContent>
        </Card>)}
      </div>
      <div className="mt-5"><Pagination meta={result.data.meta} onPage={setPage} /></div>
    </>}
  </>;
}
