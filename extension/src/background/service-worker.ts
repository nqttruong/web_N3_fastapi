import type { BrowserCapture, ExtensionMessage, ExtensionResponse } from "../shared/contracts.js";
import { getSettings } from "../shared/settings.js";

interface ApiEnvelope {
  data?: { id?: string };
  error?: { code?: string; message?: string };
}

let retryingPendingWords = false;

async function ping(): Promise<ExtensionResponse> {
  const { apiBaseUrl } = await getSettings();
  try {
    const response = await fetch(`${apiBaseUrl}/health`, {
      method: "GET",
      cache: "no-store",
      credentials: "omit",
      signal: AbortSignal.timeout(3500),
    });
    if (!response.ok) return { ok: false, message: `Backend trả HTTP ${response.status}.` };
    const payload = (await response.json()) as ApiEnvelope;
    return payload.data ? { ok: true, message: "Backend local đang hoạt động." } : { ok: false, message: "Backend chưa sẵn sàng." };
  } catch {
    return { ok: false, message: "Không kết nối được backend local. Hãy khởi động FastAPI rồi thử lại." };
  }
}

async function importCapture(capture: BrowserCapture): Promise<ExtensionResponse> {
  const { apiBaseUrl, frontendBaseUrl, token } = await getSettings();
  if (!token) return { ok: false, message: "Chưa cấu hình token extension. Mở phần Cài đặt extension." };
  try {
    const response = await fetch(`${apiBaseUrl}/imports/browser-capture`, {
      method: "POST",
      cache: "no-store",
      credentials: "omit",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
      body: JSON.stringify(capture),
      signal: AbortSignal.timeout(10_000),
    });
    const payload = (await response.json()) as ApiEnvelope;
    if (!response.ok) {
      const message = payload.error?.message ?? `Backend trả HTTP ${response.status}.`;
      return { ok: false, message };
    }
    const draftId = payload.data?.id;
    if (!draftId || !/^[0-9a-f-]{36}$/i.test(draftId)) {
      return { ok: false, message: "Backend không trả về draft ID hợp lệ." };
    }
    const target = new URL(`/imports/${draftId}`, frontendBaseUrl).toString();
    await chrome.tabs.create({ url: target, active: true });
    return {
      ok: true,
      message: response.status === 200 ? "Capture này đã nhận trước đó; đã mở lại bản xem trước." : "Đã tạo bản xem trước nhập đề.",
      draftId,
      reused: response.status === 200,
    };
  } catch (error) {
    const message = error instanceof DOMException && error.name === "TimeoutError"
      ? "Backend quá thời gian chờ. Hãy thử lại; yêu cầu lặp lại không tạo draft trùng."
      : "Không gửi được tới backend local. Kiểm tra server và cài đặt extension.";
    return { ok: false, message };
  }
}

async function dictionaryLookup(text: string): Promise<ExtensionResponse> {
  const value = text.trim();
  if (!value || value.length > 200) return { ok: false, message: "Chọn tối đa 200 ký tự để tra." };
  const { apiBaseUrl, frontendBaseUrl } = await getSettings();
  const cacheKey = `dict:${value.normalize("NFKC").toLocaleLowerCase()}`;
  const cached = await chrome.storage.local.get([cacheKey]);
  if (cached[cacheKey]) return { ...(cached[cacheKey] as ExtensionResponse), message: "Đã tra từ bộ nhớ đệm cục bộ." };
  try {
    const local = await fetch(chrome.runtime.getURL("data/private-mimikara-ja-vi.json")).then(response => response.json()) as { entries: Array<{ term: string; reading: string | null; meaning_vi: string; source: string; source_ref: string }> };
    const exact = local.entries.filter(entry => entry.term === value).slice(0, 20);
    if (exact.length) {
      const result: ExtensionResponse = { ok: true, message: "Tìm thấy trong từ điển cá nhân ngoại tuyến.", detectedLanguage: "ja", entries: exact.map(entry => ({ id: entry.source_ref, expression: entry.term, reading: entry.reading, meaning_vi: entry.meaning_vi, source: `${entry.source} · #${entry.source_ref}` })) };
      await chrome.storage.local.set({ [cacheKey]: result });
      return result;
    }
  } catch { /* Development harness may not package the private lexicon. */ }
  try {
    const response = await fetch(`${apiBaseUrl}/dictionary/lookup?q=${encodeURIComponent(value)}`, { credentials: "omit", cache: "no-store", signal: AbortSignal.timeout(6000) });
    const body = await response.json() as { data?: { entries?: Array<{ id: string; expression: string; reading: string | null; meaning_vi: string | null; meaning_en?: string | null; meaning_ja?: string | null; english_ipa?: string | null; source: string }>; detected_language?: string | null }; error?: { message?: string } };
    if (!response.ok) return { ok: false, message: body.error?.message ?? `Từ điển trả HTTP ${response.status}.` };
    const result: ExtensionResponse = { ok: true, message: body.data?.entries?.length ? "Tìm thấy trong học liệu đã xác minh." : "Chưa có nguồn dịch cho mục này; hãy nhập nghĩa trước khi lưu.", entries: body.data?.entries ?? [], detectedLanguage: body.data?.detected_language, webUrl: `${frontendBaseUrl}/learning/my-words` };
    if (result.entries?.length) await chrome.storage.local.set({ [cacheKey]: result });
    return result;
  } catch {
    return { ok: false, message: "Không có mục trong từ điển ngoại tuyến và không kết nối được bộ tra cứu máy chủ." };
  }
}

