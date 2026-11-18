import type { Metadata } from "next";
import { Suspense } from "react";

import { LoadingState } from "@/components/states";
import { PracticeView } from "@/features/attempts/practice-view";

export const metadata: Metadata = { title: "Làm bài" };

export default function PracticePage() {
  return (
    <Suspense fallback={<LoadingState rows={5} />}>
      <PracticeView />
    </Suspense>
  );
}
