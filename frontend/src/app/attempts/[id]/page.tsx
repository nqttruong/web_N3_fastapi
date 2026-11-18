import type { Metadata } from "next";
import { Suspense } from "react";

import { LoadingState } from "@/components/states";
import { AttemptDetailView } from "@/features/attempts/attempt-detail";

export const metadata: Metadata = { title: "Chi tiết bài làm" };

export default function AttemptPage() {
  return (
    <Suspense fallback={<LoadingState rows={5} />}>
      <AttemptDetailView />
    </Suspense>
  );
}
