"use client";

import { useEffect, useSyncExternalStore } from "react";
import { useTheme } from "next-themes";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useLocale } from "@/lib/i18n";

const palettes = [
  { id: "modern", name: "Modern Minimal", colors: ["#e9f4fb", "#3574a2"] },
  { id: "wabi", name: "Wabi-sabi", colors: ["#f6eee0", "#a64532"] },
  { id: "sakura", name: "Sakura Zen", colors: ["#fbeff2", "#3b846c"], scene: "/themes/sakura-landscape.svg" },
  { id: "indigo", name: "Indigo Washi", colors: ["#edf2f7", "#315984"], scene: "/themes/indigo-washi-landscape.svg" },
  { id: "tokyo", name: "Tokyo Night", colors: ["#1c1d36", "#77cce0"] },
];
const PALETTE_EVENT = "jlpt-palette-change";
function readPalette() { return localStorage.getItem("jlpt-palette") || "modern"; }
function subscribePalette(callback: () => void) {
  window.addEventListener(PALETTE_EVENT, callback);
  window.addEventListener("storage", callback);
  return () => { window.removeEventListener(PALETTE_EVENT, callback); window.removeEventListener("storage", callback); };
}
function savePalette(id: string) { localStorage.setItem("jlpt-palette", id); window.dispatchEvent(new Event(PALETTE_EVENT)); }
function subscribeMounted() { return () => {}; }

export function ThemeSelector() {
  const { t } = useLocale();
  const { theme, setTheme } = useTheme();
  const mounted = useSyncExternalStore(subscribeMounted, () => true, () => false);
  const palette = useSyncExternalStore(subscribePalette, readPalette, () => "modern");
  useEffect(() => { document.documentElement.dataset.palette = palette; }, [palette]);
  return <Card>
    <CardHeader><CardTitle>{t("theme")}</CardTitle></CardHeader>
    <CardContent className="space-y-5">
      <fieldset>
        <legend className="mb-2 text-sm font-medium">{t("theme")}</legend>
        <div className="flex flex-wrap gap-2">
          {[["system", t("system")], ["light", t("light")], ["dark", t("dark")]].map(([id, label]) => (
            <button key={id} type="button" aria-pressed={mounted && theme === id} className="min-h-10 rounded-md border border-input bg-background px-3 text-sm text-foreground transition-colors hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring aria-pressed:border-primary aria-pressed:bg-primary/10" onClick={() => setTheme(id)}>{label}</button>
          ))}
        </div>
      </fieldset>
      <fieldset>
        <legend className="mb-2 text-sm font-medium">{t("palette")}</legend>
        <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
          {palettes.map(item => (
            <button key={item.id} type="button" aria-pressed={palette === item.id} className="flex min-h-12 items-center gap-3 rounded-md border border-input bg-background p-2.5 text-left text-sm text-foreground transition-colors hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring aria-pressed:border-primary aria-pressed:bg-primary/5 aria-pressed:ring-2 aria-pressed:ring-primary/30" onClick={() => savePalette(item.id)}>
              {item.scene ? (
                <span aria-hidden="true" className="h-8 w-14 shrink-0 rounded border bg-cover bg-center" style={{ backgroundImage: `linear-gradient(90deg, rgb(255 255 255 / .18), rgb(255 255 255 / .08)), url('${item.scene}')` }} />
              ) : (
                <span aria-hidden="true" className="flex shrink-0 overflow-hidden rounded-full border"><span className="size-5" style={{ backgroundColor: item.colors[0] }} /><span className="size-5" style={{ backgroundColor: item.colors[1] }} /></span>
              )}
              <span>{item.name}</span>
            </button>
          ))}
        </div>
      </fieldset>
    </CardContent>
  </Card>;
}