async function sendWord(word: Record<string, unknown>): Promise<ExtensionResponse> {
  const { apiBaseUrl, dictionaryToken } = await getSettings();
  if (!dictionaryToken) return { ok: false, message: "Chưa có credential Từ của tôi trong Cài đặt extension." };
  try {
    const response = await fetch(`${apiBaseUrl}/my-words/extension`, {
      method: "POST", cache: "no-store", credentials: "omit",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${dictionaryToken}` },
      body: JSON.stringify(word), signal: AbortSignal.timeout(8000),
    });
    const body = await response.json() as { data?: { id?: string; created?: boolean }; error?: { message?: string } };
    if (!response.ok) return { ok: false, message: body.error?.message ?? `Lưu từ thất bại (HTTP ${response.status}).` };
    return { ok: true, message: body.data?.created ? "Đã lưu lên Web." : "Từ này đã được lưu trước đó." };
  } catch {
    const stored = await chrome.storage.local.get(["pendingWords"]);
    const queue = Array.isArray(stored.pendingWords) ? stored.pendingWords as Record<string, unknown>[] : [];
    if (queue.some(item => item.request_id === word.request_id)) return { ok: false, queued: true, message: "Mất kết nối; từ đã nằm trong hàng chờ trên thiết bị." };
    if (queue.length >= 100) return { ok: false, queued: false, message: "Hàng chờ ngoại tuyến đã đầy; từ này chưa được lưu. Hãy đồng bộ rồi thử lại." };
    queue.push(word);
    await chrome.storage.local.set({ pendingWords: queue });
    return { ok: false, queued: true, message: "Mất kết nối; đã giữ bản nháp trong extension. Chưa lưu lên Web." };
  }
}

async function retryPendingWords(): Promise<void> {
  if (retryingPendingWords) return;
  retryingPendingWords = true;
  try {
  const stored = await chrome.storage.local.get(["pendingWords"]);
  const queue = Array.isArray(stored.pendingWords) ? stored.pendingWords as Record<string, unknown>[] : [];
  if (!queue.length) return;
  const remaining: Record<string, unknown>[] = [];
  for (const word of queue) {
    const result = await sendWord(word);
    if (!result.ok) remaining.push(word);
  }
  await chrome.storage.local.set({ pendingWords: remaining });
  } finally {
    retryingPendingWords = false;
  }
}

chrome.runtime.onMessage.addListener((message: unknown, sender, sendResponse) => {
  if (sender.id !== chrome.runtime.id || !message || typeof message !== "object") return;
  const input = message as ExtensionMessage;
  if (!["PING", "IMPORT_CAPTURE", "DICT_LOOKUP", "SAVE_WORD"].includes(input.type)) return;
  const task = input.type === "PING"
    ? ping().then(async result => { if (result.ok) await retryPendingWords(); return result; })
    : input.type === "IMPORT_CAPTURE"
      ? input.capture ? importCapture(input.capture) : Promise.resolve({ ok: false, message: "Không có dữ liệu capture." } satisfies ExtensionResponse)
      : input.type === "DICT_LOOKUP"
        ? dictionaryLookup(input.text ?? "")
        : input.word ? sendWord(input.word) : Promise.resolve({ ok: false, message: "Thiếu nội dung từ." } satisfies ExtensionResponse);
  task.then(sendResponse).catch(() => sendResponse({ ok: false, message: "Lỗi nội bộ extension." }));
  return true;
});

if (chrome.runtime.onInstalled && chrome.contextMenus) {
  chrome.runtime.onInstalled.addListener(() => {
    chrome.contextMenus.create({ id: "jlpt-lookup-selection", title: "Tra từ với JLPT AI Review", contexts: ["selection"] });
    chrome.alarms.create("retry-pending-words", { delayInMinutes: 1, periodInMinutes: 15 });
  });
  chrome.contextMenus.onClicked.addListener((info, tab) => {
    if (info.menuItemId !== "jlpt-lookup-selection" || !tab?.id || !info.selectionText) return;
    void chrome.scripting.executeScript({ target: { tabId: tab.id }, files: ["content/dictionary-helper.js"] })
      .then(() => chrome.tabs.sendMessage(tab.id!, { type: "JLPT_LOOKUP_SELECTION", text: info.selectionText }))
      .catch(() => undefined);
  });
}

chrome.runtime.onStartup?.addListener(() => {
  chrome.alarms.create("retry-pending-words", { delayInMinutes: 1, periodInMinutes: 15 });
  void retryPendingWords();
});
chrome.alarms.onAlarm.addListener(alarm => {
  if (alarm.name === "retry-pending-words") void retryPendingWords();
});
