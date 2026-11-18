import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const { studyApi, push } = vi.hoisted(() => ({
  studyApi: { courseLesson: vi.fn(), start: vi.fn() },
  push: vi.fn(),
}));

vi.mock("./study-api", () => ({
  studyApi,
  studyTitle: (item: { item_type: string; payload: Record<string, unknown> }) => String(item.payload[item.item_type === "vocabulary" ? "expression" : item.item_type === "kanji" ? "character" : "pattern"] ?? ""),
}));
vi.mock("next/navigation", () => ({ useRouter: () => ({ push }) }));

import { CourseView } from "./course-view";

function wrap(node: ReactNode) {
  return <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>{node}</QueryClientProvider>;
}

describe("composite course flashcards", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    studyApi.courseLesson.mockResolvedValue({ number: 1, title: "Bài 01", sections: {
      vocabulary: [{ id: "v", item_type: "vocabulary", payload: { expression: "学校", reading: "がっこう", meaningVi: "trường học" }, examples: [{ japanese: "学校へ行く。", furigana: "{学校|がっこう}へ行く。", translationVi: "Đi đến trường." }] }],
      grammar: [{ id: "g", item_type: "grammar", payload: { pattern: "〜ている", structure: "Vて + いる", meaningVi: "đang diễn ra", usage: "Diễn tả hành động đang tiếp diễn." }, examples: [{ japanese: "雨が降っています。", furigana: "雨が{降|ふ}っています。", translationVi: "Trời đang mưa." }] }],
      kanji: [{ id: "k", item_type: "kanji", payload: { character: "学", meaningVi: "học", hanViet: "HỌC", onReadings: ["ガク"], kunReadings: ["まな.ぶ"] }, examples: [{ japanese: "学校", furigana: "{学校|がっこう}", translationVi: "trường học" }] }],
    } });
    studyApi.start.mockResolvedValue({ id: "session-1" });
  });

  it("starts one mixed session without a type filter", async () => {
    render(wrap(<CourseView number={1} />));
    fireEvent.click(await screen.findByRole("button", { name: "Flashcard tổng hợp" }));
    await waitFor(() => expect(studyApi.start.mock.calls[0]?.[0]).toEqual({ mode: "course", course_number: 1 }));
    expect(push).toHaveBeenCalledWith("/learning/study/session-1");
  });

  it("renders source readings, meanings, and furigana for all three card types", async () => {
    render(wrap(<CourseView number={1} />));
    expect(await screen.findByText("学校", { selector: '[data-slot="card-title"]' })).toBeInTheDocument();
    const reading = screen.getAllByText("がっこう").find(node => node.tagName.toLowerCase() === "p");
    expect(reading).toBeInTheDocument();
    expect(screen.getByText("〜ている", { selector: '[data-slot="card-title"]' })).toBeInTheDocument();
    expect(screen.getByText("đang diễn ra")).toBeInTheDocument();
    expect(screen.getByText(/Trời đang mưa/)).toBeInTheDocument();
    expect(screen.getByText("学", { selector: '[data-slot="card-title"]' })).toBeInTheDocument();
    expect(screen.getByText(/Âm Hán Việt: HỌC/)).toBeInTheDocument();
    expect(screen.getByText(/On’yomi: ガク · Kun’yomi: まな\.ぶ/)).toBeInTheDocument();
    expect(screen.getAllByText("がっこう").some(node => node.closest("ruby")?.textContent.includes("学校"))).toBe(true);
  });

  it.each([
    ["Từ vựng", "vocabulary"],
    ["Ngữ pháp", "grammar"],
    ["Kanji", "kanji"],
  ] as const)("starts a %s-only flashcard session", async (label, itemType) => {
    render(wrap(<CourseView number={1} />));
    await screen.findByText("Bài 01");
    const button = screen.getAllByRole("button").find(element => element.textContent?.includes("Học bằng thẻ") && element.textContent.includes(label));
    expect(button).toBeDefined();
    fireEvent.click(button!);
    await waitFor(() => expect(studyApi.start.mock.calls.at(-1)?.[0]).toEqual({ mode: "course", course_number: 1, item_type: itemType }));
  });
});
