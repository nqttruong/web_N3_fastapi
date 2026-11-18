import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const { api } = vi.hoisted(() => ({
  api: {
    learningContentStatus: vi.fn(),
    listLearningContent: vi.fn(),
    requestLearningContentSync: vi.fn(),
  },
}));

vi.mock("@/lib/api/endpoints", () => ({ api }));

import { LearningContentView } from "./learning-content-view";
import { LearningSyncSettingsView } from "./learning-sync-settings-view";

const status = {
  source_configured: true,
  source_available: true,
  source_description: "Git-tracked Android content assets (read-only)",
  interval_minutes: 30,
  last_checked_at: "2026-11-16T03:00:00Z",
  last_success_at: "2026-11-16T03:00:00Z",
  current_versions: [
    {
      id: "n3-kanji",
      title: "Kanji N3",
      jlpt_level: "N3",
      source_version: 3,
      source_commit_sha: "1234567890abcdef",
      license_blocked_count: 7,
      active_item_count: 1,
      synced_at: "2026-11-16T03:00:00Z",
      is_archived: false,
    },
  ],
  active_counts: { vocabulary: 0, kanji: 1, grammar: 0 },
  last_run: {
    id: "run-1",
    status: "succeeded",
    trigger: "startup",
    source_commit_sha: "1234567890abcdef",
    source_manifest_hash: "abcdef1234567890",
    counts: { new_kanji: 1, license_blocked: 7 },
    error: null,
    attempts: 1,
    requested_at: "2026-11-16T03:00:00Z",
    started_at: "2026-11-16T03:00:01Z",
    finished_at: "2026-11-16T03:00:02Z",
  },
};

function wrap(node: ReactNode) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={client}>{node}</QueryClientProvider>;
}

describe("learning content views", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    api.learningContentStatus.mockResolvedValue(status);
    api.listLearningContent.mockResolvedValue({
      items: [
        {
          id: "item-1",
          stable_source_id: "n3-kanji:kanji:n3k-k01",
          item_type: "kanji",
          jlpt_level: "N3",
          pack_id: "n3-kanji",
          pack_title: "Kanji N3",
          source_version: 3,
          lesson_id: "n3k-l01",
          lesson_number: 1,
          lesson_title: "Kanji N3 · bài 1",
          order_index: 0,
          source_name: "N3.pdf / KANJIDIC2",
          source_license: "CC BY-SA 4.0",
          payload: { character: "学", meaningVi: "học", onReadings: ["ガク"], kunReadings: ["まな.ぶ"] },
          examples: [{ japanese: "学校へ行く。", furigana: "{学校|がっこう}へ行く。", translationVi: "Đi đến trường." }],
        },
      ],
      total: 1,
      page: 1,
      page_size: 60,
    });
    api.requestLearningContentSync.mockResolvedValue({ run_id: "run-2", status: "queued", message: "Queued" });
  });

  it("renders mapped Japanese learning content with its source examples", async () => {
    render(wrap(<LearningContentView />));
    expect(screen.getByRole("link", { name: "Bài học tổng hợp N3" })).toHaveAttribute("href", "/learning#composite-lessons");
    expect(screen.queryByRole("button", { name: "Tất cả" })).not.toBeInTheDocument();
    expect(await screen.findByTestId("learning-content-list")).toBeInTheDocument();
    expect(screen.getByText("学")).toBeInTheDocument();
    expect(screen.getByText(/Kun: まな\.ぶ/)).toBeInTheDocument();
    expect(screen.getByText("Đi đến trường.")).toBeInTheDocument();
    expect(screen.getByText(/Bài 1/)).toBeInTheDocument();
  });

  it("pages through real content instead of stopping at the first 60 records", async () => {
    api.listLearningContent.mockImplementation(async ({ page }: { page: number }) => ({
      items: [{ id: `item-${page}`, stable_source_id: `source-${page}`, item_type: "kanji", jlpt_level: "N3", pack_id: "pack", pack_title: "Kanji N3", source_version: 1, lesson_id: "l1", lesson_number: 1, lesson_title: "Bài 1", order_index: 0, source_name: "source", source_license: "licensed", payload: { character: page === 1 ? "学" : "校", meaningVi: "học" }, examples: [] }],
      total: 61, page, page_size: 60,
    }));
    render(wrap(<LearningContentView embedded />));
    expect(await screen.findByText("学")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Trang sau" }));
    expect(await screen.findByText("校")).toBeInTheDocument();
    expect(api.listLearningContent).toHaveBeenCalledWith(expect.objectContaining({ page: 2 }));
  });

  it("exposes current source version and queues manual checks with the provided token", async () => {
    render(wrap(<LearningSyncSettingsView />));
    expect(await screen.findByText(/Kanji N3/)).toBeInTheDocument();
    expect(screen.getByText(/commit 12345678/)).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Learning sync token"), { target: { value: "local-manual-secret" } });
    fireEvent.click(screen.getByRole("button", { name: "Kiểm tra cập nhật bài học" }));
    await waitFor(() => expect(api.requestLearningContentSync).toHaveBeenCalledWith("local-manual-secret"));
  });
});
