import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { beforeEach, describe, expect, it, vi } from "vitest";

type MessageListener = (
  message: unknown,
  sender: { id?: string },
  sendResponse: (response: unknown) => void,
) => boolean | void;

const capture = {
  schema_version: "1.0",
  capture_id: "f0d8f90e-67cb-48cc-8a55-77e5ea8d4bad",
  source: "dethitiengnhat",
  source_url: "https://dethitiengnhat.com/jlpt/N3/32/3",
  level: "N3",
  exam_title: "N3",
  category: "grammar",
  capture_state: "graded",
  captured_at: "2026-11-12T00:00:00Z",
  questions: [{
    number: 1,
    section_heading: "文法",
    question_text: "雨が降っています。",
    options: ["ので", "のに", "ながら", "ばかりか"],
    selected_answer_index: 0,
    source_correct_answer_index: 1,
    answer_source: "page_result",
    passage: null,
    points: 1,
  }],
};

describe("extension service worker handoff", () => {
  let listener: MessageListener | undefined;
  let fetchMock: ReturnType<typeof vi.fn>;
  let createTab: ReturnType<typeof vi.fn>;
  let installedListener: (() => void) | undefined;
  let alarmListener: ((alarm: { name: string }) => void) | undefined;
  let startupListener: (() => void) | undefined;
  let storageState: Record<string, unknown>;

  beforeEach(async () => {
    vi.resetModules();
    listener = undefined;
    installedListener = undefined;
    alarmListener = undefined;
    startupListener = undefined;
    storageState = {
      apiBaseUrl: "http://127.0.0.1:8000/api/v1",
      frontendBaseUrl: "http://127.0.0.1:3000",
      token: "local-extension-test-token-0123456789abcdef",
      dictionaryToken: "dictionary-only-test-token-0123456789abcdef-0123456789abcdef",
    };
    fetchMock = vi.fn();
    createTab = vi.fn().mockResolvedValue({ id: 2 });
    vi.stubGlobal("fetch", fetchMock);
    vi.stubGlobal("chrome", {
      runtime: {
        id: "local-extension-id",
        onMessage: { addListener: (callback: MessageListener) => { listener = callback; } },
        onInstalled: { addListener: (callback: () => void) => { installedListener = callback; } },
        onStartup: { addListener: (callback: () => void) => { startupListener = callback; } },
      },
      storage: {
        local: {
          get: vi.fn(async (keys: string[]) => Object.fromEntries(keys.map(key => [key, storageState[key]]))),
          set: vi.fn(async (values: Record<string, unknown>) => { Object.assign(storageState, values); }),
        },
      },
      tabs: { create: createTab },
      alarms: {
        create: vi.fn(),
        onAlarm: { addListener: (callback: (alarm: { name: string }) => void) => { alarmListener = callback; } },
      },
      contextMenus: {
        create: vi.fn(),
        onClicked: { addListener: vi.fn() },
      },
    });
    await import("../src/background/service-worker.js");
  });

  async function send(message: unknown): Promise<Record<string, unknown>> {
    if (!listener) throw new Error("service worker message listener was not registered");
    return new Promise((resolveResponse, reject) => {
      const keepAlive = listener!(message, { id: "local-extension-id" }, (response) => {
        resolveResponse(response as Record<string, unknown>);
      });
      if (keepAlive !== true) reject(new Error("message channel was not kept open"));
    });
  }

  it("reports backend offline without claiming import success", async () => {
    fetchMock.mockRejectedValue(new TypeError("offline"));
    const response = await send({ type: "PING" });
    expect(response).toMatchObject({ ok: false, message: expect.stringContaining("Không kết nối được") });
    expect(createTab).not.toHaveBeenCalled();
  });

  it("posts once with omitted credentials and opens the existing import preview", async () => {
    const draftId = "29a1eaeb-7522-4de4-8e2f-03df53035281";
    fetchMock.mockResolvedValue(new Response(JSON.stringify({ data: { id: draftId } }), { status: 201 }));
    const response = await send({ type: "IMPORT_CAPTURE", capture });
    expect(response).toMatchObject({ ok: true, draftId, reused: false });
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(fetchMock).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/api/v1/imports/browser-capture",
      expect.objectContaining({
        method: "POST",
        credentials: "omit",
        headers: expect.objectContaining({ Authorization: expect.stringMatching(/^Bearer /) }),
        body: JSON.stringify(capture),
      }),
    );
    expect(createTab).toHaveBeenCalledWith({
      url: `http://127.0.0.1:3000/imports/${draftId}`,
      active: true,
    });
  });

  it("reopens a retry draft and reports timeout without faking success", async () => {
    const draftId = "29a1eaeb-7522-4de4-8e2f-03df53035281";
    fetchMock.mockResolvedValue(new Response(JSON.stringify({ data: { id: draftId } }), { status: 200 }));
    const duplicate = await send({ type: "IMPORT_CAPTURE", capture });
    expect(duplicate).toMatchObject({ ok: true, draftId, reused: true });
    expect(createTab).toHaveBeenCalledTimes(1);

    fetchMock.mockRejectedValue(new DOMException("timeout", "TimeoutError"));
    const timeout = await send({ type: "IMPORT_CAPTURE", capture });
    expect(timeout).toMatchObject({ ok: false, message: expect.stringContaining("quá thời gian chờ") });
  });

  it("keeps manifest permissions narrow and excludes credential access", () => {
    const manifest = JSON.parse(readFileSync(resolve(process.cwd(), "manifest.json"), "utf8")) as {
      permissions: string[];
      host_permissions: string[];
    };
    expect(manifest.permissions).toEqual(["activeTab", "scripting", "storage", "contextMenus", "alarms"]);
    expect(manifest.host_permissions).toEqual([
      "http://127.0.0.1/*",
      "http://localhost/*",
      "https://127.0.0.1/*",
      "https://localhost/*",
    ]);
    expect(manifest.permissions).not.toContain("cookies");
    expect(manifest.host_permissions).not.toContain("<all_urls>");
    expect(manifest.optional_host_permissions).toEqual(["http://*/*", "https://*/*"]);
  });

  it("schedules durable offline word retries without needing a Web tab", () => {
    if (!installedListener) throw new Error("install listener was not registered");
    installedListener();
    expect(chrome.alarms.create).toHaveBeenCalledWith("retry-pending-words", { delayInMinutes: 1, periodInMinutes: 15 });
    expect(alarmListener).toBeTypeOf("function");
    expect(startupListener).toBeTypeOf("function");
  });

  it("looks up only selected text and uses a separate save-scoped credential", async () => {
    fetchMock.mockResolvedValueOnce(new Response(JSON.stringify({ data: { detected_language: "ja", entries: [{ id: "one", expression: "学校", reading: "がっこう", meaning_vi: "trường học", source: "PDF" }] } }), { status: 200 }));
    const result = await send({ type: "DICT_LOOKUP", text: "学校" });
    expect(result).toMatchObject({ ok: true, detectedLanguage: "ja" });
    expect(fetchMock.mock.calls[0][0]).toContain("/dictionary/lookup?q=");
    fetchMock.mockResolvedValueOnce(new Response(JSON.stringify({ data: { id: "word-id", created: true } }), { status: 201 }));
    const word = { request_id: "a-uuid", original_text: "学校", language: "ja", meanings: { vi: ["trường học"] } };
    const saved = await send({ type: "SAVE_WORD", word });
    expect(saved).toMatchObject({ ok: true });
    const options = fetchMock.mock.calls[1][1] as RequestInit;
    expect((options.headers as Record<string, string>).Authorization).toContain("dictionary-only-test-token");
    expect((options.headers as Record<string, string>).Authorization).not.toContain("local-extension-test-token");
  });

  it("looks up an exact local dictionary match offline without opening a Web tab", async () => {
    (chrome.runtime as unknown as { getURL: ReturnType<typeof vi.fn> }).getURL = vi.fn(() => "extension://id/data/private-mimikara-ja-vi.json");
    fetchMock.mockResolvedValueOnce(new Response(JSON.stringify({ entries: [
      { term: "学校", reading: "がっこう", meaning_vi: "trường học", source: "Personal dictionary", source_ref: "1" },
    ] }), { status: 200 }));

    const result = await send({ type: "DICT_LOOKUP", text: "学校" });

    expect(result).toMatchObject({ ok: true, detectedLanguage: "ja", entries: [{ reading: "がっこう", meaning_vi: "trường học" }] });
    expect(fetchMock).toHaveBeenCalledTimes(1);
    const cached = await send({ type: "DICT_LOOKUP", text: "学校" });
    expect(cached.message).toContain("bộ nhớ đệm cục bộ");
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(createTab).not.toHaveBeenCalled();
  });

  it("reports unavailable translation sources instead of fabricating a result", async () => {
    fetchMock.mockRejectedValue(new TypeError("offline"));
    const result = await send({ type: "DICT_LOOKUP", text: "unlisted word" });
    expect(result).toMatchObject({ ok: false, message: expect.stringContaining("không kết nối") });
    expect(result.entries).toBeUndefined();
    expect(createTab).not.toHaveBeenCalled();
  });

  it("keeps an offline save across worker restart and retries the same operation id", async () => {
    const word = { request_id: "stable-operation-1", original_text: "学校", language: "ja", meanings: { vi: ["trường học"] } };
    fetchMock.mockRejectedValueOnce(new TypeError("offline"));
    const queued = await send({ type: "SAVE_WORD", word });
    expect(queued).toMatchObject({ ok: false, queued: true, message: expect.stringContaining("Chưa lưu lên Web") });
    expect(storageState.pendingWords).toEqual([word]);
    fetchMock.mockRejectedValueOnce(new TypeError("still offline"));
    await send({ type: "SAVE_WORD", word });
    expect(storageState.pendingWords).toEqual([word]);

    vi.resetModules();
    await import("../src/background/service-worker.js");
    fetchMock
      .mockResolvedValueOnce(new Response(JSON.stringify({ data: { health: "ok" } }), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ data: { id: "word-id", created: true } }), { status: 201 }));
    const online = await send({ type: "PING" });
    expect(online.ok).toBe(true);
    expect(storageState.pendingWords).toEqual([]);
    const upload = fetchMock.mock.calls.find(([url]) => String(url).includes("/my-words/extension"))?.[1] as RequestInit;
    expect(JSON.parse(String(upload.body))).toMatchObject({ request_id: "stable-operation-1" });
    expect(createTab).not.toHaveBeenCalled();
  });

  it("does not put revoked credentials or other HTTP errors into the offline queue", async () => {
    fetchMock.mockResolvedValueOnce(new Response(JSON.stringify({ error: { message: "Credential revoked" } }), { status: 401 }));
    const result = await send({ type: "SAVE_WORD", word: { request_id: "bad-credential-op", original_text: "語", language: "ja" } });
    expect(result).toMatchObject({ ok: false, message: "Credential revoked" });
    expect(result.queued).toBeUndefined();
    expect(storageState.pendingWords).toBeUndefined();
  });
});
