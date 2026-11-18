import type { Locale } from "@/lib/i18n";

const localeTag: Record<Locale, string> = { vi: "vi-VN", en: "en-US", ja: "ja-JP" };

export function formatDateTime(iso: string | null | undefined, locale: Locale = "vi"): string {
  if (!iso) return "—";
  const date = new Date(iso);
  return Number.isNaN(date.getTime()) ? "—" : new Intl.DateTimeFormat(localeTag[locale], { dateStyle: "medium", timeStyle: "short" }).format(date);
}

export function formatPercent(ratio: number | null | undefined, locale: Locale = "vi"): string {
  if (ratio === null || ratio === undefined) return "—";
  return `${(ratio * 100).toLocaleString(localeTag[locale], { maximumFractionDigits: 1 })}%`;
}

export function formatDuration(startIso: string, endIso: string | null, locale: Locale = "vi"): string {
  if (!endIso) return "—";
  const seconds = Math.max(0, Math.round((Date.parse(endIso) - Date.parse(startIso)) / 1000));
  const minutes = Math.floor(seconds / 60);
  const rest = seconds % 60;
  const formatUnit = (value: number, unit: "minute" | "second") => new Intl.NumberFormat(localeTag[locale], { style: "unit", unit, unitDisplay: "short" }).format(value);
  return minutes > 0 ? `${formatUnit(minutes, "minute")} ${formatUnit(rest, "second")}` : formatUnit(rest, "second");
}
