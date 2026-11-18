import { fireEvent, render, screen } from "@testing-library/react";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { beforeEach, describe, expect, it, vi } from "vitest";

const { setTheme } = vi.hoisted(() => ({ setTheme: vi.fn() }));
vi.mock("next-themes", () => ({ useTheme: () => ({ theme: "light", setTheme }) }));

import { LanguageSwitcher } from "@/components/language-switcher";
import { LocaleProvider } from "@/lib/i18n";
import { ThemeSelector } from "./theme-selector";

const css = readFileSync(resolve(process.cwd(), "src/app/globals.css"), "utf8");

describe("theme and locale preferences", () => {
  beforeEach(() => {
    localStorage.clear();
    setTheme.mockClear();
  });

  it("uses matching accessible controls and persists palette and light/dark preference", () => {
    render(<LocaleProvider><LanguageSwitcher /><ThemeSelector /></LocaleProvider>);
    const language = screen.getByRole("combobox", { name: "Ngôn ngữ giao diện" });
    expect(language).toHaveClass("min-h-10", "border-input", "focus-visible:ring-2");
    expect(screen.getByRole("button", { name: "Sáng" })).toHaveClass("min-h-10", "border-input", "focus-visible:ring-2");
    expect(screen.getByRole("button", { name: "Tối" })).toHaveAttribute("aria-pressed", "false");

    fireEvent.click(screen.getByRole("button", { name: "Tối" }));
    fireEvent.click(screen.getByRole("button", { name: "Sakura Zen" }));
    expect(setTheme).toHaveBeenCalledWith("dark");
    expect(localStorage.getItem("jlpt-palette")).toBe("sakura");
    expect(document.documentElement.dataset.palette).toBe("sakura");
    expect(screen.getByRole("button", { name: "Sakura Zen" })).toHaveAttribute("aria-pressed", "true");
  });

  it("limits landscape backgrounds to Sakura Zen and Indigo Washi quote banners", () => {
    expect(css).toContain(':root[data-palette="sakura"] .quote-scenery');
    expect(css).toContain(':root.dark[data-palette="sakura"] .quote-scenery');
    expect(css).toContain(':root[data-palette="indigo"] .quote-scenery');
    expect(css).toContain(':root.dark[data-palette="indigo"] .quote-scenery');
    expect(css).not.toMatch(/:root\[data-palette="(?:modern|wabi|tokyo)"\] \.quote-scenery/);
    expect(css.match(/url\("\/themes\//g)).toHaveLength(4);
  });

  it("uses original lightweight SVG artwork without external image URLs", () => {
    const root = resolve(process.cwd(), "public/themes");
    for (const file of ["sakura-landscape.svg", "indigo-washi-landscape.svg"]) {
      const asset = readFileSync(resolve(root, file), "utf8");
      expect(asset).toContain("Original vector artwork created for this application");
      expect(asset).not.toMatch(/<image\b|href="https?:/i);
      expect(Buffer.byteLength(asset)).toBeLessThan(2_000);
    }
  });
});
