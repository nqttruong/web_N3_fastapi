import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";

import { AppShell } from "@/components/app-shell";
import { Providers } from "@/components/providers";
import { Toaster } from "@/components/ui/sonner";
import { PwaRegistration } from "@/components/pwa-registration";

import "./globals.css";

// Japanese glyphs fall back to OS fonts (avoids downloading a large CJK web font).
const sans = Geist({
  variable: "--font-sans",
  subsets: ["latin", "latin-ext"],
  fallback: ["Hiragino Sans", "Noto Sans JP", "Noto Sans CJK JP", "Yu Gothic UI", "Meiryo", "system-ui", "sans-serif"],
});
const mono = Geist_Mono({ variable: "--font-geist-mono", subsets: ["latin"] });

export const metadata: Metadata = {
  title: { default: "JLPT AI Review", template: "%s · JLPT AI Review" },
  description: "Quản lý và chữa đề JLPT N3 cá nhân",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="vi" suppressHydrationWarning className={`${sans.variable} ${mono.variable} h-full antialiased`}>
      <head><script dangerouslySetInnerHTML={{ __html: "try{var p=localStorage.getItem('jlpt-palette');if(['modern','wabi','sakura','tokyo','indigo'].includes(p))document.documentElement.dataset.palette=p}catch(e){}" }} /></head>
      <body className="min-h-full bg-background font-sans text-foreground">
        <Providers>
          <AppShell>{children}</AppShell>
          <Toaster richColors position="top-right" />
          <PwaRegistration />
        </Providers>
      </body>
    </html>
  );
}
