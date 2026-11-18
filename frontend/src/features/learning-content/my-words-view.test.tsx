import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { LanguageSwitcher } from "@/components/language-switcher";
import { LocaleProvider } from "@/lib/i18n";

const { myWordsApi } = vi.hoisted(() => ({ myWordsApi: { list: vi.fn(), create: vi.fn(), edit: vi.fn(), archive: vi.fn(), review: vi.fn() } }));
vi.mock("./my-words-api", () => ({ myWordsApi }));

import { MyWordsView } from "./my-words-view";

function wrap(node: ReactNode) {
  return <LocaleProvider><LanguageSwitcher /><QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>{node}</QueryClientProvider></LocaleProvider>;
}

const word = { id: "word-1", original_text: "学校", language: "ja", meanings: { en: ["school"], vi: ["trường học"] }, japanese_reading: "がっこう", english_ipa: null, source_url: null, source_title: null, context: null, tags: [], created_at: "2026-01-01T00:00:00Z", updated_at: "2026-01-01T00:00:00Z", progress: null };

describe("My Words localization", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.setItem("jlpt-locale", "vi");
    myWordsApi.list.mockResolvedValue({ items: [word], total: 1, page: 1 });
    myWordsApi.create.mockResolvedValue({ word, created: true });
    myWordsApi.archive.mockResolvedValue({ archived: true });
  });

  it("localizes the saved word card and preserves reveal state and source text across locale changes", async () => {
    render(wrap(<MyWordsView />));
    expect(await screen.findByText("学校")).toBeInTheDocument();
    fireEvent.change(screen.getByRole("combobox", { name: "Ngôn ngữ giao diện" }), { target: { value: "en" } });
    expect(await screen.findByText("学校")).toBeInTheDocument();
    expect(screen.getByText("My words")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Reveal card" }));
    expect(screen.getByText(/がっこう/)).toBeInTheDocument();
    expect(screen.getByText(/school/)).toBeInTheDocument();
    fireEvent.change(screen.getByRole("combobox", { name: "Interface language" }), { target: { value: "ja" } });
    expect(await screen.findByText("自分の単語")).toBeInTheDocument();
    expect(screen.getByText("学校")).toBeInTheDocument();
    expect(screen.getByText(/がっこう/)).toBeInTheDocument();
    expect(screen.getByText(/school/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "意味を隠す" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "保存を解除" }));
    await waitFor(() => expect(myWordsApi.archive).toHaveBeenCalledWith("word-1"));
  });

  it("localizes the add-word form without losing its draft when locale changes", async () => {
    render(wrap(<MyWordsView />));
    await screen.findByText("Từ của tôi");
    fireEvent.click(screen.getByRole("button", { name: "Thêm từ của tôi" }));
    const term = screen.getByRole("textbox", { name: "Từ hoặc cụm từ gốc" });
    fireEvent.change(term, { target: { value: "勉強" } });
    fireEvent.change(screen.getByRole("combobox", { name: "Ngôn ngữ giao diện" }), { target: { value: "en" } });
    expect(await screen.findByRole("textbox", { name: "Original word or phrase" })).toHaveValue("勉強");
    expect(screen.getAllByRole("button", { name: "Add word" }).length).toBeGreaterThan(0);
    fireEvent.change(screen.getByRole("combobox", { name: "Interface language" }), { target: { value: "ja" } });
    expect(await screen.findByRole("textbox", { name: "元の単語またはフレーズ" })).toHaveValue("勉強");
    expect(screen.getAllByRole("button", { name: "単語を追加" }).length).toBeGreaterThan(0);
  });
});
