import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const { apiRequest, toDataURL } = vi.hoisted(() => ({
  apiRequest: vi.fn(),
  toDataURL: vi.fn(),
}));

vi.mock("@/lib/api/client", () => ({ apiRequest }));
vi.mock("qrcode", () => ({ default: { toDataURL } }));

import { QRPairingPanel } from "./qr-pairing-panel";

const session = {
  id: "session-123",
  status: "WAITING_FOR_DEVICE",
  device_name: null,
  device_id: null,
  expires_at: "2026-11-18T12:05:00Z",
  qr_payload: {
    version: 1,
    base_url: "https://jlpt.example.test",
    session_id: "session-123",
    challenge: "short-lived-challenge-that-is-not-a-token",
    expires_at: "2026-11-18T12:05:00Z",
  },
};
let paired = false;

function renderPanel() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}><QRPairingPanel adminKey="admin-secret" /></QueryClientProvider>);
}

describe("QR pairing panel", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    paired = false;
    toDataURL.mockResolvedValue("data:image/png;base64,bW9jay1xci1pbWFnZQ==");
    apiRequest.mockImplementation(async (path: string, options?: { method?: string; body?: { confirmation_code?: string } }) => {
      if (path === "/sync/admin/qr-sessions" && options?.method === "POST") return { data: session };
      if (path === "/sync/admin/qr-sessions/session-123" && options?.method !== "POST") {
        return { data: { ...session, status: paired ? "PAIRED" : "AWAITING_CONFIRMATION", device_name: "Mock Android" } };
      }
      if (path === "/sync/admin/qr-sessions/session-123/confirm") {
        paired = true;
        return { data: { ...session, status: "PAIRED", device_name: "Mock Android", device_id: "device-123" } };
      }
      throw new Error(`Unexpected API call ${path}`);
    });
  });

  it("creates the QR, waits for a device, confirms the code, and distinguishes pairing from sync", async () => {
    renderPanel();
    fireEvent.click(screen.getByRole("button", { name: "Tạo mã QR" }));
    expect(await screen.findByRole("img", { name: /có hiệu lực trong 5 phút/i })).toBeInTheDocument();
    expect(await screen.findByText("Chờ bạn xác nhận mã trên Android")).toBeInTheDocument();
    expect(screen.getByText(/Mock Android/)).toBeInTheDocument();
    expect(screen.queryByText(session.qr_payload.challenge)).not.toBeInTheDocument();

    fireEvent.change(screen.getByRole("textbox", { name: "Mã xác nhận trên Android" }), { target: { value: "123456" } });
    fireEvent.click(screen.getByRole("button", { name: "Xác nhận ghép nối" }));
    await waitFor(() => expect(screen.getByText("Ghép nối thành công")).toBeInTheDocument());
    expect(screen.getByText(/cần gọi bootstrap\/pull\/push để thực sự đồng bộ dữ liệu/i)).toBeInTheDocument();
    expect(apiRequest).toHaveBeenCalledWith("/sync/admin/qr-sessions/session-123/confirm", expect.objectContaining({
      method: "POST",
      headers: { "X-Sync-Admin-Key": "admin-secret" },
      body: { confirmation_code: "123456" },
    }));
  });
});
