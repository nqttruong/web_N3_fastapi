import type { Metadata } from "next";

import { KnowledgeView } from "@/features/knowledge/knowledge-view";

export const metadata: Metadata = { title: "Kiến thức" };

export default function KnowledgePage() {
  return <KnowledgeView />;
}
