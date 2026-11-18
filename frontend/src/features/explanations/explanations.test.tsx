import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
import type { ReactNode } from "react";
import { describe, expect, it, vi } from "vitest";

import type { AttemptExplanationOverview, ExplanationPayload } from "@/lib/api/types";
import { LocaleProvider } from "@/lib/i18n";

import { ExplanationView } from "./explanation-view";
import { checkJsonSyntax, ManualMode } from "./manual-mode";

vi.mock("next/navigation", () => ({ useSearchParams: () => new URLSearchParams() }));

const payload: ExplanationPayload = {
  schema_version: "1.0",
  question_id: "q1",
  correct_answer_index: 1,
  translation_vi: "Vì trời mưa nên trận đấu bị huỷ.",
  solution_summary_vi: "Chọn mẫu chỉ nguyên nhân.",
  correct_explanation: "ので nêu nguyên nhân khách quan.",
  recognition_tips: "Vế sau là kết quả.",
  options_analysis: [
    { option_index: 0, option_text: "のに", meaning_vi: "vậy mà", is_correct: false, reason: "Trái với mong đợi, không hợp.", when_it_would_be_correct: "Khi kết quả bất ngờ.", difference_from_correct: "Ngược nghĩa.", common_misconception: "Âm gần giống ので.", how_to_distinguish: "のに = bất mãn.", example_ja: "勉強したのに、落ちた。", example_vi: "Đã học vậy mà trượt." },
    { option_index: 1, option_text: "ので", meaning_vi: "vì", is_correct: true, reason: "Nêu nguyên nhân.", when_it_would_be_correct: null, difference_from_correct: null, common_misconception: null, how_to_distinguish: null, example_ja: null, example_vi: null },
  ],
  grammar_points: [{ pattern: "〜ので", meaning_vi: "vì", usage: "Nguyên nhân khách quan.", contrast: null, example_ja: null }],
  vocabulary: [{ surface: "試合", reading: "しあい", meaning_vi: "trận đấu", note: null }],
  kanji: [],
  sentence_structure: null,
  evidence: [],
  key_takeaway: "ので = nguyên nhân; のに = trái mong đợi.",
  review_topics: ["〜ので"],
  quality: { context_sufficient: true, source_answer_concern: null, uncertainty_notes: [] },
};

describe("ExplanationView", () => {
  it("shows 1-based answers, every wrong option and the learner analysis", () => {
    render(
      <ExplanationView
        payload={payload}
        learner={{ selected_answer_index: 0, is_correct: false, selected_option_text: "のに", possible_misconception: "Âm gần giống ので.", how_to_distinguish: "のに = bất mãn.", study_advice: "Ôn lại 〜ので." }}
      />,
    );
    expect(screen.getByText("Đáp án đúng").parentElement).toHaveTextContent("2. ので");
    expect(screen.getByText("Bạn đã chọn")).toBeInTheDocument();
    expect(screen.getByText("Khi nào có thể đúng:")).toBeInTheDocument();
    expect(screen.getByText("Có thể nhầm vì:")).toBeInTheDocument();
    expect(screen.getByText("しあい")).toBeInTheDocument();
  });

  it("never invents a learner error without data", () => {
    render(<ExplanationView payload={payload} learner={null} />);
    expect(screen.getByText(/Không có dữ liệu lựa chọn của bạn/)).toBeInTheDocument();
    expect(screen.queryByText("Bạn đã chọn")).toBeNull();
  });

  it.each([
    ["vi", "A. Tổng quan", "Đáp án đúng"],
    ["en", "A. Overview", "Correct answer"],
    ["ja", "A. 概要", "正解"],
  ])("localizes explanation controls in %s without translating saved study content", (locale, overviewLabel, correctLabel) => {
    localStorage.setItem("jlpt-locale", locale);
    render(<LocaleProvider><ExplanationView payload={payload} learner={null} /></LocaleProvider>);
    expect(screen.getByText(overviewLabel)).toBeInTheDocument();
    expect(screen.getByText(correctLabel)).toBeInTheDocument();
    expect(screen.getByText("Vì trời mưa nên trận đấu bị huỷ.")).toBeInTheDocument();
  });
});

