"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ExternalLink, PlayCircle } from "lucide-react";
import Link from "next/link";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import { toast } from "sonner";

import { RichText } from "@/components/rich-text";
import { CategoryBadge, StatusBadge } from "@/components/badges";
import { PageHeader } from "@/components/page-header";
import { Pagination } from "@/components/pagination";
import { EmptyState, ErrorState, LoadingState, errorMessage } from "@/components/states";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { api } from "@/lib/api/endpoints";
import { queryKeys } from "@/lib/api/keys";
import { EXAM_STATUSES, type ExamStatus } from "@/lib/api/types";
import { formatDateTime, formatPercent } from "@/lib/format";
import { useLocale } from "@/lib/i18n";

import { PassageForm } from "./passage-form";
import { QuestionForm } from "./question-form";
import { QuestionList } from "./question-list";

export function ExamDetail() {
  const { t, locale } = useLocale();
  const { id } = useParams<{ id: string }>();
  const searchParams = useSearchParams();
  const router = useRouter();
  const attemptPage = Math.max(1, Number(searchParams.get("history_page")) || 1);
  const queryClient = useQueryClient();

  const exam = useQuery({ queryKey: queryKeys.exam(id), queryFn: () => api.getExam(id) });
  const questions = useQuery({ queryKey: queryKeys.questions(id), queryFn: () => api.listQuestions(id) });
  const passages = useQuery({ queryKey: queryKeys.passages(id), queryFn: () => api.listPassages(id) });
  const attemptsParams = { exam_id: id, page: attemptPage, page_size: 10 };
  const attempts = useQuery({ queryKey: queryKeys.attempts(attemptsParams), queryFn: () => api.listAttempts(attemptsParams) });

  function changeAttemptPage(page: number) {
    const next = new URLSearchParams(searchParams.toString());
    if (page > 1) next.set("history_page", String(page));
    else next.delete("history_page");
    router.replace(next.size ? `/exams/${id}?${next}` : `/exams/${id}#history`, { scroll: false });
  }

  const updateStatus = useMutation({
    mutationFn: (status: ExamStatus) => api.updateExam(id, { status }),
    onSuccess: (updated) => {
      queryClient.setQueryData(queryKeys.exam(id), updated);
      queryClient.invalidateQueries({ queryKey: queryKeys.examsRoot });
      queryClient.invalidateQueries({ queryKey: queryKeys.dashboard });
      toast.success(`${t("status")}: ${updated.status === "draft" ? t("statusDraft") : updated.status === "ready" ? t("statusReady") : t("statusArchived")}`);
    },
    onError: (e) => toast.error(errorMessage(e)),
  });

  if (exam.isPending) return <LoadingState rows={4} />;
  if (exam.error) return <ErrorState error={exam.error} onRetry={() => exam.refetch()} />;

  const data = exam.data;
  const list = questions.data?.data ?? [];
  const nextNumber = list.reduce((max, q) => Math.max(max, q.question_number), 0) + 1;
  const canPractice = data.question_count > 0 && data.status !== "archived";

  return (
    <>
      <PageHeader
        title={<span lang="ja">{data.title}</span>}
        description={
          <span className="flex flex-wrap items-center gap-2">
            <span>{data.level}</span>
            <CategoryBadge category={data.category} />
            <StatusBadge status={data.status} />
            <span>· {data.question_count} {t("questionCount")} · {data.verified_answer_count} {t("verifiedAnswers")}</span>
          </span>
        }
        actions={
          canPractice ? (
            <Button asChild>
              <Link href={`/exams/${id}/practice`}>
                <PlayCircle aria-hidden /> {t("takeExam")}
              </Link>
            </Button>
          ) : (
            <Button disabled title={data.status === "archived" ? t("takeArchivedExam") : t("examHasNoQuestions")}>
              <PlayCircle aria-hidden /> {t("takeExam")}
            </Button>
          )
        }
      />

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_22rem]">
        <div className="space-y-6">
          <section id="history" aria-labelledby="history-heading" className="scroll-mt-4">
            <h2 id="history-heading" className="mb-3 text-lg font-semibold">{t("history")}</h2>
            {attempts.isPending ? <LoadingState rows={2} /> : attempts.error ? (
              <ErrorState error={attempts.error} onRetry={() => attempts.refetch()} />
            ) : attempts.data.data.length === 0 ? (
              <EmptyState title={t("noAttempts")} description={t("attemptsEmptyHint")} action={canPractice ? <Button asChild size="sm"><Link href={`/exams/${id}/practice`}>{t("takeExam")}</Link></Button> : undefined} />
            ) : (
              <div className="space-y-3">
                {attempts.data.data.map((attempt) => (
                  <Card key={attempt.id}>
                    <CardContent className="flex flex-wrap items-center justify-between gap-3">
                      <div>
                        <p className="font-medium">{formatDateTime(attempt.started_at, locale)}</p>
                        <p className="text-sm text-muted-foreground">
                          {attempt.correct_count} {t("correct")} · {attempt.incorrect_count} {t("incorrect")} · {attempt.unanswered_count} {t("unanswered")}
                          {attempt.accuracy !== null ? ` · ${formatPercent(attempt.accuracy, locale)}` : ` · ${t("unavailable")}`}
                        </p>
                        <p className="text-xs text-muted-foreground">
                          {t("latestExplanationStatus")}: {(attempt.approved_explanation_count ?? 0) > 0 ? `${attempt.approved_explanation_count} ${t("approvedChatgptExplanation")}` : (attempt.pending_explanation_count ?? 0) > 0 ? t("pendingApproval") : t("noCurrentExplanation")}
                        </p>
                      </div>
                      <div className="flex flex-wrap gap-2">
                        <Button size="sm" variant="outline" asChild><Link href={`/attempts/${attempt.id}`}>{t("viewResult")}</Link></Button>
                        <Button size="sm" asChild><Link href={`/attempts/${attempt.id}#ai-review`}>{t("reviewChatgpt")}</Link></Button>
                      </div>
                    </CardContent>
                  </Card>
                ))}
                <Pagination meta={attempts.data.meta} onPage={changeAttemptPage} />
              </div>
            )}
          </section>

          <section aria-labelledby="questions-heading">
            <h2 id="questions-heading" className="mb-3 text-lg font-semibold">
              {t("questionsList")}
            </h2>
            {questions.isPending ? (
              <LoadingState />
            ) : questions.error ? (
              <ErrorState error={questions.error} onRetry={() => questions.refetch()} />
            ) : list.length === 0 ? (
              <EmptyState title={t("examHasNoQuestions")} description={t("addQuestionHint")} />
            ) : (
              <QuestionList questions={list} passages={passages.data ?? []} />
            )}
          </section>

          {passages.data && passages.data.length > 0 ? (
            <section aria-labelledby="passages-heading">
              <h2 id="passages-heading" className="mb-3 text-lg font-semibold">
                {t("passages")}
              </h2>
              <ol className="space-y-3">
                {passages.data.map((p, i) => (
                  <li key={p.id} className="rounded-xl border bg-muted/30 p-4">
                    <p className="mb-1 text-xs font-medium text-muted-foreground">{t("passageNumber")} {i + 1}</p>
                    <p lang="ja" className="leading-relaxed whitespace-pre-wrap">
                      <RichText text={p.content} />
                    </p>
                  </li>
                ))}
              </ol>
            </section>
          ) : null}

          <Card>
            <CardHeader>
              <CardTitle>{t("addQuestion")}</CardTitle>
              <CardDescription>{t("questionFormHint")}</CardDescription>
            </CardHeader>
            <CardContent>
              {questions.isPending || passages.isPending ? (
                <LoadingState rows={2} />
              ) : (
                <QuestionForm
                  key={`${nextNumber}-${passages.data?.length ?? 0}`}
                  examId={id}
                  category={data.category}
                  nextNumber={nextNumber}
                  passages={passages.data ?? []}
                />
              )}
            </CardContent>
          </Card>
        </div>

        <aside className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>{t("examInfo")}</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4 text-sm">
              {data.description ? <p className="whitespace-pre-wrap">{data.description}</p> : null}
              <dl className="space-y-2">
                <div>
                  <dt className="text-muted-foreground">{t("source")}</dt>
                  <dd className="break-all">
                    {data.source_url ? (
                      <a href={data.source_url} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 hover:underline">
                        {data.source_name ?? data.source_url} <ExternalLink className="size-3.5" aria-hidden />
                      </a>
                    ) : (
                      (data.source_name ?? t("sourceNotAvailable"))
                    )}
                  </dd>
                </div>
                <div>
                  <dt className="text-muted-foreground">{t("created")}</dt>
                  <dd>{formatDateTime(data.created_at, locale)}</dd>
                </div>
                <div>
                  <dt className="text-muted-foreground">{t("updated")}</dt>
                  <dd>{formatDateTime(data.updated_at, locale)}</dd>
                </div>
              </dl>
              <div className="space-y-1.5">
                <label htmlFor="exam-status" className="text-muted-foreground">
                  {t("status")}
                </label>
                <Select
                  value={data.status}
                  disabled={updateStatus.isPending}
                  onValueChange={(v) => updateStatus.mutate(v as ExamStatus)}
                >
                  <SelectTrigger id="exam-status" className="w-full">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {EXAM_STATUSES.map((s) => (
                      <SelectItem key={s} value={s}>
                        {s === "draft" ? t("statusDraft") : s === "ready" ? t("statusReady") : t("statusArchived")}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <p className="text-xs text-muted-foreground">{t("attemptHistoryAndReview")}</p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>{t("addPassage")}</CardTitle>
              <CardDescription>{t("addPassageHint")}</CardDescription>
            </CardHeader>
            <CardContent>
              <PassageForm examId={id} />
            </CardContent>
          </Card>
        </aside>
      </div>
    </>
  );
}
