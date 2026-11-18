import type { Metadata } from "next";
import { Suspense } from "react";

import { LoadingState } from "@/components/states";
import { ImportEditor } from "@/features/imports/import-editor";

export const metadata: Metadata = { title: "Xem trước nhập đề" };

export default function ImportDraftPage() {
  return (
    <Suspense fallback={<LoadingState rows={6} />}>
      <ImportEditor />
    </Suspense>
  );
}
