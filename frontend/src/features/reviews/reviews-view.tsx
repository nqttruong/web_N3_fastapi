"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";
import { toast } from "sonner";

import { PageHeader } from "@/components/page-header";
import { EmptyState, ErrorState, LoadingState } from "@/components/states";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { api } from "@/lib/api/endpoints";
import { queryKeys } from "@/lib/api/keys";
import type { Rating, ReviewCard } from "@/lib/api/types";
import { useLocale } from "@/lib/i18n";

const RATINGS: Rating[] = ["again", "hard", "good", "easy"];
const reviewTypeKeys = { original_question: "reviewTypeOriginalQuestion", knowledge_recall: "reviewTypeKnowledgeRecall", contrast: "reviewTypeContrast" } as const;
const srsStateKeys = { new: "srsNew", learning: "srsLearning", review: "srsReview", mastered: "srsMastered" } as const;

export function ReviewsView() {
  const { t, locale } = useLocale();
  const params = useSearchParams();
  const router = useRouter();
  const queryClient = useQueryClient();
  const sessionId = params.get("session");
  const [reveals, setReveals] = useState<Record<string, Record<string, unknown>>>({});
  const dateLocale = locale === "ja" ? "ja-JP" : locale === "en" ? "en-US" : "vi-VN";
  const ratingLabel = (rating: Rating) => t(rating === "again" ? "forgotten" : rating);

  const due = useQuery({ queryKey: queryKeys.reviews("due"), queryFn: () => api.listReviews("due") });
  const progress = useQuery({ queryKey: queryKeys.reviewProgress, queryFn: () => api.reviewProgress(30) });
  const session = useQuery({
    queryKey: queryKeys.reviewSession(sessionId ?? ""),
    queryFn: () => api.getReviewSession(sessionId!),
    enabled: !!sessionId,
  });

  useEffect(() => {
    if (!sessionId || !session.data) return;
    let active = true;
    const missing = session.data.cards.filter((card) => card.answered && !reveals[card.card_id]);
    if (missing.length) {
      void Promise.all(missing.map((card) => api.answerCard(sessionId, card.card_id, card.selected_index)))
        .then((values) => {
          if (!active) return;
          setReveals((current) => {
            const next = { ...current };
            missing.forEach((card, index) => { next[card.card_id] = values[index]!.reveal; });
            return next;
          });
        })
        .catch(() => undefined);
    }
    return () => { active = false; };
  }, [reveals, session.data, sessionId]);

  const start = useMutation({
    mutationFn: () => api.createReviewSession(20),
    onSuccess: (value) => {
      if (value.cards.length === 0) {
        toast.info(t("noDueCards"));
        return;
      }
      setReveals({});
      router.replace(`/reviews?session=${value.id}`);
      queryClient.setQueryData(queryKeys.reviewSession(value.id), value);
    },
    onError: () => toast.error(t("sessionCreateError")),
  });

  const answer = useMutation({
    mutationFn: ({ card, selected }: { card: ReviewCard; selected: number | null }) => api.answerCard(sessionId!, card.card_id, selected),
    onSuccess: (value, { card }) => {
      setReveals((current) => ({ ...current, [card.card_id]: value.reveal }));
      queryClient.setQueryData<{ id: string; cards: ReviewCard[] }>(queryKeys.reviewSession(sessionId!), (current) => current && ({ ...current, cards: current.cards.map((item) => item.card_id === card.card_id ? value.card : item) }));
    },
    onError: () => toast.error(t("answerSubmitError")),
  });

  const rate = useMutation({
    mutationFn: ({ card, rating }: { card: ReviewCard; rating: Rating }) => api.rateReview({
      request_id: crypto.randomUUID(), review_item_id: card.review_item_id, rating,
      timezone: Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC", session_id: sessionId!, card_id: card.card_id,
    }),
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: queryKeys.reviewSession(sessionId!) }),
        queryClient.invalidateQueries({ queryKey: queryKeys.reviewsRoot }),
        queryClient.invalidateQueries({ queryKey: queryKeys.reviewProgress }),
        queryClient.invalidateQueries({ queryKey: queryKeys.knowledgeRoot }),
      ]);
      toast.success(t("ratingSaveSuccess"));
    },
    onError: () => toast.error(t("ratingSaveError")),
  });

  return (
    <>
      <PageHeader title={t("reviewTitle")} description={t("reviewDescription")} actions={sessionId ? <Button variant="outline" onClick={() => router.replace("/reviews")}>{t("exitSession")}</Button> : <Button onClick={() => start.mutate()} disabled={start.isPending || (due.data?.items.length ?? 0) === 0}>{start.isPending ? t("creatingSession") : `${t("reviewDueAction")}${due.data ? ` (${due.data.items.length})` : ""}`}</Button>} />

      {progress.isPending ? <LoadingState rows={1} label={t("loadingReviews")} /> : progress.error ? <ErrorState error={progress.error} title={t("learningLoadError")} notFoundTitle={t("learningDataNotFound")} message={t("learningLoadError")} retryLabel={t("retry")} onRetry={() => progress.refetch()} /> : (
        <div className="mb-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-4" data-testid="review-progress">
          <Stat label={t("reviewsLast30Days")} value={progress.data.total_reviews} />
          <Stat label={t("dueNow")} value={progress.data.due_now} />
          <Stat label={t("answeredAccuracy")} value={progress.data.answer_accuracy === null ? "—" : `${new Intl.NumberFormat(dateLocale, { maximumFractionDigits: 1 }).format(progress.data.answer_accuracy * 100)}%`} />
          <Stat label={t("answeredQuestions")} value={progress.data.answered} />
        </div>
      )}

      {sessionId ? (
        session.isPending ? <LoadingState rows={2} label={t("loadingSession")} /> : session.error ? <ErrorState error={session.error} title={t("learningLoadError")} notFoundTitle={t("learningDataNotFound")} message={t("learningLoadError")} retryLabel={t("retry")} onRetry={() => session.refetch()} /> : session.data.cards.length === 0 ? (
          <EmptyState title={t("emptyReviewSession")} description={t("emptyReviewSessionDescription")} action={<Button onClick={() => router.replace("/reviews")}>{t("backToQueue")}</Button>} />
        ) : (
          <div className="space-y-4" data-testid="review-session">
            <p className="text-sm text-muted-foreground">{t("ratedProgress").replace("{rated}", String(session.data.cards.filter((card) => card.rated).length)).replace("{total}", String(session.data.cards.length))}</p>
            {session.data.cards.map((card, index) => {
              const reveal = reveals[card.card_id];
              const answered = card.answered;
              return <Card key={card.card_id} data-testid="review-card">
                <CardHeader>
                  <div className="flex flex-wrap items-center gap-2"><Badge variant="secondary">{t(reviewTypeKeys[card.review_type])}</Badge><CardTitle className="text-base">{t("reviewCard").replace("{number}", String(index + 1))}: {card.label}</CardTitle>{card.rated ? <Badge>{t("rated")}</Badge> : null}</div>
                  <CardDescription>{card.prompt}</CardDescription>
                </CardHeader>
                <CardContent className="space-y-3">
                  {card.passage ? <p lang="ja" className="rounded-lg bg-muted p-3 whitespace-pre-wrap">{card.passage}</p> : null}
                  {!answered && card.options.length ? <div className="grid gap-2 sm:grid-cols-2">{card.options.map((option, optionIndex) => <Button key={`${card.card_id}-${optionIndex}`} variant="outline" className="h-auto min-h-9 justify-start whitespace-normal text-left" disabled={answer.isPending} onClick={() => answer.mutate({ card, selected: optionIndex })}>{optionIndex + 1}. {option}</Button>)}</div> : null}
                  {!answered && card.options.length === 0 ? <Button variant="outline" disabled={answer.isPending} onClick={() => answer.mutate({ card, selected: null })}>{t("showHint")}</Button> : null}
                  {answered ? <>
                    {card.options.length ? <ol className="grid gap-1 sm:grid-cols-2">{card.options.map((option, optionIndex) => <li key={`${card.card_id}-answer-${optionIndex}`} className={`rounded-md border px-3 py-2 text-sm ${optionIndex === card.answer_index ? "border-emerald-600/50 bg-emerald-50 dark:bg-emerald-950/30" : ""} ${optionIndex === card.selected_index && card.correct === false ? "border-destructive/50 bg-destructive/5" : ""}`}>{optionIndex + 1}. {option}{optionIndex === card.answer_index ? ` · ${t("answerLabel")}` : ""}{optionIndex === card.selected_index ? ` · ${t("yourChoice")}` : ""}</li>)}</ol> : null}
                    {card.correct !== null ? <p className={card.correct ? "text-sm text-emerald-700 dark:text-emerald-400" : "text-sm text-destructive"}>{card.correct ? t("answerCorrect") : t("answerIncorrect")}</p> : null}
                    <Reveal reveal={reveal} />
                    {!card.rated ? <div className="flex flex-wrap gap-2" aria-label={t("reviewRating")}>{RATINGS.map((rating) => <Button key={rating} variant={rating === "again" ? "destructive" : "outline"} disabled={rate.isPending} onClick={() => rate.mutate({ card, rating })}>{ratingLabel(rating)}</Button>)}</div> : <p className="text-sm text-muted-foreground">{t("ratingRecorded")}</p>}
                  </> : null}
                </CardContent>
              </Card>;
            })}
          </div>
        )
      ) : (
        <>
          {due.isPending ? <LoadingState rows={3} label={t("loadingReviews")} /> : due.error ? <ErrorState error={due.error} title={t("learningLoadError")} notFoundTitle={t("learningDataNotFound")} message={t("learningLoadError")} retryLabel={t("retry")} onRetry={() => due.refetch()} /> : due.data.items.length === 0 ? <EmptyState title={t("noDueItems")} description={t("reviewItemsAppear")} /> : (
            <Card>
              <CardHeader><CardTitle>{t("dueQueue")}</CardTitle><CardDescription>{due.data.items.length} {t("itemsReadyForReview")}</CardDescription></CardHeader>
              <CardContent className="space-y-2">{due.data.items.slice(0, 12).map((item) => <div key={item.id} className="flex flex-wrap items-center gap-2 rounded-lg border p-3"><Badge variant="secondary">{t(reviewTypeKeys[item.review_type])}</Badge><span className="min-w-0 flex-1">{item.label}</span><Badge variant="outline">{t(srsStateKeys[item.srs_state])}</Badge><span className="text-xs text-muted-foreground">{item.due_at ? new Intl.DateTimeFormat(dateLocale, { dateStyle: "medium", timeStyle: "short" }).format(new Date(item.due_at)) : "—"}</span></div>)}</CardContent>
            </Card>
          )}
        </>
      )}
    </>
  );
}

