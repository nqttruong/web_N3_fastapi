import type { Metadata } from "next";
import { Suspense } from "react";

import { LoadingState } from "@/components/states";
import { ExamLibrary } from "@/features/exams/exam-library";

export const metadata: Metadata = { title: "Kho đề" };

export default function ExamsPage() {
  // useSearchParams() needs a Suspense boundary under Cache Components.
  return (
    <Suspense fallback={<LoadingState rows={5} />}>
      <ExamLibrary />
    </Suspense>
  );
}
