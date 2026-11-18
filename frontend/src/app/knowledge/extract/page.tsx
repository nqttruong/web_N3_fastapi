import type { Metadata } from "next";
import { Suspense } from "react";

import { LoadingState } from "@/components/states";
import { ExtractWorkflow } from "@/features/knowledge/extract-workflow";

export const metadata: Metadata = { title: "Trích xuất kiến thức" };

export default function KnowledgeExtractPage() {
  return <Suspense fallback={<LoadingState rows={4} />}><ExtractWorkflow /></Suspense>;
}