function Stat({ label, value }: { label: string; value: string | number }) {
  return <Card><CardContent><p className="text-xs text-muted-foreground">{label}</p><p className="mt-1 text-2xl font-semibold tabular-nums">{value}</p></CardContent></Card>;
}

function Reveal({ reveal }: { reveal: Record<string, unknown> | undefined }) {
  const { t } = useLocale();
  if (!reveal) return null;
  const items = Array.isArray(reveal.items) ? reveal.items as { title?: string; content?: string; details?: Record<string, unknown> }[] : [];
  const payload = reveal.payload && typeof reveal.payload === "object" ? reveal.payload as Record<string, unknown> : null;
  const summary = payload?.solution_summary_vi ?? payload?.explanation_vi;
  return <div className="rounded-lg bg-muted/60 p-3 text-sm" data-testid="review-reveal">
    <p className="mb-1 font-medium">{t("revealHint")}</p>
    {items.length ? items.map((item, i) => <div key={`${item.title}-${i}`} className="mb-2 last:mb-0"><p lang="ja" className="font-medium">{item.title}</p><p>{item.content}</p></div>) : null}
    {typeof summary === "string" ? <p>{summary}</p> : null}
    {reveal.type === "none" ? <p>{String(reveal.message ?? t("noApprovedExplanation"))}</p> : null}
    {items.length === 0 && typeof summary !== "string" && reveal.type !== "none" ? <p>{t("recallBeforeRating")}</p> : null}
  </div>;
}
