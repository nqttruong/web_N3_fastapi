import { LessonView } from "@/features/learning-content/lesson-view";
import { Suspense } from "react";
import { LoadingState } from "@/components/states";

async function Content({ params }: { params: Promise<{ packId: string; lessonId: string }> }) {
  const { packId, lessonId } = await params;
  return <LessonView packId={decodeURIComponent(packId)} lessonId={decodeURIComponent(lessonId)} />;
}

export default function Page({ params }: { params: Promise<{ packId: string; lessonId: string }> }) { return <Suspense fallback={<LoadingState rows={4} />}><Content params={params} /></Suspense>; }
