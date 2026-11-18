import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const { studyApi } = vi.hoisted(() => ({ studyApi: { answerExercise: vi.fn() } }));
vi.mock("./study-api", () => ({ studyApi }));

import { GrammarExercises } from "./grammar-exercise";
import type { StudyItem } from "./study-api";

const item = {
  id: "item-1", item_type: "grammar", pack_id: "pack", lesson_id: "lesson", lesson_title: "Bài 1",
  payload: { pattern: "〜ばかり", meaningVi: "vừa mới", exercises: [{ id: "ex-1", prompt: "{日本|にほん}に＿＿＿ばかりです。", options: ["来る", "来た"], answerIndex: 1, explanationVi: "Thể た + ばかり" }] },
  examples: [], saved: false, progress: null, exercise_results: {},
} as StudyItem;

function wrap(node: ReactNode) {
  return <QueryClientProvider client={new QueryClient()}>{node}</QueryClientProvider>;
}

describe("grammar practice", () => {
  beforeEach(() => { vi.clearAllMocks(); studyApi.answerExercise.mockResolvedValue({ selected_index: 0, is_correct: false, answer_index: 1, explanation_vi: "Thể た + ばかり", duplicate: false }); });

  it("persists a real source question answer and shows the verified source explanation", async () => {
    render(wrap(<GrammarExercises item={item} />));
    expect(screen.getByText("日本").closest("ruby")).toHaveTextContent("にほん");
    fireEvent.click(screen.getByRole("button", { name: "来る" }));
    await waitFor(() => expect(studyApi.answerExercise).toHaveBeenCalledWith("item-1", "ex-1", expect.any(String), 0));
    expect(await screen.findByText(/Chưa đúng/)).toBeInTheDocument();
    expect(screen.getByText("Thể た + ばかり")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Làm lại" }));
    expect(screen.getByRole("button", { name: "来た" })).toBeEnabled();
  });

  it("restores the latest stored answer after reload", () => {
    render(wrap(<GrammarExercises item={{ ...item, exercise_results: { "ex-1": { selected_index: 1, is_correct: true, answered_at: "2026-11-17T00:00:00Z" } } }} />));
    expect(screen.getByText("Đúng")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "来る" })).toBeDisabled();
  });
});
