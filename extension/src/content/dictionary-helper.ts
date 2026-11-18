/* Injected only after per-site permission. Never reads extension credentials. */
(() => {
  const marker = "jlpt-dictionary-helper";
  if (document.getElementById(marker) || !document.body) return;
  const host = document.createElement("div");
  host.id = marker;
  host.style.cssText = "position:fixed;z-index:2147483647;top:0;left:0;pointer-events:none";
  const shadow = host.attachShadow({ mode: "closed" });
  const style = document.createElement("style");
  style.textContent = `*{box-sizing:border-box}button,input,textarea,select{font:inherit}button{cursor:pointer;border:1px solid #b7c8d0;border-radius:7px;background:#fff;color:#172a35;padding:6px 9px}button:hover{background:#eaf4f6}.icon{width:30px;height:30px;border-radius:50%;background:#217b83;color:#fff;border:0}.panel{width:min(330px,calc(100vw - 20px));max-height:70vh;overflow:auto;background:#fff;color:#172a35;border:1px solid #9db7be;border-radius:12px;box-shadow:0 8px 28px #0003;padding:12px;font:14px/1.5 system-ui,sans-serif;pointer-events:auto}.row{display:flex;gap:6px;flex-wrap:wrap;margin-top:8px}.field{display:block;margin-top:8px;font-size:12px}.field input,.field textarea,.field select{display:block;width:100%;border:1px solid #adbdc4;border-radius:6px;padding:5px;color:#172a35;background:white}.muted{color:#54656e;font-size:12px}.error{color:#a42524}`;
  shadow.append(style);
  document.body.append(host);
  let current = "";
  let requestId = "";
  let hoverTimer = 0;
  let closeTimer = 0;
  let enabledNodes: Array<{ node: HTMLElement; value: string; priority: string }> = [];

  function clear() { window.clearTimeout(hoverTimer); window.clearTimeout(closeTimer); shadow.querySelectorAll("button,.panel").forEach(node => node.remove()); }
  function place(node: HTMLElement, rect: DOMRect) {
    node.style.position = "fixed";
    const width = node.classList.contains("panel") ? Math.min(330, window.innerWidth - 20) : 30;
    const height = node.classList.contains("panel") ? Math.min(400, window.innerHeight * 0.7) : 30;
    node.style.left = `${Math.max(8, Math.min(rect.right + 5, window.innerWidth - width - 8))}px`;
    const below = rect.bottom + 5;
    const above = rect.top - height - 5;
    node.style.top = `${Math.max(8, Math.min(below + height <= window.innerHeight ? below : above, window.innerHeight - height - 8))}px`;
    shadow.append(node);
  }
  function field(panel: HTMLElement, labelText: string, value: string) {
    const label = document.createElement("label"); label.className = "field"; label.textContent = labelText;
    const input = document.createElement("input"); input.value = value; label.append(input); panel.append(label);
    return input;
  }
  function text(panel: HTMLElement, value: string, className = "") {
    const p = document.createElement("p"); p.className = className; p.textContent = value; panel.append(p); return p;
  }
  function button(parent: HTMLElement, label: string, action: () => void) {
    const item = document.createElement("button"); item.type = "button"; item.textContent = label; item.addEventListener("click", action); parent.append(item); return item;
  }
  function speak(value: string, language: string, status: HTMLElement) {
    if (!("speechSynthesis" in window)) { status.textContent = "Trình duyệt không hỗ trợ giọng đọc."; return; }
    const voices = speechSynthesis.getVoices();
    const voice = voices.find(item => item.lang.toLowerCase().startsWith(language));
    if (!voice) { status.textContent = "Không có giọng đọc phù hợp trên thiết bị."; return; }
    speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(value); utterance.voice = voice; utterance.lang = voice.lang;
    utterance.onerror = () => { status.textContent = "Không phát được âm thanh."; };
    speechSynthesis.speak(utterance);
  }
  async function openLookup(rect: DOMRect) {
    clear();
    const panel = document.createElement("div"); panel.className = "panel";
    panel.setAttribute("role", "dialog"); panel.setAttribute("aria-label", "Tra từ đã chọn"); panel.tabIndex = -1;
    panel.addEventListener("pointerenter", () => window.clearTimeout(closeTimer));
    panel.addEventListener("pointerleave", () => { closeTimer = window.setTimeout(clear, 180); });
    text(panel, current, "");
    const status = text(panel, "Đang tra từ nguồn đã xác minh…", "muted");
    place(panel, rect);
    const result = await chrome.runtime.sendMessage<{
      ok: boolean; message: string; detectedLanguage?: string | null; webUrl?: string;
      entries?: Array<{ expression: string; reading: string | null; meaning_vi: string | null; meaning_en?: string | null; meaning_ja?: string | null; english_ipa?: string | null; source: string }>;
    }>({ type: "DICT_LOOKUP", text: current });
    status.textContent = result.message;
    const entries = result.entries ?? [];
    if (entries.length > 1) text(panel, `${entries.length} mục từ trùng dạng; hãy kiểm tra nghĩa/cách đọc.`, "muted");
    const languageLabel = document.createElement("label"); languageLabel.className = "field"; languageLabel.textContent = "Ngôn ngữ nguồn";
    const language = document.createElement("select");
    for (const [value, label] of [["ja", "日本語"], ["en", "English"], ["vi", "Tiếng Việt"]]) {
      const option = document.createElement("option"); option.value = value; option.textContent = label; language.append(option);
    }
    language.value = result.detectedLanguage === "ja" || result.detectedLanguage === "en" || result.detectedLanguage === "vi" ? result.detectedLanguage : "ja";
    languageLabel.append(language); panel.append(languageLabel);
    if (!result.detectedLanguage) text(panel, "Chưa nhận diện chắc chắn; hãy chọn ngôn ngữ nguồn.", "muted");
    const readings = [...new Set(entries.map(item => item.reading).filter(Boolean))];
    const reading = field(panel, "Hiragana (chỉ nguồn xác minh; có thể sửa)", readings.length === 1 ? readings[0] || "" : "");
    if (readings.length > 1) text(panel, `Có nhiều cách đọc trong nguồn: ${readings.join("、")}. Chọn cách phù hợp ngữ cảnh.`, "muted");
    const ipaValues = [...new Set(entries.map(item => item.english_ipa).filter(Boolean))];
    const ipa = field(panel, "IPA tiếng Anh (chỉ khi nguồn cung cấp)", ipaValues.length === 1 ? ipaValues[0] || "" : "");
    const viValues = [...new Set(entries.map(item => item.meaning_vi).filter(Boolean))];
    const enValues = [...new Set(entries.map(item => item.meaning_en).filter(Boolean))];
    const jaValues = [...new Set(entries.map(item => item.meaning_ja).filter(Boolean))];
    const vi = field(panel, "Nghĩa tiếng Việt", viValues.join("; "));
    const en = field(panel, "English meaning", enValues.join("; "));
    const ja = field(panel, "日本語の意味", jaValues.join("; "));
    if (!enValues.length || !jaValues.length || !ipaValues.length) {
      text(panel, `Nguồn tra hiện có: ${[...new Set(entries.map(item => item.source))].filter(Boolean).join("; ") || "không có"}. Trường dịch/IPA trống nghĩa là nguồn chưa cung cấp; không tự tạo kết quả.`, "muted");
    } else if (entries.length) {
      text(panel, `Nguồn: ${[...new Set(entries.map(item => item.source))].join("; ")}`, "muted");
    }
    const row = document.createElement("div"); row.className = "row"; panel.append(row);
    button(row, "🔊 Nghe", () => speak(current, language.value, status));
    button(row, "Dừng", () => { if ("speechSynthesis" in window) speechSynthesis.cancel(); });
    const saveButton = button(row, "Lưu từ", async () => {
      if (!requestId) requestId = crypto.randomUUID();
      status.textContent = "Đang lưu…";
      const source = new URL(location.href); source.search = ""; source.hash = "";
      const saved = await chrome.runtime.sendMessage<{ ok: boolean; queued?: boolean; message: string }>({
        type: "SAVE_WORD",
        word: {
          request_id: requestId, original_text: current, language: language.value,
          meanings: { vi: vi.value.trim() ? [vi.value.trim()] : [], en: en.value.trim() ? [en.value.trim()] : [], ja: ja.value.trim() ? [ja.value.trim()] : [] },
          japanese_reading: reading.value.trim() || null, english_ipa: ipa.value.trim() || null,
          source_url: source.toString(), source_title: document.title.slice(0, 300),
          context: null, tags: [],
        },
      });
      status.textContent = saved.message;
      status.className = saved.ok || saved.queued ? "muted" : "error";
      if (saved.ok) {
        saveButton.disabled = true;
        saveButton.textContent = "Đã đồng bộ";
      }
    });
    button(row, "Đóng", clear);
    panel.addEventListener("keydown", event => { if (event.key === "Escape") clear(); });
  }
  function selection() {
    const sel = window.getSelection();
    const value = sel?.toString().trim() ?? "";
    const active = document.activeElement;
    if (!sel || sel.rangeCount === 0 || !value || value.length > 200 || shadow.activeElement || active instanceof HTMLInputElement && (active.type === "password" || active.type === "text") || active instanceof HTMLTextAreaElement || active instanceof HTMLElement && active.isContentEditable) return;
    const rect = sel.getRangeAt(0).getBoundingClientRect();
    if (rect.width <= 0) return;
    current = value; requestId = ""; clear();
    const icon = document.createElement("button"); icon.className = "icon"; icon.type = "button"; icon.textContent = "訳"; icon.title = "Di chuột để tra từ"; icon.setAttribute("aria-label", "Tra từ đã chọn"); icon.style.pointerEvents = "auto";
    icon.addEventListener("mousedown", event => event.preventDefault());
    icon.addEventListener("pointerenter", () => { window.clearTimeout(closeTimer); hoverTimer = window.setTimeout(() => { void openLookup(rect); }, 200); });
    icon.addEventListener("pointerleave", () => { window.clearTimeout(hoverTimer); closeTimer = window.setTimeout(() => { if (!shadow.querySelector(".panel:hover")) clear(); }, 220); });
    icon.addEventListener("focus", () => { window.clearTimeout(hoverTimer); hoverTimer = window.setTimeout(() => { void openLookup(rect); }, 200); });
    icon.addEventListener("click", () => { void openLookup(rect); });
    place(icon, rect);
  }
  document.addEventListener("mouseup", () => setTimeout(selection, 0));
  document.addEventListener("keyup", event => { if (event.key === "Shift" || event.key.startsWith("Arrow")) setTimeout(selection, 0); });
  function restoreSelection() {
    for (const { node, value, priority } of enabledNodes) {
      if (value) node.style.setProperty("user-select", value, priority);
      else node.style.removeProperty("user-select");
      node.removeAttribute("data-jlpt-select");
    }
    enabledNodes = [];
  }
  async function applySelectionPreference() {
    restoreSelection();
    const stored = await chrome.storage.local.get(["enabledSelectionHosts"]);
    const hosts = Array.isArray(stored.enabledSelectionHosts) ? stored.enabledSelectionHosts as string[] : [];
    if (!hosts.includes(location.hostname)) return;
    for (const node of document.body.querySelectorAll<HTMLElement>("*")) {
      if (getComputedStyle(node).userSelect === "none") {
        enabledNodes.push({ node, value: node.style.getPropertyValue("user-select"), priority: node.style.getPropertyPriority("user-select") });
        node.style.setProperty("user-select", "text", "important");
        node.dataset.jlptSelect = "1";
      }
    }
  }
  chrome.runtime.onMessage.addListener((message: unknown) => {
    if (!message || typeof message !== "object") return;
    const type = (message as { type?: string }).type;
    if (type === "JLPT_SELECTION_PREFERENCE") void applySelectionPreference();
    if (type === "JLPT_DICTIONARY_DISABLE") { restoreSelection(); clear(); host.remove(); }
    if (type === "JLPT_LOOKUP_SELECTION") {
      const value = (message as { text?: string }).text?.trim() ?? "";
      if (value && value.length <= 200) {
        current = value; requestId = "";
        const selected = window.getSelection();
        const rect = selected?.rangeCount ? selected.getRangeAt(0).getBoundingClientRect() : new DOMRect(16, 16, 1, 1);
        void openLookup(rect);
      }
    }
  });
  void applySelectionPreference();
})();
