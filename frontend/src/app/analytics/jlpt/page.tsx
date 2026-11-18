import type { Metadata } from "next";
import { AnalyticsTabs } from "@/features/analytics/analytics-tabs";

export const metadata: Metadata = { title: "Phân tích JLPT" };

export default function JlptAnalyticsPage() { return <AnalyticsTabs />; }
