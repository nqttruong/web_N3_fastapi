import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { afterAll, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";

import { LocaleProvider, useLocale } from "@/lib/i18n";
import { api } from "@/lib/api/endpoints";
import { JlptAnalyticsView } from "./jlpt-analytics-view";
import { MistakesView } from "@/features/attempts/mistakes-view";
import { AttemptList } from "@/features/attempts/attempt-list";
import { ExamLibrary } from "@/features/exams/exam-library";
import { ImportList } from "@/features/imports/import-list";
import { ExamDetail } from "@/features/exams/exam-detail";
import { AttemptDetailView } from "@/features/attempts/attempt-detail";

vi.mock("next/link", () => ({ default: ({ href, children, ...props }: React.PropsWithChildren<{ href: string }>) => <a href={href} {...props}>{children}</a> }));
vi.mock("next/navigation", () => ({
  usePathname: () => "/exams",
  useRouter: () => ({ replace: vi.fn(), push: vi.fn(), back: vi.fn() }),
  useParams: () => ({ id: "id-1" }),
  useSearchParams: () => new URLSearchParams(),
}));
vi.mock("@/features/explanations/ai-review-panel", () => ({ AiReviewPanel: () => null }));

const emptyPage = { data: [], meta: { page: 1, page_size: 20, total: 0, total_pages: 0 } };
const emptyAnalytics = {
  attempt_count: 0, correct: 0, incorrect: 0, unanswered: 0, ungraded: 0,
  accuracy: null, correct_over_all: null, average_duration_seconds: null,
  skill_results: {}, mistakes_by_question_type: {}, trend: [], repeated_exams: [], sources: {},
  android_attempt_count: null, listening_data_available: false, score_note: "score note should not be shown raw",
};

function renderWithLocale(ui: ReactNode) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<LocaleProvider><QueryClientProvider client={client}>{ui}</QueryClientProvider></LocaleProvider>);
}

beforeEach(() => {
  localStorage.setItem("jlpt-locale", "vi");
  vi.spyOn(api, "jlptAnalytics").mockResolvedValue(emptyAnalytics);
  vi.spyOn(api, "listExams").mockResolvedValue(emptyPage as never);
  vi.spyOn(api, "listMistakes").mockResolvedValue(emptyPage as never);
  vi.spyOn(api, "listAttempts").mockResolvedValue(emptyPage as never);
  vi.spyOn(api, "listImports").mockResolvedValue(emptyPage as never);
  vi.spyOn(api, "listQuestions").mockResolvedValue(emptyPage as never);
  vi.spyOn(api, "listPassages").mockResolvedValue([] as never);
  vi.spyOn(api, "getExam").mockResolvedValue({
    id: "id-1", source_id: null, source_name: null, source_url: null, level: "N3", category: "grammar",
    title: "試験タイトル", description: null, status: "ready", question_count: 0, verified_answer_count: 0,
    attempt_count: 0, latest_attempt_started_at: null, latest_attempt_accuracy: null, approved_explanation_count: 0,
    created_at: "2026-11-18T00:00:00Z", updated_at: "2026-11-18T00:00:00Z",
  } as never);
  vi.spyOn(api, "getAttempt").mockResolvedValue({
    id: "attempt-1", exam_id: "id-1", exam_title: "試験タイトル", exam_category: "grammar",
    started_at: "2026-11-18T00:00:00Z", completed_at: "2026-11-18T00:30:00Z", total_questions: 0,
    correct_count: 0, incorrect_count: 0, unanswered_count: 0, ungraded_count: 0, source: "practice",
    accuracy: null, approved_explanation_count: 0, pending_explanation_count: 0, created_at: "2026-11-18T00:00:00Z",
    exam_source_url: null, answers: [],
  } as never);
});

beforeAll(() => {
  vi.stubGlobal("ResizeObserver", class {
    observe() {}
    unobserve() {}
    disconnect() {}
  });
});

afterAll(() => vi.unstubAllGlobals());

