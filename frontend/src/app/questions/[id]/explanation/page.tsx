import type { Metadata } from "next";
import { Suspense } from "react";

import { LoadingState } from "@/components/states";
import { QuestionExplanationPage } from "@/features/explanations/question-explanation";

export const metadata: Metadata = { title: "Lời giải" };

export default function Page() {
  return (
    <Suspense fallback={<LoadingState rows={5} />}>
      <QuestionExplanationPage />
    </Suspense>
  );
}
