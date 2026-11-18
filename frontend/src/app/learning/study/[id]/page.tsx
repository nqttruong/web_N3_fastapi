import { StudySessionView } from "@/features/learning-content/study-session-view";
import { Suspense } from "react";
import { LoadingState } from "@/components/states";

async function Content({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <StudySessionView id={id} />;
}

export default function Page({ params }: { params: Promise<{ id: string }> }) { return <Suspense fallback={<LoadingState rows={4} />}><Content params={params} /></Suspense>; }
