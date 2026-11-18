import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError, apiRequest } from "./client";

function mockFetch(status: number, body: unknown) {
  return vi.spyOn(globalThis, "fetch").mockResolvedValue(
    new Response(body === null ? null : JSON.stringify(body), {
      status,
      headers: { "Content-Type": "application/json" },
    }),
  );
}

afterEach(() => vi.restoreAllMocks());

describe("apiRequest", () => {
  it("returns parsed JSON and builds the query string without empty values", async () => {
    const spy = mockFetch(200, { data: [], meta: { page: 1 } });
    const result = await apiRequest("/exams", { query: { page: 2, q: "", category: undefined } });
    expect(result).toEqual({ data: [], meta: { page: 1 } });
    const url = new URL(String(spy.mock.calls[0]?.[0]));
    expect(url.pathname.endsWith("/api/v1/exams")).toBe(true);
    expect(url.searchParams.get("page")).toBe("2");
    expect(url.searchParams.has("q")).toBe(false);
  });

  it("maps the backend error envelope to ApiError", async () => {
    mockFetch(422, {
      error: {
        code: "validation_error",
        message: "Dữ liệu gửi lên không hợp lệ.",
        details: [{ loc: ["body", "title"], msg: "too short", type: "string_too_short" }],
      },
    });
    const error = (await apiRequest("/exams", { method: "POST", body: {} }).catch((e: unknown) => e)) as ApiError;
    expect(error).toBeInstanceOf(ApiError);
    expect(error.status).toBe(422);
    expect(error.code).toBe("validation_error");
    expect(error.fieldErrors()).toEqual({ title: "too short" });
  });

  it("reports network failures in Vietnamese", async () => {
    vi.spyOn(globalThis, "fetch").mockRejectedValue(new TypeError("Failed to fetch"));
    const error = (await apiRequest("/health").catch((e: unknown) => e)) as ApiError;
    expect(error).toBeInstanceOf(ApiError);
    expect(error.code).toBe("network_error");
  });

  it("handles 204 No Content", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(null, { status: 204 }));
    await expect(apiRequest("/questions/x", { method: "DELETE" })).resolves.toBeUndefined();
  });
});
