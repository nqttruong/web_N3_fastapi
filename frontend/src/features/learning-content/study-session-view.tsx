"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";

import { PageHeader } from "@/components/page-header";
import { JapaneseText } from "@/components/japanese-text";
import { ErrorState, LoadingState } from "@/components/states";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { studyApi, studyTitle, type Rating } from "./study-api";
import { useLocale } from "@/lib/i18n";

const ratings: { value: Rating; key: string }[] = [{ value: "again", key: "1" }, { value: "hard", key: "2" }, { value: "good", key: "3" }, { value: "easy", key: "4" }];

export function StudySessionView({ id }: { id: string }) {
  const { t } = useLocale();
  const client = useQueryClient();
  const result = useQuery({ queryKey: ["study-session", id], queryFn: () => studyApi.session(id) });
  const [revealed, setRevealed] = useState(false);
  const pendingId = useRef<string | null>(null);
  const rate = useMutation({ mutationFn: (rating: Rating) => studyApi.rate(id, pendingId.current ??= crypto.randomUUID(), rating), onSuccess: session => { client.setQueryData(["study-session", id], session); pendingId.current = null; setRevealed(false); void client.invalidateQueries({ queryKey: ["study-overview"] }); void client.invalidateQueries({ queryKey: ["study-lesson"] }); } });
  useEffect(() => {
    function key(event: KeyboardEvent) {
      if (event.target instanceof HTMLInputElement || event.target instanceof HTMLTextAreaElement) return;
      if (event.code === "Space" && !revealed) { event.preventDefault(); setRevealed(true); }
      if (revealed && !rate.isPending) { const choice = ratings.find(r => r.key === event.key); if (choice) rate.mutate(choice.value); }
    }
    window.addEventListener("keydown", key);
    return () => window.removeEventListener("keydown", key);
  }, [revealed, rate]);
  if (result.isPending) return <LoadingState rows={3} label={t("loadingSession")} />;
  if (result.error) return <ErrorState error={result.error} title={t("learningLoadError")} notFoundTitle={t("learningDataNotFound")} message={t("learningLoadError")} retryLabel={t("retry")} onRetry={() => void result.refetch()} />;
  const session = result.data;
  if (!session.current) return <div className="space-y-5"><PageHeader title={t("studySessionComplete")} description={`${session.total} ${t("cardsProcessed")}`} /><Card><CardContent className="space-y-3 pt-5"><p>{t("forgotten")} {session.ratings.again ?? 0} · {t("hard")} {session.ratings.hard ?? 0} · {t("good")} {session.ratings.good ?? 0} · {t("easy")} {session.ratings.easy ?? 0}</p><Button asChild><Link href="/learning">{t("learning")}</Link></Button></CardContent></Card></div>;
  const item = session.current;
  const readings = (value: unknown) => Array.isArray(value) ? value.filter((part): part is string => typeof part === "string").join("、") : typeof value === "string" ? value : "";
  return <div className="mx-auto max-w-3xl space-y-5"><PageHeader title={session.mode === "review" ? t("reviewDue") : t("flashcards")} description={`${t("card")} ${session.position + 1}/${session.total} · ${session.mode === "review" ? t("ratingUpdatesSchedule") : t("practiceNoSchedule")}`} actions={<Button asChild variant="outline"><Link href="/learning">{t("pause")}</Link></Button>} />
    <div className="h-2 rounded-full bg-muted" role="progressbar" aria-label={t("studyProgress")} aria-valuenow={session.position} aria-valuemin={0} aria-valuemax={session.total}><div className="h-2 rounded-full bg-teal-600" style={{ width: `${session.total ? 100*session.position/session.total : 0}%` }} /></div>
    <Card><CardContent className="flex min-h-72 flex-col items-center justify-center gap-5 p-8 text-center"><p className="text-sm text-muted-foreground">{t(item.item_type)}</p><p lang="ja" className="text-5xl leading-tight"><JapaneseText value={studyTitle(item)} /></p>{revealed && <div className="w-full space-y-3 border-t pt-5">
      {item.item_type === "vocabulary" && <><p lang="ja" className="text-xl">{String(item.payload.reading ?? item.payload.furigana ?? "")}</p><p className="text-xl">{String(item.payload.meaningVi ?? "")}</p>{item.payload.partOfSpeech ? <p className="text-sm text-muted-foreground">{String(item.payload.partOfSpeech)}</p> : null}</>}
      {item.item_type === "kanji" && <><p className="text-xl">{String(item.payload.meaningVi ?? "")}</p>{item.payload.hanViet ? <p>{t("hanViet")}: {String(item.payload.hanViet)}</p> : null}<p lang="ja" className="text-sm text-muted-foreground">{t("onReading")}: {readings(item.payload.onReadings) || t("noSourceReading")} · {t("kunReading")}: {readings(item.payload.kunReadings) || t("noSourceReading")}</p></>}
      {item.item_type === "grammar" && <><p className="text-xl">{String(item.payload.meaningVi ?? "")}</p>{item.payload.structure ? <p lang="ja">{t("structure")}: {String(item.payload.structure)}</p> : null}{item.payload.usage ? <p className="text-sm">{t("usage")}: {String(item.payload.usage)}</p> : null}{item.payload.formation ? <p className="text-sm">{t("formation")}: {String(item.payload.formation)}</p> : null}</>}
      {item.examples.slice(0,3).map((example,i) => <p key={i} className="text-base leading-loose"><JapaneseText value={example.furigana ?? example.japanese} /> {example.translationVi && <span className="block text-sm text-muted-foreground">{example.translationVi}</span>}</p>)}
    </div>}</CardContent></Card>
    {!revealed ? <Button size="lg" className="w-full" onClick={() => setRevealed(true)}>{t("turnCard")} · {t("spaceKey")}</Button> : <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">{ratings.map(r => <Button key={r.value} variant={r.value === "again" ? "outline" : "default"} disabled={rate.isPending} onClick={() => rate.mutate(r.value)}>{t(r.value === "again" ? "forgotten" : r.value)} · {r.key}</Button>)}</div>}
    {rate.error && <p role="alert" className="text-destructive">{t("sessionActionError")} · {t("retrySameRating")}</p>}
  </div>;
}
