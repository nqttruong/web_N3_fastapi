import { Suspense } from "react";

import { LoadingState } from "@/components/states";
import { ExamDetail } from "@/features/exams/exam-detail";

export default function ExamDetailPage() {
  // useParams() suspends for request-time params under Cache Components.
  return (
    <Suspense fallback={<LoadingState rows={4} />}>
      <ExamDetail />
    </Suspense>
  );
}