describe("exam and analytics UI localization", () => {
  it.each([
    ["vi", "Phân tích JLPT", "Chưa có dữ liệu bài thi", "Sổ lỗi sai"],
    ["en", "JLPT analysis", "No exam data yet", "Mistake notebook"],
    ["ja", "JLPT分析", "試験データはありません", "間違いノート"],
  ])("renders analytics and mistake states in %s", async (locale, analyticsTitle, noAnalytics, mistakesTitle) => {
    localStorage.setItem("jlpt-locale", locale);
    const { rerender } = renderWithLocale(<JlptAnalyticsView />);
    expect(await screen.findByText(analyticsTitle)).toBeInTheDocument();
    expect(screen.getByText(noAnalytics)).toBeInTheDocument();
    expect(screen.queryByText("score note should not be shown raw")).not.toBeInTheDocument();
    rerender(<LocaleProvider><QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><MistakesView /></QueryClientProvider></LocaleProvider>);
    expect(await screen.findByText(mistakesTitle)).toBeInTheDocument();
  });

  it("updates visible analytics UI when locale changes without remounting", async () => {
    const { container } = renderWithLocale(<><LocalePicker /><JlptAnalyticsView /></>);
    expect(await screen.findByText("Phân tích JLPT")).toBeInTheDocument();
    fireEvent.change(screen.getByRole("combobox"), { target: { value: "ja" } });
    await waitFor(() => expect(screen.getByText("JLPT分析")).toBeInTheDocument());
    expect(container).toHaveTextContent("試験データはありません");
  });

  it.each([
    ["vi", "Độ chính xác = đúng / (đúng + sai)"],
    ["en", "Accuracy = correct / (correct + incorrect)"],
    ["ja", "正答率 = 正解 / (正解 + 不正解)"],
  ])("localizes scoring explanation in %s without showing backend-language notes", async (locale, scoreText) => {
    localStorage.setItem("jlpt-locale", locale);
    vi.mocked(api.jlptAnalytics).mockResolvedValue({ ...emptyAnalytics, attempt_count: 1, correct: 1, incorrect: 1, accuracy: 0.5, correct_over_all: 0.5 });
    const { container } = renderWithLocale(<JlptAnalyticsView />);
    await waitFor(() => expect(container).toHaveTextContent(scoreText));
    expect(container).not.toHaveTextContent("score note should not be shown raw");
  });

  it.each([
    ["vi", "Kho đề", "Kho đề đang trống", "Bài làm", "Chưa có bản nháp nào"],
    ["en", "Exam library", "Your exam library is empty", "Attempts", "No import drafts"],
    ["ja", "試験ライブラリ", "試験ライブラリは空です", "受験履歴", "インポート下書きはありません"],
  ])("localizes exam library, attempts, and import draft empty states in %s", async (locale, examTitle, noExam, attemptsTitle, noDrafts) => {
    localStorage.setItem("jlpt-locale", locale);
    const { unmount } = renderWithLocale(<ExamLibrary />);
    expect(await screen.findByText(examTitle)).toBeInTheDocument();
    expect(await screen.findByText(noExam)).toBeInTheDocument();
    unmount();
    const attempts = renderWithLocale(<AttemptList />);
    expect(await screen.findByText(attemptsTitle)).toBeInTheDocument();
    attempts.unmount();
    renderWithLocale(<ImportList embedded />);
    expect(await screen.findByText(noDrafts)).toBeInTheDocument();
  });

  it.each([
    ["vi", "Lịch sử", "Chưa có lần làm nào", "Tổng kết", "Chi tiết câu trả lời"],
    ["en", "History", "No attempts yet", "Summary", "Answer details"],
    ["ja", "履歴", "受験履歴はありません", "概要", "解答詳細"],
  ])("localizes exam detail and attempt result in %s", async (locale, history, noAttempts, summary, details) => {
    localStorage.setItem("jlpt-locale", locale);
    const exam = renderWithLocale(<ExamDetail />);
    expect(await screen.findByText(history)).toBeInTheDocument();
    expect(screen.getByText(noAttempts)).toBeInTheDocument();
    exam.unmount();
    renderWithLocale(<AttemptDetailView />);
    expect(await screen.findByLabelText(summary)).toBeInTheDocument();
    expect(screen.getByText(details)).toBeInTheDocument();
  });
});

function LocalePicker() {
  const { locale, setLocale } = useLocale();
  return <select aria-label="locale" value={locale} onChange={(e) => setLocale(e.target.value as "vi" | "en" | "ja")}><option value="vi">vi</option><option value="en">en</option><option value="ja">ja</option></select>;
}
