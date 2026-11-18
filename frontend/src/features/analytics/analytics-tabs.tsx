"use client";

import { useSearchParams } from "next/navigation";
import Link from "next/link";
import { Suspense } from "react";
import { Button } from "@/components/ui/button";
import { MistakesView } from "@/features/attempts/mistakes-view";
import { JlptAnalyticsView } from "./jlpt-analytics-view";
import { useLocale } from "@/lib/i18n";

function Tabs() {
  const { t } = useLocale();
  const active = useSearchParams().get("tab") === "mistakes" ? "mistakes" : "stats";
  return <div className="space-y-5"><nav aria-label={t("analytics")} className="flex gap-2"><Button asChild variant={active === "stats" ? "default" : "outline"}><Link href="/analytics/jlpt">{t("stats")}</Link></Button><Button asChild variant={active === "mistakes" ? "default" : "outline"}><Link href="/analytics/jlpt?tab=mistakes">{t("mistakes")}</Link></Button></nav>{active === "mistakes" ? <MistakesView /> : <JlptAnalyticsView />}</div>;
}
export function AnalyticsTabs() { return <Suspense fallback={<JlptAnalyticsView />}><Tabs /></Suspense>; }
