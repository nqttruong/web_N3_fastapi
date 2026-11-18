import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { LanguageSwitcher } from "@/components/language-switcher";
import { LocaleProvider } from "@/lib/i18n";

const { api, route, toast } = vi.hoisted(() => ({
  api: { listReviews: vi.fn(), reviewProgress: vi.fn(), getReviewSession: vi.fn(), answerCard: vi.fn(), rateReview: vi.fn(), createReviewSession: vi.fn() },
  route: { session: null as string | null },
  toast: { info: vi.fn(), error: vi.fn(), success: vi.fn() },
}));
vi.mock("@/lib/api/endpoints", () => ({ api }));
vi.mock("next/navigation", () => ({ useRouter: () => ({ replace: vi.fn() }), useSearchParams: () => new URLSearchParams(route.session ? `session=${route.session}` : "") }));
vi.mock("sonner", () => ({ toast }));

import { ReviewsView } from "./reviews-view";

function wrap(node: ReactNode) {
  return <LocaleProvider><LanguageSwitcher /><QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>{node}</QueryClientProvider></LocaleProvider>;
}

const card = { card_id: "card-1", review_item_id: "item-1", review_type: "knowledge_recall", kind: "question", label: "学校", prompt: "学校の意味は？", passage: null, options: ["school", "station"], answered: false, selected_index: null, correct: null, rated: false, answer_index: 0 };
const dueItem = { id: "item-1", review_type: "knowledge_recall", label: "学校", knowledge_id: null, related_knowledge_id: null, source_question_id: null, source_question_ids: [], source_explanation_id: null, status: "active", srs_state: "learning", step_index: 0, interval_minutes: 10, due_at: "2026-11-18T00:00:00Z", last_reviewed_at: null, review_count: 2, lapse_count: 0, algorithm_version: "fsrs", ladder: "[]", version: 1, blocked_reason: null, created_at: "2026-11-01T00:00:00Z", updated_at: "2026-11-01T00:00:00Z" };

describe("Review UI localization", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.setItem("jlpt-locale", "vi");
    route.session = null;
    api.listReviews.mockResolvedValue({ bucket: "due", counts: {}, items: [dueItem] });
    api.reviewProgress.mockResolvedValue({ days: 30, total_reviews: 3, ratings: { again: 0, hard: 1, good: 1, easy: 1 }, answer_accuracy: 2 / 3, answered: 3, due_now: 1, per_day: [] });
    api.getReviewSession.mockResolvedValue({ id: "session-1", cards: [card], created_at: "2026-11-18T00:00:00Z", finished_at: null });
    api.answerCard.mockResolvedValue({ card: { ...card, answered: true, selected_index: 0, correct: true }, reveal: { items: [{ title: "学校", content: "school" }] } });
    api.rateReview.mockResolvedValue({ event: {}, duplicate: false, item: dueItem });
  });

  it("translates the due queue and review metrics in all supported locales", async () => {
    render(wrap(<ReviewsView />));
    expect(await screen.findByText("Hàng đợi đến hạn")).toBeInTheDocument();
    expect(screen.getByText("Ôn tập SRS")).toBeInTheDocument();
    expect(screen.getByText("Nhớ kiến thức")).toBeInTheDocument();

    fireEvent.change(screen.getByRole("combobox", { name: "Ngôn ngữ giao diện" }), { target: { value: "en" } });
    expect(await screen.findByText("SRS review")).toBeInTheDocument();
    expect(screen.getByText("Due queue")).toBeInTheDocument();
    expect(screen.getByText("Recall knowledge")).toBeInTheDocument();
    expect(screen.getByText("Answer accuracy")).toBeInTheDocument();

    fireEvent.change(screen.getByRole("combobox", { name: "Interface language" }), { target: { value: "ja" } });
    expect(await screen.findByText("SRS復習")).toBeInTheDocument();
    expect(screen.getByText("期限のキュー")).toBeInTheDocument();
    expect(screen.getByText("知識を思い出す")).toBeInTheDocument();
    expect(screen.getByText("回答の正答率")).toBeInTheDocument();
    expect(screen.getByText("学校")).toBeInTheDocument();
  });

  it("keeps the active review card and answer state when the locale changes", async () => {
    route.session = "session-1";
    render(wrap(<ReviewsView />));
    expect(await screen.findByText("Thẻ 1: 学校")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "1. school" }));
    expect(await screen.findByText("Bạn trả lời đúng.")).toBeInTheDocument();
    fireEvent.change(screen.getByRole("combobox", { name: "Ngôn ngữ giao diện" }), { target: { value: "en" } });
    expect(await screen.findByText("Correct answer.")).toBeInTheDocument();
    expect(screen.getByText("Rated 0/1 cards.")).toBeInTheDocument();
    expect(screen.getByText("学校")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Good" }));
    await waitFor(() => expect(api.rateReview).toHaveBeenCalledWith(expect.objectContaining({ rating: "good", review_item_id: "item-1", session_id: "session-1" })));
  });

  it("renders answered review controls in Japanese", async () => {
    localStorage.setItem("jlpt-locale", "ja");
    route.session = "session-1";
    api.getReviewSession.mockResolvedValue({ id: "session-1", cards: [{ ...card, answered: true, selected_index: 0, correct: true }], created_at: "2026-11-18T00:00:00Z", finished_at: null });
    render(wrap(<ReviewsView />));
    expect(await screen.findByText("正解です。")).toBeInTheDocument();
    expect(screen.getByText("知識を思い出す")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "よい" })).toBeInTheDocument();
    expect(screen.getByText("学校")).toBeInTheDocument();
  });
});
