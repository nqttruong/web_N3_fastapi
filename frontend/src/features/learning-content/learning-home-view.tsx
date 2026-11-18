"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useId, useState } from "react";
import type { ReactNode } from "react";

import { PageHeader } from "@/components/page-header";
import { EmptyState, LoadingState } from "@/components/states";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { useLocale } from "@/lib/i18n";
import { studyApi, type StudyType } from "./study-api";

const types: StudyType[] = ["vocabulary", "kanji", "grammar"];

function LearningAccordion({ title, description, children }: { title: string; description: string; children: ReactNode }) {
  const [open, setOpen] = useState(false);
  const panelId = useId();
  return <section className="overflow-hidden rounded-xl border bg-card">
    <button type="button" aria-controls={panelId} aria-expanded={open} onClick={() => setOpen(value => !value)} className="flex min-h-20 w-full items-center justify-between gap-4 px-5 py-4 text-left hover:bg-muted/40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring">
      <span><span className="block font-semibold">{title}</span><span className="mt-1 block text-sm text-muted-foreground">{description}</span></span>
      <span aria-hidden="true" className={`shrink-0 transition-transform duration-200 motion-reduce:transition-none ${open ? "rotate-180" : ""}`}>⌄</span>
    </button>
    <div id={panelId} aria-hidden={!open} inert={!open} className={`grid transition-[grid-template-rows,opacity] duration-200 motion-reduce:transition-none ${open ? "grid-rows-[1fr] opacity-100" : "grid-rows-[0fr] opacity-0"}`}>
      <div className="min-h-0 overflow-hidden"><div className="border-t p-5">{children}</div></div>
    </div>
  </section>;
}

