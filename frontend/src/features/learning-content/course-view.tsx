"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useMutation, useQuery } from "@tanstack/react-query";
import { PageHeader } from "@/components/page-header";
import { ErrorState, LoadingState, errorMessage } from "@/components/states";
import { Button } from "@/components/ui/button";
import { StudyItemCard } from "./lesson-view";
import { studyApi, type StudyType } from "./study-api";
import { useLocale } from "@/lib/i18n";

export function CourseView({ number }: { number: number }) {
  const { t } = useLocale();
  const sections: { type: StudyType; title: string }[] = [
    { type: "vocabulary", title: t("vocabulary") },
    { type: "grammar", title: t("grammar") },
    { type: "kanji", title: t("kanji") },
  ];
  const router = useRouter();
  const result = useQuery({ queryKey: ["study-course-lesson", number], queryFn: () => studyApi.courseLesson(number) });
  const start = useMutation({ mutationFn: studyApi.start, onSuccess: session => router.push(`/learning/study/${session.id}`) });
  if (result.isPending) return <LoadingState rows={4} />;
  if (result.error) return <ErrorState error={result.error} onRetry={() => void result.refetch()} />;
  const lesson = result.data;
  const total = sections.reduce((sum, section) => sum + lesson.sections[section.type].length, 0);
  return <div className="space-y-6"><PageHeader title={lesson.title} description={t("compositeSourceDescription")} actions={<div className="flex flex-wrap gap-2"><Button asChild variant="outline"><Link href="/learning">{t("courseIndex")}</Link></Button><Button disabled={!total || start.isPending} onClick={() => start.mutate({ mode: "course", course_number: number })}>{t("mixedFlashcards")}</Button></div>} />
    {sections.map(({ type, title }) => <section key={type} className="space-y-3" aria-label={title}><div className="flex flex-wrap items-center justify-between gap-2"><h2 className="text-xl font-semibold">{title} · {lesson.sections[type].length}</h2>{lesson.sections[type].length > 0 && <Button disabled={start.isPending} onClick={() => start.mutate({ mode: "course", course_number: number, item_type: type })}>{t("studyByFlashcard")} · {title}</Button>}</div>{lesson.sections[type].length ? <div className="grid gap-4 md:grid-cols-2">{lesson.sections[type].map(item => <StudyItemCard key={item.id} item={item} />)}</div> : <p className="text-sm text-muted-foreground">{t("sourceContentEnded")}</p>}</section>)}
    {start.error && <p role="alert" className="text-destructive">{errorMessage(start.error)}</p>}
  </div>;
}