describe("checkJsonSyntax", () => {
  it("accepts JSON with or without a code fence and reports errors", () => {
    expect(checkJsonSyntax('{"explanations": []}')).toBeNull();
    expect(checkJsonSyntax('```json\n{"a": 1}\n```')).toBeNull();
    expect(checkJsonSyntax("{oops")).not.toBeNull();
  });
});

describe("manual ChatGPT review entry state", () => {
  it.each([
    ["vi", "Chưa chọn câu hỏi", "Mở một bài làm hoặc một câu hỏi"],
    ["en", "No questions selected", "Open an attempt or question"],
    ["ja", "問題が選択されていません", "受験または問題を開き"],
  ])("localizes the manual review entry state in %s", (locale, title, hint) => {
    localStorage.setItem("jlpt-locale", locale);
    render(wrap(<ManualMode />));
    expect(screen.getByText(title)).toBeInTheDocument();
    expect(screen.getByText(new RegExp(hint))).toBeInTheDocument();
  });
});

const overview: AttemptExplanationOverview = {
  attempt_id: "a1",
  wrong_count: 2,
  eligible_wrong_count: 1,
  explained_wrong_count: 0,
  needs_review_count: 0,
  items: [
    { attempt_answer_id: "aa1", question_id: "q1", question_number: 1, selected_answer: 2, is_correct: false, eligible: true, ineligible_code: null, explanation_id: null, explanation_status: null },
    { attempt_answer_id: "aa2", question_id: "q2", question_number: 2, selected_answer: 1, is_correct: false, eligible: false, ineligible_code: "answer_not_verified", explanation_id: null, explanation_status: null },
  ],
  latest_job: {
    id: "j1", attempt_id: "a1", status: "partial_failed", force: false,
    counts: { total: 1, pending: 0, running: 0, succeeded: 0, cached: 0, failed: 1, skipped: 0, cancelled: 0 },
    items: [{ id: "i1", question_id: "q1", question_number: 1, attempt_answer_id: "aa1", status: "failed", tries: 1, error_code: "provider_timeout", error_message: "Gọi AI quá thời gian chờ.", explanation_id: null }],
    created_at: "2026-11-10T00:00:00Z", started_at: null, finished_at: null,
  },
};

vi.mock("@/lib/api/endpoints", () => ({
  api: {
    aiCapabilities: vi.fn(async () => ({ api_available: false, provider: "openai", model: "m", reason: "Chưa cấu hình OPENAI_API_KEY.", prompt_version: "v1", schema_version: "1.0", max_concurrent_requests: 2, batch_max_questions: 50, budget: {} })),
    attemptExplanations: vi.fn(async () => overview),
  },
}));

function wrap(node: ReactNode) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <LocaleProvider><QueryClientProvider client={client}>{node}</QueryClientProvider></LocaleProvider>;
}

describe("AiReviewPanel", () => {
  it.each([
    ["vi", "Hoàn tất một phần (có câu lỗi)", "Các câu sai", "Xuất prompt"],
    ["en", "Partially completed (some questions failed)", "Incorrect questions", "Export prompt"],
    ["ja", "一部完了（失敗した問題あり）", "不正解の問題", "プロンプトを出力"],
  ])("localizes the review panel and keeps its manual fallback in %s", async (locale, status, listLabel, promptLabel) => {
    localStorage.setItem("jlpt-locale", locale);
    const { AiReviewPanel } = await import("./ai-review-panel");
    render(wrap(<AiReviewPanel attemptId="a1" />));
    expect(await screen.findByTestId("job-status")).toHaveTextContent(status);
    expect(screen.getByText("Gọi AI quá thời gian chờ.")).toBeInTheDocument();
    expect(screen.getByText(locale === "ja" ? "解答未確認" : locale === "en" ? "Answer not verified" : "Chưa xác nhận đáp án")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /AI chữa các câu sai/ })).toBeNull(); // no fake button
    const manual = screen.getByRole("link", { name: new RegExp(`${promptLabel}.*1`) });
    expect(manual).toHaveAttribute("href", "/explanations/manual?q=q1&attempt=a1");
    const list = screen.getByRole("list", { name: listLabel });
    expect(within(list).getAllByRole("checkbox")[1]).toBeDisabled();
  });
});
