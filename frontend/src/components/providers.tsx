"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { ThemeProvider } from "next-themes";

import { ApiError } from "@/lib/api/client";
import { LocaleProvider } from "@/lib/i18n";

let browserQueryClient: QueryClient | undefined;

function makeQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: 15_000,
        // Do not hammer the API on 4xx: those are not transient.
        retry: (failureCount, error) =>
          !(error instanceof ApiError && error.status >= 400 && error.status < 500) &&
          failureCount < 2,
      },
    },
  });
}

function getQueryClient() {
  // Isolate server renders; reuse a single client in the browser.
  if (typeof window === "undefined") return makeQueryClient();
  browserQueryClient ??= makeQueryClient();
  return browserQueryClient;
}

export function Providers({ children }: { children: ReactNode }) {
  return <ThemeProvider attribute="class" defaultTheme="system" enableSystem disableTransitionOnChange><LocaleProvider><QueryClientProvider client={getQueryClient()}>{children}</QueryClientProvider></LocaleProvider></ThemeProvider>;
}
