"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { PageHeader } from "@/components/page-header";
import { EmptyState, ErrorState, LoadingState } from "@/components/states";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useLocale } from "@/lib/i18n";
import { StudyItemCard } from "./lesson-view";
import { studyApi } from "./study-api";

export function SavedView() {
  const { t } = useLocale();
  const router = useRouter();
  const [search, setSearch] = useState("");
  const result = useQuery({ queryKey: ["study-saved"], queryFn: studyApi.saved });
  const start = useMutation({ mutationFn: studyApi.start, onSuccess: session => router.push(`/learning/study/${session.id}`) });
  const visible = result.data?.filter(item => `${item.payload.expression ?? item.payload.character ?? item.payload.pattern ?? ""} ${item.payload.meaningVi ?? ""} ${item.lesson_title}`.toLocaleLowerCase().includes(search.toLocaleLowerCase())) ?? [];
  return <div className="space-y-5"><PageHeader title={t("savedContent")} description={t("savedLearningDescription")} actions={<Button disabled={!result.data?.length || start.isPending} onClick={() => start.mutate({ mode: "saved" })}>{t("studySavedCards")}</Button>} />{start.error && <p role="alert">{t("sessionActionError")}</p>}<Input value={search} onChange={event => setSearch(event.target.value)} placeholder={t("searchSavedContent")} aria-label={t("searchSavedContent")} />{result.isPending ? <LoadingState rows={3} label={t("loadingLearning")} /> : result.error ? <ErrorState error={result.error} title={t("learningLoadError")} notFoundTitle={t("learningDataNotFound")} message={t("learningLoadError")} retryLabel={t("retry")} onRetry={() => void result.refetch()} /> : result.data.length === 0 ? <EmptyState title={t("noSavedItems")} description={t("saveItemsFromLesson")} /> : visible.length === 0 ? <EmptyState title={t("noSavedSearchResults")} description={t("tryAnotherSearch")} /> : <div className="grid gap-3 md:grid-cols-2">{visible.map(item => <StudyItemCard key={item.id} item={item} />)}</div>}</div>;
}
