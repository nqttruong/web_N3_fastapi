import type { Metadata } from "next";
import { Suspense } from "react";

import { LoadingState } from "@/components/states";
import { ExamNewTabs } from "@/features/imports/exam-new-tabs";

export const metadata: Metadata = { title: "Nhập đề" };

export default function NewExamPage() {
  return (
    <Suspense fallback={<LoadingState rows={4} />}>
      <ExamNewTabs />
    </Suspense>
  );
}
