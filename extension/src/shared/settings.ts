import type { ExtensionSettings } from "./contracts.js";

export const DEFAULT_SETTINGS: ExtensionSettings = {
  apiBaseUrl: "http://127.0.0.1:8000/api/v1",
  frontendBaseUrl: "http://127.0.0.1:3000",
  token: "",
  dictionaryToken: "",
};

function validLoopbackUrl(raw: string, allowPath: boolean): URL | null {
  try {
    const url = new URL(raw);
    if (
      !["http:", "https:"].includes(url.protocol) ||
      !["127.0.0.1", "localhost"].includes(url.hostname) ||
      url.username ||
      url.password ||
      url.search ||
      url.hash ||
      (!allowPath && url.pathname !== "/")
    ) return null;
    return url;
  } catch {
    return null;
  }
}

export function normalizeApiBaseUrl(raw: string): string | null {
  const url = validLoopbackUrl(raw.trim(), true);
  if (!url) return null;
  url.pathname = url.pathname.replace(/\/+$/, "");
  return url.toString().replace(/\/$/, "");
}

export function normalizeFrontendBaseUrl(raw: string): string | null {
  const url = validLoopbackUrl(raw.trim(), false);
  return url ? url.origin : null;
}

export async function getSettings(): Promise<ExtensionSettings> {
  const stored = await chrome.storage.local.get(["apiBaseUrl", "frontendBaseUrl", "token", "dictionaryToken"]);
  return {
    apiBaseUrl: normalizeApiBaseUrl(String(stored.apiBaseUrl ?? "")) ?? DEFAULT_SETTINGS.apiBaseUrl,
    frontendBaseUrl: normalizeFrontendBaseUrl(String(stored.frontendBaseUrl ?? "")) ?? DEFAULT_SETTINGS.frontendBaseUrl,
    token: typeof stored.token === "string" ? stored.token : "",
    dictionaryToken: typeof stored.dictionaryToken === "string" ? stored.dictionaryToken : "",
  };
}
