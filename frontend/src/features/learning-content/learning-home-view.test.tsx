import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { hydrateRoot } from "react-dom/client";
import { renderToString } from "react-dom/server";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { LanguageSwitcher } from "@/components/language-switcher";
import { LocaleProvider } from "@/lib/i18n";

const { studyApi } = vi.hoisted(() => ({ studyApi: { overview: vi.fn(), lessons: vi.fn(), course: vi.fn(), start: vi.fn() } }));
vi.mock("./study-api", () => ({ studyApi }));
vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn() }) }));

import { LearningHomeView } from "./learning-home-view";

function wrap(node: ReactNode, withLanguageSwitcher = false) {
  return <LocaleProvider><QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>{withLanguageSwitcher && <LanguageSwitcher />}{node}</QueryClientProvider></LocaleProvider>;
}

describe("learning home accordions", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.setItem("jlpt-locale", "vi");
    studyApi.overview.mockResolvedValue({ learned: 2, due: 1, saved: 3, content_counts: { vocabulary: 5, kanji: 4, grammar: 3 }, learned_by_type: { vocabulary: 1, kanji: 1, grammar: 0 }, active_session_id: null, available_new: 1, recent_activity: [{ item_id: "jp-school", item_type: "vocabulary", title: "学校", rating: "good", reviewed_at: "2026-11-17T00:00:00Z", origin: "web_practice" }] });
    studyApi.lessons.mockResolvedValue([]);
    studyApi.course.mockResolvedValue([]);
  });

  it("shows composite lessons beside the three subject accordions, collapsed by default", async () => {
    render(wrap(<LearningHomeView />));
    const names = ["Bài học tổng hợp N3", "Từ vựng", "Kanji", "Ngữ pháp"];
    const findAccordion = (name: string) => screen.getAllByRole("button").find(button => button.hasAttribute("aria-controls") && button.textContent?.includes(name));
    await waitFor(() => expect(screen.getAllByRole("button").filter(button => button.hasAttribute("aria-controls"))).toHaveLength(4));
    expect(document.getElementById("composite-lessons")).toBeInTheDocument();
    for (const name of names) expect(findAccordion(name)).toHaveAttribute("aria-expanded", "false");
    fireEvent.click(findAccordion("Ngữ pháp")!);
    expect(findAccordion("Ngữ pháp")).toHaveAttribute("aria-expanded", "true");
    expect(findAccordion("Từ vựng")).toHaveAttribute("aria-expanded", "false");
    fireEvent.click(findAccordion("Ngữ pháp")!);
    expect(findAccordion("Ngữ pháp")).toHaveAttribute("aria-expanded", "false");
    expect(findAccordion("Bài học tổng hợp N3")).toHaveAttribute("aria-expanded", "false");
  });

  it("updates the learning page body in Vietnamese, English, and Japanese without changing source content", async () => {
    render(wrap(<LearningHomeView />, true));
    const selector = () => screen.getByRole("combobox", { name: "Ngôn ngữ giao diện" });
    await screen.findByText("Tiến độ theo nội dung");
    expect(screen.getAllByText("Từ vựng", { selector: "span" }).length).toBeGreaterThan(0);
    expect(screen.getByText("Tiến độ theo nội dung")).toBeInTheDocument();
    expect(screen.getByText("学校")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Ôn bài/ })).toBeInTheDocument();

    fireEvent.change(selector(), { target: { value: "en" } });
    await screen.findByText("Progress by content");
    expect(screen.getByText("N3 composite lessons")).toBeInTheDocument();
    expect(screen.getByText("Progress by content")).toBeInTheDocument();
    expect(screen.getByText("Recent activity")).toBeInTheDocument();
    expect(screen.getByText("学校")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Review/ })).toBeInTheDocument();

    fireEvent.change(screen.getByRole("combobox", { name: "Interface language" }), { target: { value: "ja" } });
    await screen.findByText("学習");
    expect(screen.getByText("N3総合レッスン")).toBeInTheDocument();
    expect(screen.getByText("種類別の進捗")).toBeInTheDocument();
    expect(screen.getByText("最近の学習")).toBeInTheDocument();
    expect(screen.getByText("学校")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /復習/ })).toBeInTheDocument();
    expect(document.documentElement.lang).toBe("ja");
  });

  it("localizes search empty state and startup errors", async () => {
    studyApi.start.mockRejectedValue(new Error("server detail"));
    render(wrap(<LearningHomeView />, true));
    await screen.findByText("Tiến độ theo nội dung");
    fireEvent.change(screen.getByRole("combobox", { name: "Ngôn ngữ giao diện" }), { target: { value: "en" } });
    fireEvent.click(screen.getByRole("button", { name: /Vocabulary/ }));
    fireEvent.change(screen.getByRole("textbox", { name: "Search lessons" }), { target: { value: "no-such-lesson" } });
    expect(await screen.findAllByText("No lessons found")).toHaveLength(3);
    fireEvent.click(screen.getByRole("button", { name: /Review/ }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Could not start the study session. Please try again.");
  });

  it("uses the same Vietnamese server snapshot during hydration, then applies the saved locale", async () => {
    localStorage.setItem("jlpt-locale", "en");
    const element = wrap(<LearningHomeView />);
    const serverMarkup = renderToString(element);
    expect(serverMarkup).toContain("Học tập");
    expect(serverMarkup).not.toContain(">Learning<");

    const container = document.createElement("div");
    container.innerHTML = serverMarkup;
    document.body.append(container);
    const consoleError = vi.spyOn(console, "error").mockImplementation(() => {});
    let root: ReturnType<typeof hydrateRoot>;
    await act(async () => { root = hydrateRoot(container, element); });
    await waitFor(() => expect(container).toHaveTextContent("Learning"));
    expect(consoleError.mock.calls.flat().join(" ")).not.toMatch(/hydration failed|didn't match|server rendered html/i);
    consoleError.mockRestore();
    await act(async () => root.unmount());
    container.remove();
  });
});
