import type { Metadata } from "next";
import { Suspense } from "react";

import { LoadingState } from "@/components/states";
import { ManualMode } from "@/features/explanations/manual-mode";

export const metadata: Metadata = { title: "Chữa bài bằng ChatGPT" };

export default function Page() {
  return (
    <Suspense fallback={<LoadingState rows={4} />}>
      <ManualMode />
    </Suspense>
  );
}