export function LearningHomeView() {
  const router = useRouter();
  const { t, locale } = useLocale();
  const [search, setSearch] = useState("");
  const overview = useQuery({ queryKey: ["study-overview"], queryFn: studyApi.overview });
  const vocabularyLessons = useQuery({ queryKey: ["study-lessons", "vocabulary"], queryFn: () => studyApi.lessons("vocabulary") });
  const kanjiLessons = useQuery({ queryKey: ["study-lessons", "kanji"], queryFn: () => studyApi.lessons("kanji") });
  const grammarLessons = useQuery({ queryKey: ["study-lessons", "grammar"], queryFn: () => studyApi.lessons("grammar") });
  const lessonsByType = { vocabulary: vocabularyLessons, kanji: kanjiLessons, grammar: grammarLessons };
  const course = useQuery({ queryKey: ["study-course"], queryFn: studyApi.course });
  const start = useMutation({ mutationFn: studyApi.start, onSuccess: session => router.push(`/learning/study/${session.id}`) });
  const dateLocale = locale === "ja" ? "ja-JP" : locale === "en" ? "en-US" : "vi-VN";
  const learningError = (retry: () => void) => <div role="alert" className="rounded-lg border border-destructive/40 bg-destructive/5 p-4 text-sm"><p>{t("learningLoadError")}</p><Button variant="outline" size="sm" className="mt-3" onClick={retry}>{t("retry")}</Button></div>;
  const statusLabel = (status: string) => status === "needs_review" ? t("needsReview") : status === "completed" ? t("completed") : status === "in_progress" ? t("inProgress") : t("notStarted");
  return <div className="space-y-7">
    <PageHeader title={t("learning")} description={t("learningIntro")} actions={<Button asChild variant="outline"><Link href="/help">{t("studyHelp")}</Link></Button>} />
    {overview.isPending ? <LoadingState rows={2} label={t("loadingLearning")} /> : overview.error ? learningError(() => void overview.refetch()) : <>
      <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4" aria-label={t("studyProgress")}>
        {[ [t("learned"), overview.data.learned], [t("dueToday"), overview.data.due], [t("saved"), overview.data.saved], [t("totalContent"), Object.values(overview.data.content_counts).reduce((a,b) => a+b, 0)] ].map(([label, value]) => <Card key={label}><CardContent className="pt-4"><p className="text-sm text-muted-foreground">{label}</p><p className="text-3xl font-semibold tabular-nums">{value}</p></CardContent></Card>)}
      </section>
      <div className="flex flex-wrap gap-2">
        {overview.data.active_session_id && <Button asChild><Link href={`/learning/study/${overview.data.active_session_id}`}>{t("continueLearning")}</Link></Button>}
        <Button disabled={!(overview.data.due + overview.data.available_new) || start.isPending} onClick={() => start.mutate({ mode: "review" })}>{t("reviewDue")} · {overview.data.due} {t("reviewDueCount")}, {overview.data.available_new} {t("newItems")}</Button>
        <Button asChild variant="outline"><Link href="/learning/saved">{t("savedContent")} ({overview.data.saved})</Link></Button>
        <Button asChild variant="outline"><Link href="/learning/my-words">{t("myWords")}</Link></Button>
      </div>
      {start.error && <p role="alert" className="text-destructive">{t("unknownLearningError")}</p>}
      <section className="grid gap-4 lg:grid-cols-2" aria-label={t("contentProgress")}>
        <Card><CardHeader><CardTitle>{t("contentProgress")}</CardTitle></CardHeader><CardContent className="space-y-3">{types.map(id => { const total = overview.data.content_counts[id] ?? 0; const learned = overview.data.learned_by_type[id] ?? 0; const label = t(id); return <div key={id}><div className="mb-1 flex justify-between text-sm"><span>{label}</span><span className="tabular-nums">{learned}/{total}</span></div><div className="h-2 rounded-full bg-muted" role="progressbar" aria-label={`${label} — ${t("studyProgress")}`} aria-valuenow={learned} aria-valuemax={total}><div className="h-2 rounded-full bg-teal-600" style={{ width: `${total ? 100 * learned / total : 0}%` }} /></div></div>; })}</CardContent></Card>
        <Card><CardHeader><CardTitle>{t("recentActivity")}</CardTitle></CardHeader><CardContent>{overview.data.recent_activity.length ? <ul className="divide-y">{overview.data.recent_activity.map((activity, index) => <li key={`${activity.item_id}:${activity.reviewed_at}:${index}`} className="flex items-center justify-between gap-3 py-2 text-sm"><span lang="ja" className="min-w-0 truncate">{activity.title}</span><span className="shrink-0 text-muted-foreground">{activity.origin === "web_practice" ? t("practice") : t("review")} · {t(activity.rating === "again" ? "forgotten" : activity.rating)} · {new Date(activity.reviewed_at).toLocaleDateString(dateLocale)}</span></li>)}</ul> : <p className="text-sm text-muted-foreground">{t("noRecentActivity")}</p>}</CardContent></Card>
      </section>
    </>}
    <section className="space-y-3" aria-label={t("learningCategories")}>
      <Input className="w-full sm:w-80" value={search} onChange={event => setSearch(event.target.value)} placeholder={t("searchLessons")} aria-label={t("searchLessonLabel")} />
      <div className="space-y-3">
        <div id="composite-lessons"><LearningAccordion title={t("compositeCourse")} description={t("courseLimits")}>
          {course.isPending ? <LoadingState rows={2} label={t("loadingLearning")} /> : course.error ? learningError(() => void course.refetch()) : course.data.length ? <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">{course.data.map(lesson => <Card key={lesson.number}><CardHeader><CardTitle>{lesson.title}</CardTitle></CardHeader><CardContent className="space-y-2 text-sm"><p>{lesson.counts.vocabulary} {t("vocabulary")} · {lesson.counts.grammar} {t("grammar")} · {lesson.counts.kanji} {t("kanji")}</p><p className="text-muted-foreground"><span aria-label={t("studyProgress")}>{lesson.learned}/{lesson.total} {t("learnedCount")}</span> · {statusLabel(lesson.status)}</p><Button asChild variant="outline"><Link href={`/learning/course/${lesson.number}`}>{lesson.learned ? t("resume") : t("start")}</Link></Button></CardContent></Card>)}</div> : <EmptyState title={t("noCompositeCourse")} description={t("syncLearningContent")} />}
        </LearningAccordion></div>
        {types.map(id => {
          const query = lessonsByType[id];
          const visible = query.data?.filter(lesson => `${lesson.title} ${lesson.pack_title} ${lesson.number}`.toLocaleLowerCase().includes(search.toLocaleLowerCase())) ?? [];
          const category = t(id);
          return <LearningAccordion key={id} title={category} description={t("standaloneLessonDescription").replace("{category}", category.toLocaleLowerCase(locale))}>
            {query.isPending ? <LoadingState rows={3} label={t("loadingLearning")} /> : query.error ? learningError(() => void query.refetch()) : !visible.length ? <EmptyState title={search ? t("searchResultsNone") : t("lessonNoContent").replace("{category}", category.toLocaleLowerCase(locale))} description={search ? t("tryAnotherSearch") : t("sourceNeedsSync")} /> : <div className="grid gap-3 md:grid-cols-2">{visible.map(lesson => <Card key={`${lesson.pack_id}:${lesson.lesson_id}`}><CardHeader><CardTitle>{lesson.title}</CardTitle></CardHeader><CardContent className="space-y-3 text-sm"><p className="text-muted-foreground">{lesson.pack_title} · {lesson.jlpt_level} · {lesson.total} {t("items")}</p><p>{lesson.learned}/{lesson.total} {t("learnedViaReview")} · {lesson.learned === 0 ? t("notStarted") : lesson.learned >= lesson.total ? t("completed") : t("inProgress")}</p><div className="h-2 rounded-full bg-muted"><div className="h-full rounded-full bg-teal-600" style={{ width: `${lesson.total ? 100*lesson.learned/lesson.total : 0}%` }} /></div><Button asChild variant="outline"><Link href={`/learning/lessons/${encodeURIComponent(lesson.pack_id)}/${encodeURIComponent(lesson.lesson_id)}`}>{lesson.learned ? t("continueLesson") : t("openLesson")}</Link></Button></CardContent></Card>)}</div>}
          </LearningAccordion>;
        })}
      </div>
    </section>
  </div>;
}
