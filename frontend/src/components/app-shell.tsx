import { BookOpenCheck } from "lucide-react";
import Link from "next/link";
import { Suspense, type ReactNode } from "react";

import { MainNav, StaticNav } from "@/components/main-nav";
import { LanguageSwitcher } from "@/components/language-switcher";

export function AppShell({ children }: { children: ReactNode }) {
  return (
    <div className="flex min-h-dvh flex-col md:flex-row">
      <aside className="border-b bg-muted/30 md:sticky md:top-0 md:h-dvh md:w-60 md:shrink-0 md:border-r md:border-b-0">
        <div className="flex items-center gap-2 px-4 py-4 md:px-5 md:py-6">
          <BookOpenCheck className="size-5 text-primary" aria-hidden />
          <Link href="/" className="font-semibold tracking-tight">
            JLPT AI Review
          </Link>
          <span className="ml-auto rounded-md border px-1.5 py-0.5 text-xs text-muted-foreground md:ml-1">N3</span>
        </div>
        <Suspense fallback={<StaticNav />}>
          <MainNav />
        </Suspense>
        <div className="px-4 pb-3 md:mt-auto md:pb-5"><LanguageSwitcher /></div>
      </aside>
      <main className="min-w-0 flex-1 px-4 py-6 md:px-10 md:py-10">
        <div className="mx-auto w-full max-w-6xl">{children}</div>
      </main>
    </div>
  );
}
