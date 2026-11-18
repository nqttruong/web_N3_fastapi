import { beforeEach, describe, expect, it, vi } from "vitest";

type Listener = (message: unknown) => void;

describe("per-site dictionary helper", () => {
  let listener: Listener | undefined;
  let sendMessage: ReturnType<typeof vi.fn>;
  let getStorage: ReturnType<typeof vi.fn>;

  beforeEach(async () => {
    vi.resetModules();
    Object.defineProperty(Range.prototype, "getBoundingClientRect", {
      configurable: true,
      value: () => new DOMRect(40, 60, 45, 18),
    });
    document.body.innerHTML = "<p id='source'>学校</p><p id='locked' style='user-select:none'>locked</p>";
    listener = undefined;
    sendMessage = vi.fn().mockResolvedValue({ ok: true, message: "Tìm thấy", detectedLanguage: "ja", entries: [{ expression: "学校", reading: "がっこう", meaning_vi: "trường học" }], webUrl: "http://127.0.0.1:3000/learning/my-words" });
    getStorage = vi.fn().mockResolvedValue({ enabledSelectionHosts: [location.hostname] });
    vi.stubGlobal("chrome", { runtime: { onMessage: { addListener: (callback: Listener) => { listener = callback; } }, sendMessage }, storage: { local: { get: getStorage } } });
    const original = HTMLElement.prototype.attachShadow;
    vi.spyOn(HTMLElement.prototype, "attachShadow").mockImplementation(function () { return original.call(this, { mode: "open" }); });
    await import("../src/content/dictionary-helper.js");
    await Promise.resolve();
  });

  it("enables ordinary selection only on the opted-in site and restores styles", async () => {
    const locked = document.querySelector<HTMLElement>("#locked")!;
    await new Promise(resolve => setTimeout(resolve, 0));
    expect(locked.style.getPropertyValue("user-select")).toBe("text");
    expect(locked.style.getPropertyPriority("user-select")).toBe("important");
    expect(getStorage).toHaveBeenCalledWith(["enabledSelectionHosts"]);
    listener?.({ type: "JLPT_DICTIONARY_DISABLE" });
    expect(locked.style.getPropertyValue("user-select")).toBe("none");
    expect(document.getElementById("jlpt-dictionary-helper")).toBeNull();
  });

  it("looks up only the requested selection and lets the user edit language and meaning before saving", async () => {
    listener?.({ type: "JLPT_LOOKUP_SELECTION", text: "学校" });
    await new Promise(resolve => setTimeout(resolve, 0));
    expect(sendMessage).toHaveBeenCalledWith({ type: "DICT_LOOKUP", text: "学校" });
    const shadow = document.getElementById("jlpt-dictionary-helper")!.shadowRoot!;
    const fields = shadow.querySelectorAll<HTMLInputElement>("input");
    expect(fields[0].value).toBe("がっこう");
    expect(fields[2].value).toBe("trường học");
    fields[2].value = "trường học; học đường";
    const language = shadow.querySelector<HTMLSelectElement>("select")!;
    language.value = "vi";
    sendMessage.mockResolvedValueOnce({ ok: true, message: "Đã lưu lên Web." });
    const save = Array.from(shadow.querySelectorAll("button")).find(button => button.textContent === "Lưu từ")!;
    save.click();
    await new Promise(resolve => setTimeout(resolve, 0));
    expect(sendMessage).toHaveBeenCalledWith(expect.objectContaining({
      type: "SAVE_WORD",
      word: expect.objectContaining({ original_text: "学校", language: "vi", japanese_reading: "がっこう", meanings: expect.objectContaining({ vi: ["trường học; học đường"] }) }),
    }));
  });

  it("shows the icon after selection and opens lookup on hover without saving", async () => {
    const source = document.querySelector<HTMLElement>("#source")!;
    const range = document.createRange();
    range.selectNodeContents(source);
    const selection = window.getSelection()!;
    selection.removeAllRanges();
    selection.addRange(range);

    document.dispatchEvent(new MouseEvent("mouseup", { bubbles: true }));
    await new Promise(resolve => setTimeout(resolve, 5));
    const shadow = document.getElementById("jlpt-dictionary-helper")!.shadowRoot!;
    const icon = shadow.querySelector<HTMLButtonElement>("button.icon")!;
    expect(icon).toBeTruthy();
    expect(icon.getAttribute("aria-label")).toContain("Tra từ");

    icon.dispatchEvent(new Event("pointerenter"));
    await new Promise(resolve => setTimeout(resolve, 230));
    const panel = shadow.querySelector<HTMLElement>(".panel")!;
    expect(panel).toBeTruthy();
    expect(sendMessage).toHaveBeenCalledWith({ type: "DICT_LOOKUP", text: "学校" });
    expect(sendMessage).not.toHaveBeenCalledWith(expect.objectContaining({ type: "SAVE_WORD" }));
  });

  it("keeps the popup open over its content and closes after leaving it", async () => {
    listener?.({ type: "JLPT_LOOKUP_SELECTION", text: "学校" });
    await new Promise(resolve => setTimeout(resolve, 0));
    const shadow = document.getElementById("jlpt-dictionary-helper")!.shadowRoot!;
    const panel = shadow.querySelector<HTMLElement>(".panel")!;
    panel.dispatchEvent(new Event("pointerenter"));
    await new Promise(resolve => setTimeout(resolve, 240));
    expect(shadow.querySelector(".panel")).toBe(panel);
    panel.dispatchEvent(new Event("pointerleave"));
    await new Promise(resolve => setTimeout(resolve, 240));
    expect(shadow.querySelector(".panel")).toBeNull();
  });

  it("renders only meanings and IPA supplied by a provider", async () => {
    sendMessage.mockResolvedValueOnce({
      ok: true,
      message: "Verified dictionary result",
      detectedLanguage: "en",
      entries: [{ expression: "school", reading: null, meaning_vi: "trường học", meaning_en: "an institution for education", meaning_ja: "学校", english_ipa: "/skuːl/", source: "Approved dictionary" }],
    });
    listener?.({ type: "JLPT_LOOKUP_SELECTION", text: "school" });
    await new Promise(resolve => setTimeout(resolve, 0));
    const shadow = document.getElementById("jlpt-dictionary-helper")!.shadowRoot!;
    const values = Array.from(shadow.querySelectorAll<HTMLInputElement>("input")).map(input => input.value);
    expect(values).toEqual(["", "/skuːl/", "trường học", "an institution for education", "学校"]);
    expect(shadow.textContent).toContain("Approved dictionary");
  });

  it("uses a matching browser voice and reports when that voice is unavailable", async () => {
    class TestUtterance {
      voice: SpeechSynthesisVoice | null = null;
      lang = "";
      onerror: (() => void) | null = null;
      constructor(public text: string) {}
    }
    const speak = vi.fn();
    const cancel = vi.fn();
    vi.stubGlobal("SpeechSynthesisUtterance", TestUtterance);
    vi.stubGlobal("speechSynthesis", { getVoices: () => [{ lang: "ja-JP" }], speak, cancel });
    listener?.({ type: "JLPT_LOOKUP_SELECTION", text: "学校" });
    await new Promise(resolve => setTimeout(resolve, 0));
    const shadow = document.getElementById("jlpt-dictionary-helper")!.shadowRoot!;
    const speakButton = Array.from(shadow.querySelectorAll("button")).find(button => button.textContent?.includes("Nghe"))!;
    speakButton.click();
    expect(speak).toHaveBeenCalledWith(expect.objectContaining({ text: "学校", lang: "ja-JP" }));
    expect(cancel).toHaveBeenCalledOnce();

    const language = shadow.querySelector("select")!;
    (language as HTMLSelectElement).value = "en";
    speakButton.click();
    expect(shadow.textContent).toContain("Không có giọng đọc phù hợp");
    expect(speak).toHaveBeenCalledOnce();
  });
});
