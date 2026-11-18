"use client";

import { useState, useSyncExternalStore } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { useLocale } from "@/lib/i18n";

// Original short encouragements written for this application; no author is attributed.
const QUOTES = [
  { ja: "一歩ずつ、前へ。", reading: "いっぽずつ、まえへ。", vi: "Từng bước một, tiến về phía trước.", en: "One step at a time, forward." },
  { ja: "今日の一語が、明日の力になる。", reading: "きょうのいちごが、あしたのちからになる。", vi: "Một từ học hôm nay trở thành sức mạnh ngày mai.", en: "A word learned today strengthens tomorrow." },
  { ja: "続けることが、道をつくる。", reading: "つづけることが、みちをつくる。", vi: "Kiên trì tạo nên con đường.", en: "Continuing creates a path." },
  { ja: "間違いから、また学ぼう。", reading: "まちがいから、またまなぼう。", vi: "Hãy học thêm từ những lần sai.", en: "Learn again from mistakes." },
];

export function JapaneseQuote() {
  const { locale, t } = useLocale();
  const dayIndex = useSyncExternalStore(() => () => {}, () => Math.floor(Date.now() / 86_400_000) % QUOTES.length, () => 0);
  const [offset, setOffset] = useState(0);
  const index = (dayIndex + offset) % QUOTES.length;
  const quote = QUOTES[index];
  return <Card className="quote-scenery border-primary/20 bg-primary/5"><CardContent className="flex flex-wrap items-center justify-between gap-4 pt-5"><div><p className="mb-2 text-xs font-semibold uppercase tracking-widest text-muted-foreground">{t("quote")}</p><p lang="ja" className="text-2xl font-medium leading-relaxed">{quote.ja}</p><p lang="ja" className="text-sm text-muted-foreground">{quote.reading}</p><p className="mt-2 text-sm">{locale === "en" ? quote.en : locale === "ja" ? quote.ja : quote.vi}</p></div><Button variant="outline" size="sm" onClick={() => setOffset(offset + 1)}>{t("nextQuote")}</Button></CardContent></Card>;
}
