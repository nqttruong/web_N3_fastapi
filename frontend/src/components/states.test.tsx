import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { ResultBadge } from "@/components/badges";
import { EmptyState, ErrorState } from "@/components/states";
import { ApiError } from "@/lib/api/client";
import { LocaleProvider } from "@/lib/i18n";

describe("state components", () => {
  it("ErrorState shows the API message and retries", async () => {
    const onRetry = vi.fn();
    render(<ErrorState error={new ApiError(500, "internal_error", "Máy chủ lỗi")} onRetry={onRetry} />);
    expect(screen.getByRole("alert")).toHaveTextContent("Máy chủ lỗi");
    await userEvent.click(screen.getByRole("button", { name: /thử lại/i }));
    expect(onRetry).toHaveBeenCalledOnce();
  });

  it("ErrorState hides retry for 404", () => {
    render(<ErrorState error={new ApiError(404, "not_found", "Không tìm thấy đề thi.")} onRetry={() => {}} />);
    expect(screen.getByText("Không tìm thấy dữ liệu")).toBeInTheDocument();
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });

  it.each([
    ["vi", "Yêu cầu không thành công. Hãy thử lại hoặc xem chi tiết lỗi.", "Chi tiết lỗi"],
    ["en", "The request failed. Try again or review the error details.", "Error details"],
    ["ja", "リクエストに失敗しました。再試行するか、エラーの詳細を確認してください。", "エラーの詳細"],
  ])("localizes generic API error UI in %s and keeps diagnostics expandable", (locale, message, details) => {
    localStorage.setItem("jlpt-locale", locale);
    render(<LocaleProvider><ErrorState error={new ApiError(500, "internal_error", "Backend detail")}/></LocaleProvider>);
    expect(screen.getByText(message)).toBeInTheDocument();
    expect(screen.getByText(details)).toBeInTheDocument();
    expect(screen.getByText("Backend detail")).toBeInTheDocument();
  });

  it("EmptyState renders title and description", () => {
    render(<EmptyState title="Kho đề đang trống" description="Tạo đề đầu tiên" />);
    expect(screen.getByText("Kho đề đang trống")).toBeInTheDocument();
  });

  it.each([
    [true, true, "Đúng"],
    [false, true, "Sai"],
    [null, true, "Chưa chấm"],
    [null, false, "Bỏ trống"],
  ])("ResultBadge(%s, answered=%s) → %s", (isCorrect, answered, label) => {
    render(<ResultBadge isCorrect={isCorrect} answered={answered} />);
    expect(screen.getByText(label)).toBeInTheDocument();
  });
});
