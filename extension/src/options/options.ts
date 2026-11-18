import { DEFAULT_SETTINGS, getSettings, normalizeApiBaseUrl, normalizeFrontendBaseUrl } from "../shared/settings.js";

const apiInput = document.querySelector<HTMLInputElement>("#api-url")!;
const webInput = document.querySelector<HTMLInputElement>("#web-url")!;
const tokenInput = document.querySelector<HTMLInputElement>("#extension-token")!;
const tokenState = document.querySelector<HTMLParagraphElement>("#token-state")!;
const dictionaryTokenInput = document.querySelector<HTMLInputElement>("#dictionary-token")!;
const dictionaryTokenState = document.querySelector<HTMLParagraphElement>("#dictionary-token-state")!;
const status = document.querySelector<HTMLParagraphElement>("#status")!;
const form = document.querySelector<HTMLFormElement>("form")!;
const clearButton = document.querySelector<HTMLButtonElement>("#clear-token")!;

async function load() {
  const settings = await getSettings();
  apiInput.value = settings.apiBaseUrl || DEFAULT_SETTINGS.apiBaseUrl;
  webInput.value = settings.frontendBaseUrl || DEFAULT_SETTINGS.frontendBaseUrl;
  tokenInput.value = "";
  tokenInput.placeholder = settings.token ? "Đã lưu token; để trống để giữ nguyên" : "Dán cùng token EXTENSION_IMPORT_TOKEN ở backend";
  tokenState.textContent = settings.token ? "Token đã được lưu cục bộ trong Chrome." : "Chưa có token local.";
  dictionaryTokenInput.value = "";
  dictionaryTokenInput.placeholder = settings.dictionaryToken ? "Đã lưu; để trống để giữ nguyên" : "Tạo credential trong Cài đặt đồng bộ Web";
  dictionaryTokenState.textContent = settings.dictionaryToken ? "Credential lưu từ đã được lưu trong extension storage." : "Chưa có credential lưu từ.";
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const apiBaseUrl = normalizeApiBaseUrl(apiInput.value);
  const frontendBaseUrl = normalizeFrontendBaseUrl(webInput.value);
  if (!apiBaseUrl || !frontendBaseUrl) {
    status.textContent = "URL phải dùng http/https và trỏ tới 127.0.0.1, localhost hoặc ::1.";
    status.dataset.tone = "error";
    return;
  }
  const saved = await getSettings();
  const token = tokenInput.value.trim() || saved.token;
  const dictionaryToken = dictionaryTokenInput.value.trim() || saved.dictionaryToken;
  if (token && token.length < 32) {
    status.textContent = "Token cần tối thiểu 32 ký tự ngẫu nhiên.";
    status.dataset.tone = "error";
    return;
  }
  if (dictionaryToken && dictionaryToken.length < 40) {
    status.textContent = "Credential lưu từ cần ít nhất 40 ký tự.";
    status.dataset.tone = "error";
    return;
  }
  await chrome.storage.local.set({ apiBaseUrl, frontendBaseUrl, token, dictionaryToken });
  tokenInput.value = "";
  await load();
  status.textContent = "Đã lưu cài đặt trên thiết bị này.";
  status.dataset.tone = "success";
});

clearButton.addEventListener("click", async () => {
  await chrome.storage.local.set({ token: "", dictionaryToken: "" });
  await load();
  status.textContent = "Đã xoá token đã lưu.";
  status.dataset.tone = "success";
});

void load();
