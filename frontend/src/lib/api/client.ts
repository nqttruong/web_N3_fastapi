// Thin fetch wrapper for the FastAPI backend. The browser talks to the API directly;
// it never touches the database and holds no secrets.

export function assetUrl(path: string): string {
  return `${API_BASE_URL}${path}`;
}

export const API_BASE_URL = (
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000/api/v1"
).replace(/\/$/, "");

export interface ApiErrorDetail {
  loc?: (string | number)[];
  msg?: string;
  type?: string;
}

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly details: unknown;

  constructor(status: number, code: string, message: string, details: unknown = null) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.details = details;
  }

  /** Field-level messages keyed by the last element of `loc` (e.g. "title"). */
  fieldErrors(): Record<string, string> {
    const result: Record<string, string> = {};
    if (!Array.isArray(this.details)) return result;
    for (const item of this.details as ApiErrorDetail[]) {
      const field = item.loc?.filter((part) => part !== "body").join(".");
      if (field && item.msg && !(field in result)) result[field] = item.msg;
    }
    return result;
  }
}

type Query = Record<string, string | number | boolean | null | undefined>;

function buildUrl(path: string, query?: Query): string {
  const url = new URL(`${API_BASE_URL}${path}`);
  if (query) {
    for (const [key, value] of Object.entries(query)) {
      if (value !== undefined && value !== null && value !== "") {
        url.searchParams.set(key, String(value));
      }
    }
  }
  return url.toString();
}

export async function apiRequest<T>(
  path: string,
  init: { method?: string; body?: unknown; query?: Query; signal?: AbortSignal; headers?: HeadersInit } = {},
): Promise<T> {
  let response: Response;
  // FormData (file uploads) lets the browser set the multipart boundary itself.
  const isForm = typeof FormData !== "undefined" && init.body instanceof FormData;
  try {
    response = await fetch(buildUrl(path, init.query), {
      method: init.method ?? "GET",
      headers: {
        ...(init.body !== undefined && !isForm ? { "Content-Type": "application/json" } : {}),
        ...Object.fromEntries(new Headers(init.headers).entries()),
      },
      body: init.body === undefined ? undefined : isForm ? (init.body as FormData) : JSON.stringify(init.body),
      signal: init.signal,
      cache: "no-store",
    });
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") throw error;
    throw new ApiError(
      0,
      "network_error",
      "Không kết nối được tới máy chủ API. Hãy kiểm tra backend đã chạy chưa.",
    );
  }

  if (response.status === 204) return undefined as T;

  let payload: unknown = null;
  try {
    payload = await response.json();
  } catch {
    payload = null;
  }

  if (!response.ok) {
    const error = (payload as { error?: { code?: string; message?: string; details?: unknown } })
      ?.error;
    throw new ApiError(
      response.status,
      error?.code ?? "http_error",
      error?.message ?? `Yêu cầu thất bại (HTTP ${response.status}).`,
      error?.details ?? null,
    );
  }
  return payload as T;
}
