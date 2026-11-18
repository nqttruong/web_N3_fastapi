import { extractDethitiengnhat } from "../content/extract.js";
import type { BrowserCapture, ExtensionMessage, ExtensionResponse } from "../shared/contracts.js";

const $ = <T extends HTMLElement>(selector: string): T => {
  const el = document.querySelector<T>(selector);
  if (!el) throw new Error(`Missing popup element: ${selector}`);
  return el;
};

const statusEl = $<HTMLParagraphElement>("#status");
const summaryEl = $<HTMLElement>("#summary");
const warningsEl = $<HTMLElement>("#warnings");
const extractButton = $<HTMLButtonElement>("#extract");
const sendButton = $<HTMLButtonElement>("#send");
const previewButton = $<HTMLButtonElement>("#show-data");
const dataEl = $<HTMLPreElement>("#data");
const settingsButton = $<HTMLButtonElement>("#settings");
const dictionaryEnable = $<HTMLButtonElement>("#dictionary-enable");
const dictionaryDisable = $<HTMLButtonElement>("#dictionary-disable");
const selectionToggle = $<HTMLButtonElement>("#selection-toggle");
const dictionaryStatus = $<HTMLParagraphElement>("#dictionary-status");
let activeTabId: number | null = null;
let activeUrl: URL | null = null;
let capture: BrowserCapture | null = null;
let supportedPage = false;
let sent = false;

function setStatus(text: string, tone: "info" | "success" | "error" = "info") {
  statusEl.textContent = text;
  statusEl.dataset.tone = tone;
}

function isSupportedPage(raw: string | undefined): boolean {
  if (!raw) return false;
  try {
    const url = new URL(raw);
    return ["dethitiengnhat.com", "www.dethitiengnhat.com"].includes(url.hostname) &&
      /^\/jlpt\/N3\/\d+\/(?:1|3)\/?$/.test(url.pathname);
  } catch {
    return false;
  }
}

function renderCapture(value: BrowserCapture) {
  capture = value;
  const answered = value.questions.filter((q) => q.selected_answer_index !== null).length;
  const keyed = value.questions.filter((q) => q.source_correct_answer_index !== null).length;
  const missing = value.questions.length - keyed;
  summaryEl.hidden = false;
  summaryEl.replaceChildren();
  const rows: [string, string][] = [
    ["Đề", value.exam_title || "Không đọc được tên đề"],
    ["Phần", value.category === "vocabulary" ? "Từ vựng" : "Ngữ pháp / Đọc hiểu"],
    ["Nguồn", value.source_url],
    ["Kết quả", value.capture_state === "graded" ? "Đã chấm (theo dấu trên trang)" : "Chưa thấy dấu đã chấm"],
    ["Số câu nhận diện", String(value.questions.length)],
    ["Đã trả lời", String(answered)],
    ["Có đáp án trang nguồn", String(keyed)],
    ["Chưa có đáp án nguồn", String(missing)],
  ];
  for (const [label, text] of rows) {
    const row = document.createElement("div");
    row.className = "summary-row";
    const strong = document.createElement("strong");
    strong.textContent = label;
    const valueEl = document.createElement("span");
    valueEl.textContent = text;
    row.append(strong, valueEl);
    summaryEl.append(row);
  }
  const warnings: string[] = [];
  if (value.capture_state !== "graded") warnings.push("Trang chưa có dấu chấm điểm. Các đáp án và lựa chọn sẽ cần kiểm tra trong bản xem trước.");
  if (missing) warnings.push(`${missing} câu chưa đọc được đáp án chuẩn; không tự suy đoán.`);
  if (answered < value.questions.length) warnings.push(`${value.questions.length - answered} câu chưa thấy lựa chọn đã chọn.`);
  const conflicts = value.questions.filter((q) => q.source_key_conflict).length;
  if (conflicts) warnings.push(`${conflicts} câu có đáp án dấu chấm khác key trang; sẽ cần xác minh.`);
  warningsEl.replaceChildren(...warnings.map((text) => {
    const item = document.createElement("p");
    item.textContent = text;
    return item;
  }));
  dataEl.textContent = JSON.stringify(value, null, 2);
  extractButton.disabled = false;
  previewButton.disabled = false;
  sendButton.disabled = sent;
  setStatus("Đã trích xuất từ tab đang mở. Hãy kiểm tra cảnh báo trước khi chuyển.", "success");
}

async function sendMessage(message: ExtensionMessage): Promise<ExtensionResponse> {
  return chrome.runtime.sendMessage<ExtensionResponse>(message);
}

