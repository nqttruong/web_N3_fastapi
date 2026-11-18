"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useState } from "react";

import { PageHeader } from "@/components/page-header";
import { ErrorState, LoadingState } from "@/components/states";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ExamCreateForm } from "@/features/exams/exam-create-form";
import { api } from "@/lib/api/endpoints";
import { queryKeys } from "@/lib/api/keys";
import { useLocale } from "@/lib/i18n";

import { HtmlImportForm } from "./html-import-form";
import { ImageImportForm } from "./image-import-form";
import { TextImportForm } from "./text-import-form";

const TABS = ["text", "html", "images", "manual"] as const;
type Tab = (typeof TABS)[number];

export function ExamNewTabs() {
  const { t } = useLocale();
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();
  const urlTab: Tab = TABS.find((t) => t === params.get("tab")) ?? "text";
  // Switch instantly; the URL is updated in the background so reload/back keep the tab.
  const [tab, setTab] = useState<Tab>(urlTab);
  const [syncedUrlTab, setSyncedUrlTab] = useState<Tab>(urlTab);
  if (urlTab !== syncedUrlTab) {
    setSyncedUrlTab(urlTab);
    setTab(urlTab);
  }
  const caps = useQuery({ queryKey: queryKeys.importCapabilities, queryFn: api.importCapabilities });

  return (
    <>
      <PageHeader
        title={t("importPageTitle")}
        description={t("importPageDescription")}
        actions={
          <Button asChild variant="outline">
            <Link href="/exams?tab=drafts">{t("importDraftsLink")}</Link>
          </Button>
        }
      />
      <Tabs
        value={tab}
        onValueChange={(v) => {
          setTab(v as Tab);
          router.replace(`${pathname}?tab=${v}`, { scroll: false });
        }}
      >
        <TabsList className="mb-4 flex h-auto w-full flex-wrap justify-start">
          <TabsTrigger value="text">{t("pasteText")}</TabsTrigger>
          <TabsTrigger value="html">{t("pasteHtml")}</TabsTrigger>
          <TabsTrigger value="images">{t("uploadImages")}</TabsTrigger>
          <TabsTrigger value="manual">{t("createExamManual")}</TabsTrigger>
        </TabsList>
        {tab !== "manual" && caps.isPending ? (
          <LoadingState rows={3} />
        ) : tab !== "manual" && caps.error ? (
          <ErrorState error={caps.error} onRetry={() => caps.refetch()} />
        ) : (
          <>
            <TabsContent value="text">
              <Card>
                <CardContent>{caps.data ? <TextImportForm maxChars={caps.data.limits.max_text_chars} /> : null}</CardContent>
              </Card>
            </TabsContent>
            <TabsContent value="html">
              <Card>
                <CardContent>{caps.data ? <HtmlImportForm maxBytes={caps.data.limits.max_html_bytes} /> : null}</CardContent>
              </Card>
            </TabsContent>
            <TabsContent value="images">
              <Card>
                <CardContent>{caps.data ? <ImageImportForm capabilities={caps.data} /> : null}</CardContent>
              </Card>
            </TabsContent>
            <TabsContent value="manual">
              <ExamCreateForm embedded />
            </TabsContent>
          </>
        )}
      </Tabs>
      <p className="mt-6 text-xs text-muted-foreground">
        {t("notAvailableYet")}
      </p>
    </>
  );
}
