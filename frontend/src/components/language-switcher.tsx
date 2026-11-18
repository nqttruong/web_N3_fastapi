"use client";

import { Globe2 } from "lucide-react";
import { useLocale, type Locale } from "@/lib/i18n";

export function LanguageSwitcher() {
  const { locale, setLocale, t } = useLocale();
  return <label className="relative flex items-center gap-2">
    <span className="sr-only">{t("interfaceLanguage")}</span>
    <Globe2 aria-hidden="true" className="pointer-events-none absolute left-2 size-4 text-muted-foreground" />
    <select aria-label={t("interfaceLanguage")} className="min-h-10 w-full appearance-none rounded-md border border-input bg-background py-1 pl-8 pr-7 text-sm text-foreground shadow-sm transition-colors hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring" value={locale} onChange={event => setLocale(event.target.value as Locale)}>
      <option value="vi">VI · Tiếng Việt</option><option value="en">EN · English</option><option value="ja">日本語 · JA</option>
    </select>
    <span aria-hidden="true" className="pointer-events-none absolute right-2 text-xs text-muted-foreground">⌄</span>
  </label>;
}