async function initialize() {
  const [tab] = await chrome.tabs.query({ active: true, lastFocusedWindow: true });
  activeTabId = tab?.id ?? null;
  try { activeUrl = tab?.url ? new URL(tab.url) : null; } catch { activeUrl = null; }
  const eligible = activeUrl && ["http:", "https:"].includes(activeUrl.protocol) && activeTabId !== null;
  dictionaryEnable.disabled = !eligible;
  dictionaryDisable.disabled = !eligible;
  selectionToggle.disabled = !eligible;
  if (!eligible) dictionaryStatus.textContent = "Trang này không cho phép extension thao tác (ví dụ trang nội bộ trình duyệt).";
  if (eligible) {
    const stored = await chrome.storage.local.get(["enabledSelectionHosts"]);
    const hosts = Array.isArray(stored.enabledSelectionHosts) ? stored.enabledSelectionHosts as string[] : [];
    selectionToggle.textContent = `Enable Text Selection: ${hosts.includes(activeUrl!.hostname) ? "bật" : "tắt"}`;
  }
  supportedPage = isSupportedPage(tab?.url);
  if (!supportedPage || activeTabId === null) {
    extractButton.disabled = true;
    setStatus("Chưa ở trang đề N3 được hỗ trợ. Mở đề Từ vựng hoặc Ngữ pháp/Đọc hiểu rồi thử lại.", "error");
  }
  const backend = await sendMessage({ type: "PING" });
  if (!backend.ok) setStatus(backend.message, "error");
}

extractButton.addEventListener("click", async () => {
  if (!supportedPage || activeTabId === null) return;
  extractButton.disabled = true;
  sendButton.disabled = true;
  setStatus("Đang đọc câu hỏi từ tab hiện tại…");
  try {
    const [injected] = await chrome.scripting.executeScript({
      target: { tabId: activeTabId },
      func: extractDethitiengnhat,
    });
    const result = injected?.result;
    if (!result?.ok) {
      setStatus(result?.error ?? "Không đọc được dữ liệu trang.", "error");
      extractButton.disabled = false;
      return;
    }
    renderCapture(result.capture);
  } catch {
    setStatus("Chrome không cho phép đọc tab này. Hãy mở trực tiếp trang đề rồi bấm lại extension.", "error");
    extractButton.disabled = false;
  }
});

sendButton.addEventListener("click", async () => {
  if (!capture || sent) return;
  sendButton.disabled = true;
  extractButton.disabled = true;
  setStatus("Đang gửi capture tới backend local…");
  const result = await sendMessage({ type: "IMPORT_CAPTURE", capture });
  if (result.ok) {
    sent = true;
    setStatus(result.message, "success");
  } else {
    sendButton.disabled = false;
    extractButton.disabled = false;
    setStatus(result.message, "error");
  }
});

previewButton.addEventListener("click", () => {
  dataEl.hidden = !dataEl.hidden;
  previewButton.textContent = dataEl.hidden ? "Xem dữ liệu" : "Ẩn dữ liệu";
});

settingsButton.addEventListener("click", () => void chrome.runtime.openOptionsPage());

function site() {
  if (!activeUrl || activeTabId === null || !["http:", "https:"].includes(activeUrl.protocol)) return null;
  return { pattern: `${activeUrl.protocol}//${activeUrl.hostname}/*`, id: `jlpt-dict-${activeUrl.protocol.slice(0, -1)}-${activeUrl.hostname.replace(/[^a-z0-9]/gi, "-")}`, tabId: activeTabId };
}

dictionaryEnable.addEventListener("click", async () => {
  const target = site(); if (!target) return;
  try {
    if (!await chrome.permissions.request({ origins: [target.pattern] })) { dictionaryStatus.textContent = "Chưa cấp quyền website này."; return; }
    try { await chrome.scripting.registerContentScripts([{ id: target.id, matches: [target.pattern], js: ["content/dictionary-helper.js"], runAt: "document_idle" }]); } catch { /* Already registered on this site. */ }
    await chrome.scripting.executeScript({ target: { tabId: target.tabId }, files: ["content/dictionary-helper.js"] });
    dictionaryStatus.textContent = "Đã bật cho website này. Bôi đen một từ rồi bấm biểu tượng 訳.";
  } catch { dictionaryStatus.textContent = "Không thể bật trên trang này; trình duyệt có thể đang hạn chế extension."; }
});

dictionaryDisable.addEventListener("click", async () => {
  const target = site(); if (!target) return;
  try {
    await chrome.scripting.unregisterContentScripts({ ids: [target.id] });
  } catch { /* Not registered. */ }
  try { await chrome.tabs.sendMessage(target.tabId, { type: "JLPT_DICTIONARY_DISABLE" }); } catch { /* No injected helper on this tab. */ }
  await chrome.permissions.remove({ origins: [target.pattern] });
  dictionaryStatus.textContent = "Đã tắt tra từ cho website này.";
});

selectionToggle.addEventListener("click", async () => {
  const target = site(); if (!target || !activeUrl) return;
  const stored = await chrome.storage.local.get(["enabledSelectionHosts"]);
  const hosts = new Set(Array.isArray(stored.enabledSelectionHosts) ? stored.enabledSelectionHosts as string[] : []);
  if (hosts.has(activeUrl.hostname)) hosts.delete(activeUrl.hostname); else hosts.add(activeUrl.hostname);
  await chrome.storage.local.set({ enabledSelectionHosts: [...hosts] });
  selectionToggle.textContent = `Enable Text Selection: ${hosts.has(activeUrl.hostname) ? "bật" : "tắt"}`;
  try { await chrome.tabs.sendMessage(target.tabId, { type: "JLPT_SELECTION_PREFERENCE" }); } catch { dictionaryStatus.textContent = "Bật tra từ trước để áp dụng ngay cho trang hiện tại."; }
});
void initialize().catch(() => setStatus("Không đọc được trạng thái extension.", "error"));
