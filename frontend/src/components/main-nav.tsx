"use client";

import { LayoutDashboard, Library, ChartNoAxesCombined, Settings2, BookOpenText, CircleHelp } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";

import { cn } from "@/lib/utils";
import { useLocale, type MessageKey } from "@/lib/i18n";

const NAV = [
  { href: "/", label: "overview" as MessageKey, icon: LayoutDashboard, match: (p: string) => p === "/" },
  { href: "/learning", label: "learning" as MessageKey, icon: BookOpenText, match: (p: string) => p.startsWith("/learning") },
  {
    href: "/exams",
    label: "exams" as MessageKey,
    icon: Library,
    match: (p: string) => p.startsWith("/exams") && p !== "/exams/new",
  },
  { href: "/analytics/jlpt", label: "analytics" as MessageKey, icon: ChartNoAxesCombined, match: (p: string) => p.startsWith("/analytics") || p.startsWith("/mistakes") },
];
const SECONDARY = [
  { href: "/settings", label: "settings" as MessageKey, icon: Settings2, match: (p: string) => p.startsWith("/settings") },
  { href: "/help", label: "help" as MessageKey, icon: CircleHelp, match: (p: string) => p.startsWith("/help") },
];

function NavLinks({ pathname }: { pathname: string | null }) {
  const { t } = useLocale();
  return (
    <nav aria-label={t("mainNavigation")} className="flex gap-1 overflow-x-auto px-2 pb-2 md:flex-col md:px-3">
      {NAV.map(({ href, label, icon: Icon, match }) => {
        const active = pathname !== null && match(pathname);
        return (
          <Link
            key={href}
            href={href}
            aria-current={active ? "page" : undefined}
            className={cn(
              "flex shrink-0 items-center gap-2 rounded-lg px-3 py-2 text-sm transition-colors",
              active
                ? "bg-primary text-primary-foreground"
                : "text-muted-foreground hover:bg-muted hover:text-foreground",
            )}
          >
            <Icon className="size-4" aria-hidden />
            {t(label)}
          </Link>
        );
      })}
      <div className="mx-2 hidden border-t md:block" />
      {SECONDARY.map(({ href, label, icon: Icon, match }) => <Link key={href} href={href} aria-current={pathname !== null && match(pathname) ? "page" : undefined} className={cn("flex shrink-0 items-center gap-2 rounded-lg px-3 py-2 text-sm", pathname !== null && match(pathname) ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:bg-muted hover:text-foreground")}><Icon className="size-4" aria-hidden />{t(label)}</Link>)}
    </nav>
  );
}

/** Rendered as the Suspense fallback during prerendering (no active highlight yet). */
export function StaticNav() {
  return <NavLinks pathname={null} />;
}

export function MainNav() {
  return <NavLinks pathname={usePathname()} />;
}
