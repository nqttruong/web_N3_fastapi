import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const { api } = vi.hoisted(() => ({
  api: {
    listSyncDevices: vi.fn(),
    createSyncPairingCode: vi.fn(),
    revokeSyncDevice: vi.fn(),
  },
}));

vi.mock("@/lib/api/endpoints", () => ({ api }));
vi.mock("next/link", () => ({ default: ({ href, children }: { href: string; children: ReactNode }) => <a href={href}>{children}</a> }));
vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn() } }));

import { SyncManagementView } from "./sync-management-view";

function wrap(node: ReactNode) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={client}>{node}</QueryClientProvider>;
}

describe("Android sync management", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    api.listSyncDevices.mockResolvedValue([]);
    api.createSyncPairingCode.mockResolvedValue({
      pairing_code: "one-time-code",
      expires_at: "2026-11-16T12:10:00Z",
      expires_in_minutes: 10,
    });
    api.revokeSyncDevice.mockResolvedValue({ status: "revoked", device_id: "phone-1" });
  });

  it("does not claim data sync when it only creates a pairing code", async () => {
    render(wrap(<SyncManagementView />));
    fireEvent.click(screen.getByRole("button", { name: "Tạo mã ghép nối" }));
    expect(await screen.findByTestId("pairing-code-result")).toHaveTextContent("Đã tạo · chưa ghép nối");
    expect(screen.getByRole("alert")).toHaveTextContent("Tạo mã không đồng bộ dữ liệu.");
    expect(screen.queryByText("Đồng bộ hoàn tất")).not.toBeInTheDocument();
    expect(api.createSyncPairingCode).toHaveBeenCalledWith("");
  });

  it("shows observed pull/push activity and offers device revocation", async () => {
    api.listSyncDevices.mockResolvedValue([{
      device_id: "phone-1",
      device_name: "N3 Sensei",
      paired_at: "2026-11-15T12:00:00Z",
      last_seen_at: "2026-11-16T12:00:00Z",
      last_pull_at: "2026-11-16T12:01:00Z",
      last_push_at: null,
      revoked_at: null,
    }]);
    render(wrap(<SyncManagementView />));
    expect(await screen.findByText("N3 Sensei")).toBeInTheDocument();
    expect(screen.getByText("Đã ghép nối")).toBeInTheDocument();
    expect(screen.getByText("Request thiết bị gần nhất")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Thu hồi thiết bị" }));
    await waitFor(() => expect(api.revokeSyncDevice).toHaveBeenCalledWith("phone-1", undefined));
  });
});
