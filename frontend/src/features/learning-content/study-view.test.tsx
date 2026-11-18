import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { LanguageSwitcher } from "@/components/language-switcher";
import { LocaleProvider } from "@/lib/i18n";
const { studyApi } = vi.hoisted(() => ({ studyApi: { session: vi.fn(), rate: vi.fn(), overview: vi.fn(), lessons: vi.fn(), save: vi.fn() } }));
vi.mock("./study-api", () => ({ studyApi, studyTitle: (item: { item_type: string; payload: Record<string, string> }) => item.payload[item.item_type === "vocabulary" ? "expression" : item.item_type === "kanji" ? "character" : "pattern"] }));
vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn() }) }));

import { JapaneseText } from "@/components/japanese-text";
import { StudyItemCard } from "./lesson-view";
import { StudySessionView } from "./study-session-view";

function wrap(node: ReactNode) {
  return <LocaleProvider><LanguageSwitcher /><QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>{node}</QueryClientProvider></LocaleProvider>;
}

const current = { id: "00000000-0000-0000-0000-000000000001", item_type: "kanji", payload: { character: "学", meaningVi: "học" }, examples: [{ japanese: "学校", furigana: "{学校|がっこう}", translationVi: "trường học" }] };
const session = { id: "s1", mode: "lesson", position: 0, total: 1, current, finished_at: null, ratings: {} };

describe("Web learning session", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.setItem("jlpt-locale", "vi");
    studyApi.session.mockResolvedValue(session);
    studyApi.rate.mockResolvedValue({ ...session, position: 1, current: null, finished_at: "2026-11-17T00:00:00Z", ratings: { good: 1 } });
    studyApi.save.mockResolvedValue({ saved: false });
  });

  it("renders source furigana with ruby and persists a flashcard rating", async () => {
    render(wrap(<StudySessionView id="s1" />));
    expect(await screen.findByText("学")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /Lật thẻ/ }));
    expect(screen.getByText("学校").closest("ruby")).toHaveTextContent("がっこう");
    fireEvent.click(screen.getByRole("button", { name: /Tốt · 3/ }));
    await waitFor(() => expect(studyApi.rate).toHaveBeenCalledWith("s1", expect.any(String), "good"));
    expect(await screen.findByText(/Phiên học hoàn thành/)).toBeInTheDocument();
  });

  it.each([
    {
      item_type: "vocabulary",
      payload: { expression: "学校", reading: "がっこう", meaningVi: "trường học", partOfSpeech: "Danh từ" },
      examples: [{ japanese: "学校へ行く。", furigana: "{学校|がっこう}へ行く。", translationVi: "Đi đến trường." }],
      expected: ["がっこう", "trường học", "Danh từ", "Đi đến trường."],
    },
    {
      item_type: "grammar",
      payload: { pattern: "〜ている", meaningVi: "đang diễn ra", structure: "Vて + いる", usage: "Hành động đang tiếp diễn.", formation: "Động từ thể て + いる" },
      examples: [{ japanese: "雨が降っています。", furigana: "雨が{降|ふ}っています。", translationVi: "Trời đang mưa." }],
      expected: ["đang diễn ra", "Cấu trúc: Vて + いる", "Cách dùng: Hành động đang tiếp diễn.", "Cách tạo: Động từ thể て + いる", "Trời đang mưa."],
    },
  ] as const)("reveals source-backed $item_type content with its example", async ({ item_type, payload, examples, expected }) => {
    const card = { id: `${item_type}-1`, item_type, payload, examples, saved: false, progress: null, exercise_results: {} };
    studyApi.session.mockResolvedValueOnce({ ...session, current: card, total: 1 });
    render(wrap(<StudySessionView id="source-backed-session" />));
    expect(await screen.findByText(item_type === "vocabulary" ? "学校" : "〜ている")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /Lật thẻ/ }));
    for (const value of expected) expect(screen.getAllByText(value, { exact: false }).length).toBeGreaterThan(0);
    const [rubyBase, rubyReading] = item_type === "vocabulary" ? ["学校", "がっこう"] : ["降", "ふ"];
    expect(screen.getAllByText(rubyReading).some(node => node.closest("ruby")?.textContent === `${rubyBase}${rubyReading}`)).toBe(true);
  });

  it("keeps plain Japanese surrounding annotated readings", () => {
    render(<JapaneseText value="{学校|がっこう}へ行く。" />);
    expect(screen.getByText("学校").closest("ruby")).toHaveTextContent("がっこう");
    expect(screen.getByText(/へ行く。/)).toBeInTheDocument();
  });

  it("updates flashcard UI language without losing the revealed card or session", async () => {
    render(wrap(<StudySessionView id="s1" />));
    expect(await screen.findByText("学")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /Lật thẻ/ }));
    expect(screen.getByText("học")).toBeInTheDocument();
    fireEvent.change(screen.getByRole("combobox", { name: "Ngôn ngữ giao diện" }), { target: { value: "en" } });
    expect(await screen.findByRole("heading", { name: "Flashcards" })).toBeInTheDocument();
    expect(screen.getByText("học")).toBeInTheDocument();
    expect(screen.getByText("学校").closest("ruby")).toHaveTextContent("がっこう");
    fireEvent.click(screen.getByRole("button", { name: /Good · 3/ }));
    await waitFor(() => expect(studyApi.rate).toHaveBeenCalledWith("s1", expect.any(String), "good"));
    fireEvent.change(screen.getByRole("combobox", { name: "Interface language" }), { target: { value: "ja" } });
    expect(await screen.findByText(/学習セッション完了/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "学習" })).toBeInTheDocument();
  });

  it("localizes saved-content actions while keeping the content and save state", async () => {
    const item = { id: "item-1", item_type: "vocabulary", payload: { character: "学校", expression: "学校", reading: "がっこう", meaningVi: "trường học" }, examples: [], saved: true, progress: null };
    render(wrap(<StudyItemCard item={item as never} />));
    expect(await screen.findByRole("button", { name: "Bỏ lưu" })).toBeInTheDocument();
    expect(screen.getByText("学校")).toBeInTheDocument();
    fireEvent.change(screen.getByRole("combobox", { name: "Ngôn ngữ giao diện" }), { target: { value: "en" } });
    expect(await screen.findByRole("button", { name: "Remove saved word" })).toBeInTheDocument();
    expect(screen.getByText("学校")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Remove saved word" }));
    await waitFor(() => expect(studyApi.save).toHaveBeenCalledWith("item-1", false));
  });
});
