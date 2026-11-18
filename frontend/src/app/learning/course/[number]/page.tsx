import { Suspense } from "react";

import { LoadingState } from "@/components/states";
import { CourseView } from "@/features/learning-content/course-view";

async function Content({ params }: { params: Promise<{ number: string }> }) {
  const { number } = await params;
  return <CourseView number={Number(number)} />;
}

export default function CoursePage({ params }: { params: Promise<{ number: string }> }) {
  return <Suspense fallback={<LoadingState rows={4} />}><Content params={params} /></Suspense>;
}
