import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const { overview } = vi.hoisted(() => ({ overview: vi.fn() }));
vi.mock("@/features/learning-content/study-api", () => ({ studyApi: { overview } }));

import { LocaleProvider } from "@/lib/i18n";
import { DashboardView } from "./dashboard-view";

function renderDashboard() {
  return render(
    <LocaleProvider>
      <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
        <DashboardView />
      </QueryClientProvider>
    </LocaleProvider>,
  );
}

describe("overview is separate from JLPT analytics", () => {
  beforeEach(() => {
    overview.mockResolvedValue({
      content_counts: { vocabulary: 30, kanji: 24, grammar: 7 },
      learned: 8,
      learned_by_type: { vocabulary: 5, kanji: 2, grammar: 1 },
      due: 3,
      available_new: 53,
      saved: 2,
      last_activity_at: "2026-11-18T01:00:00Z",
      active_session_id: null,
      recent_activity: [{ item_id: "v-1", item_type: "vocabulary", title: "学校", rating: "good", reviewed_at: "2026-11-18T01:00:00Z", origin: "web_practice" }],
    });
  });

  it("shows the Japanese quote first, learning snapshot and recent study activity", async () => {
    renderDashboard();
    const quote = await screen.findByText("Danh ngôn Nhật hôm nay");
    const snapshot = await screen.findByRole("region", { name: "Tổng quan học tập" });
    expect(quote.compareDocumentPosition(snapshot) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(screen.getByText("Đã học")).toBeInTheDocument();
    expect(screen.getByText("Hoạt động gần đây")).toBeInTheDocument();
    expect(screen.getByText("学校")).toBeInTheDocument();
    expect(screen.getByRole("progressbar", { name: "Từ vựng · Đã học" })).toHaveAttribute("aria-valuenow", "5");
  });

  it("has no Kho đề, Sổ lỗi sai, Học tập shortcut or detailed exam analytics", async () => {
    renderDashboard();
    await screen.findByText("Danh ngôn Nhật hôm nay");
    expect(screen.queryByRole("link", { name: /Kho đề|Sổ lỗi sai|Học tập|Thêm đề/i })).not.toBeInTheDocument();
    expect(screen.queryByText("Tổng số đề")).not.toBeInTheDocument();
    expect(screen.queryByText("Tỷ lệ chính xác")).not.toBeInTheDocument();
  });
});
