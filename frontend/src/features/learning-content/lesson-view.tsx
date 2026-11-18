"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";

import { PageHeader } from "@/components/page-header";
import { JapaneseText } from "@/components/japanese-text";
import { ErrorState, LoadingState } from "@/components/states";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useLocale } from "@/lib/i18n";
import { studyApi, studyTitle, type StudyItem } from "./study-api";
import { GrammarExercises } from "./grammar-exercise";

export function StudyItemCard({ item }: { item: StudyItem }) {
  const { t } = useLocale();
  const client = useQueryClient();
  const save = useMutation({ mutationFn: () => studyApi.save(item.id, !item.saved), onSuccess: () => { void client.invalidateQueries({ queryKey: ["study-lesson"] }); void client.invalidateQueries({ queryKey: ["study-saved"] }); void client.invalidateQueries({ queryKey: ["study-overview"] }); } });
  return <Card><CardHeader><CardTitle lang="ja" className="text-2xl leading-relaxed">{studyTitle(item)}</CardTitle></CardHeader><CardContent className="space-y-2">
    {item.item_type === "vocabulary" && <p lang="ja" className="text-lg">{String(item.payload.reading ?? "")}</p>}
    <p>{String(item.payload.meaningVi ?? "")}</p>
    {item.item_type === "kanji" && <>{item.payload.hanViet ? <p>{t("hanViet")}: {String(item.payload.hanViet)}</p> : null}<p lang="ja">{t("onReading")}: {Array.isArray(item.payload.onReadings) ? item.payload.onReadings.join("、") : t("noSourceReading")} · {t("kunReading")}: {Array.isArray(item.payload.kunReadings) ? item.payload.kunReadings.join("、") : t("noSourceReading")}</p></>}
    {item.item_type === "grammar" && <><p lang="ja">{String(item.payload.structure ?? "")}</p>{item.payload.usage && <p>{String(item.payload.usage)}</p>}</>}
    {item.examples.map((example, i) => <div key={i} className="rounded-lg bg-muted p-3"><p className="text-lg leading-loose"><JapaneseText value={example.furigana ?? example.japanese} /></p><p className="text-sm text-muted-foreground">{example.translationVi}</p></div>)}
    {item.item_type === "grammar" && <GrammarExercises item={item} />}
    <div className="flex items-center justify-between gap-3 pt-2"><span className="text-sm text-muted-foreground">{item.progress ? `${item.progress.review_count} ${t("reviewCount")} · ${t(item.progress.state === "new" ? "srsNew" : item.progress.state === "learning" ? "srsLearning" : item.progress.state === "review" ? "srsReview" : "srsMastered")}` : t("notReviewed")}</span><Button variant="outline" disabled={save.isPending} onClick={() => save.mutate()}>{item.saved ? t("removeSaved") : t("saveLearningContent")}</Button></div>
    {save.error && <p role="alert">{t("learningSaveError")}</p>}
  </CardContent></Card>;
}

export function LessonView({ packId, lessonId }: { packId: string; lessonId: string }) {
  const { t } = useLocale();
  const router = useRouter();
  const result = useQuery({ queryKey: ["study-lesson", packId, lessonId], queryFn: () => studyApi.lesson(packId, lessonId) });
  const start = useMutation({ mutationFn: studyApi.start, onSuccess: session => router.push(`/learning/study/${session.id}`) });
  if (result.isPending) return <LoadingState rows={4} label={t("loadingLesson")} />;
  if (result.error) return <ErrorState error={result.error} title={t("learningLoadError")} notFoundTitle={t("learningDataNotFound")} message={t("learningLoadError")} retryLabel={t("retry")} onRetry={() => void result.refetch()} />;
  const lesson = result.data;
  return <div className="space-y-5"><PageHeader title={lesson.title} description={t("lessonItemCount").replace("{count}", String(lesson.items.length)).replace("{number}", String(lesson.number))} actions={<Button disabled={!lesson.items.length || start.isPending} onClick={() => start.mutate({ mode: "lesson", pack_id: packId, lesson_id: lessonId })}>{t("studyByFlashcard")}</Button>} />{start.error && <p role="alert">{t("sessionActionError")}</p>}<div className="grid gap-4 md:grid-cols-2">{lesson.items.map(item => <StudyItemCard item={item} key={item.id} />)}</div></div>;
}
