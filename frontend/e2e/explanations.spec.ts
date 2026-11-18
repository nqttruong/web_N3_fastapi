import { expect, test, type APIRequestContext } from "@playwright/test";

const API = "http://127.0.0.1:8001/api/v1";

async function setup(request: APIRequestContext) {
  const exam = (await (await request.post(`${API}/exams`, { data: { title: `AI E2E ${Date.now()}`, category: "grammar" } })).json()).data;
  const question = (
    await (
      await request.post(`${API}/exams/${exam.id}/questions`, {
        data: {
          question_number: 1,
          question_type: "grammar_form",
          question_text: "雨が降っている（　　）、試合は<u>中止</u>になった。",
          options: ["のに", "ので", "ながら", "ばかりか"],
          correct_answer: 2,
          answer_status: "verified",
        },
      })
    ).json()
  ).data;
  const end = new Date(Date.now() - 60_000);
  const attempt = (
    await (
      await request.post(`${API}/attempts`, {
        data: {
          exam_id: exam.id,
          started_at: new Date(end.getTime() - 600_000).toISOString(),
          completed_at: end.toISOString(),
          answers: [{ question_id: question.id, selected_answer: 1 }],
        },
      })
    ).json()
  ).data;
  return { exam, question, attempt };
}

// What a ChatGPT answer looks like (self-written for the test).
function chatgptAnswer(questionId: string, options: string[], correctIndex: number) {
  return {
    explanations: [
      {
        schema_version: "1.0",
        question_id: questionId,
        correct_answer_index: correctIndex,
        translation_vi: "Vì trời đang mưa nên trận đấu bị huỷ.",
        solution_summary_vi: "Vế trước là nguyên nhân, vế sau là kết quả khách quan nên chọn ので.",
        correct_explanation: "「ので」 nối nguyên nhân khách quan với kết quả: mưa → trận đấu bị huỷ.",
        recognition_tips: "Vế sau là kết quả tự nhiên của vế trước.",
        options_analysis: options.map((text, i) => ({
          option_index: i,
          option_text: text,
          meaning_vi: `Nghĩa của 「${text}」`,
          is_correct: i === correctIndex,
          reason:
            i === correctIndex
              ? "「ので」 diễn tả nguyên nhân khách quan dẫn tới kết quả ở vế sau."
              : `「${text}」 không diễn tả quan hệ nguyên nhân – kết quả cần có ở câu này.`,
          when_it_would_be_correct: i === correctIndex ? null : `Dùng 「${text}」 khi câu mang nghĩa khác.`,
          difference_from_correct: i === correctIndex ? null : "Khác ので về quan hệ giữa hai vế.",
          common_misconception: i === correctIndex ? null : "Người học có thể nhầm vì hình thức gần giống.",
          how_to_distinguish: i === correctIndex ? null : "Xem vế sau là kết quả hay là điều trái mong đợi.",
          example_ja: null,
          example_vi: null,
        })),
        grammar_points: [{ pattern: "〜ので", meaning_vi: "vì", usage: "Nêu nguyên nhân khách quan.", contrast: "〜のに: trái mong đợi", example_ja: "雨なので、出かけません。" }],
        vocabulary: [{ surface: "中止", reading: "ちゅうし", meaning_vi: "huỷ bỏ", note: null }],
        kanji: [],
        sentence_structure: null,
        evidence: [],
        key_takeaway: "ので = nguyên nhân → kết quả; のに = trái mong đợi.",
        review_topics: ["〜ので", "〜のに"],
        quality: { context_sufficient: true, source_answer_concern: null, uncertainty_notes: [] },
      },
    ],
  };
}

test("manual ChatGPT mode: export prompt → paste JSON → preview → save → approve", async ({ page, request }) => {
  const { exam, question, attempt } = await setup(request);
  const caps = (await (await request.get(`${API}/explanations/capabilities`)).json()).data;
  expect(caps.api_available).toBe(false); // E2E backend runs without an API key

  // Verify the user-initiated handoff without navigating to or controlling ChatGPT.
  await page.addInitScript(() => {
    const testWindow = window as Window & { __copiedPrompt?: string; __openedChatGPT?: string };
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: { writeText: async (text: string) => { testWindow.__copiedPrompt = text; } },
    });
    window.open = ((url: string) => {
      testWindow.__openedChatGPT = url;
      return null;
    }) as typeof window.open;
  });

  await page.goto(`/attempts/${attempt.id}`);
  await expect(page.getByTestId("ai-stat-incorrect")).toHaveText("1");
  await expect(page.getByRole("button", { name: /AI chữa các câu sai/ })).toHaveCount(0);
  await page.getByRole("button", { name: "Toàn bộ đề" }).click();
  await page.getByRole("link", { name: /Xuất prompt cho ChatGPT \(1\)/ }).click();

  await expect(page).toHaveURL(/\/explanations\/manual\?q=/);
  await expect(page.getByLabel("Prompt cho ChatGPT")).toHaveValue(new RegExp(question.id));
  await expect(page.getByLabel("Prompt cho ChatGPT")).toHaveValue(/"learner_selected_index": 0/);
  await page.getByRole("button", { name: "Chữa bài với ChatGPT" }).click();
  await expect.poll(() => page.evaluate(() => (window as Window & { __openedChatGPT?: string }).__openedChatGPT)).toBe("https://chatgpt.com/");
  const promptText = await page.getByLabel("Prompt cho ChatGPT").inputValue();
  await expect.poll(() => page.evaluate(() => (window as Window & { __copiedPrompt?: string }).__copiedPrompt)).toBe(promptText);

  // A ChatGPT answer that tries to change the verified key is refused
  const bad = chatgptAnswer(question.id, question.options, 0);
  await page.getByLabel("JSON từ ChatGPT").fill(JSON.stringify(bad));
  await page.getByRole("button", { name: "Kiểm tra & xem trước" }).click();
  await expect(page.getByText("Không hợp lệ — sẽ không lưu")).toBeVisible();
  await expect(page.getByRole("button", { name: /Xác nhận lưu 0/ })).toBeDisabled();

  const good = chatgptAnswer(question.id, question.options, 1);
  await page.getByLabel("JSON từ ChatGPT").fill("```json\n" + JSON.stringify(good, null, 2) + "\n```");
  await page.getByRole("button", { name: "Kiểm tra & xem trước" }).click();
  const item = page.getByTestId("manual-preview-item");
  await expect(item).toContainText("Hợp lệ · sẽ lưu là “đang chờ duyệt”");
  await expect(item.getByTestId("explanation-view")).toContainText("ちゅうし");
  await page.getByRole("button", { name: "Xác nhận lưu 1 lời giải hợp lệ" }).click();
  await page.getByRole("link", { name: "Đã lưu — mở để xác nhận" }).click();

  await expect(page).toHaveURL(/\/questions\/.+\/explanation/);
  await expect(page.getByText("Lời giải đang chờ bạn xác nhận")).toBeVisible();
  await expect(page.getByText("Đáp án đúng", { exact: true }).locator("..")).toContainText("2. ので");
  await page.getByRole("button", { name: "Xác nhận lời giải" }).click();
  await expect(page.getByText("Đã xác nhận lời giải.")).toBeVisible();
  await expect(page.locator("text=Đã xác nhận").first()).toBeVisible();

  // Reload keeps everything (stored server-side) and the attempt page reflects it
  await page.goto(`/attempts/${attempt.id}`);
  await expect(page.getByTestId("ai-stat-explained")).toHaveText("1");
  await page.getByTestId("attempt-answer").getByRole("link", { name: "Xem lời giải đầy đủ" }).click();
  await expect(page.getByText("Vì sao dễ nhầm:").first()).toBeVisible(); // learner view from the real selection

  await page.goto(`/attempts/${attempt.id}`);
  await page.getByRole("link", { name: "Trích xuất kiến thức" }).click();
  await expect(page.getByRole("heading", { name: "Trích xuất kiến thức" })).toBeVisible();
  await expect(page.getByTestId("extract-question")).toHaveCount(1);
  await page.getByRole("button", { name: /Xác nhận \d+ mục/ }).click();
  await expect(page.getByText("Đã lưu vào kho kiến thức")).toBeVisible();
  await expect(page.getByRole("alert").filter({ hasText: "Đã lưu vào kho kiến thức" })).toBeVisible();
  await expect(page.getByRole("alert").getByRole("link", { name: "Kho kiến thức" })).toBeVisible();
  await expect(page.getByRole("link", { name: /bài ôn|ôn tập/i })).toHaveCount(0);

  await page.goto(`/exams/${exam.id}`);
  await expect(page.getByText("Lời giải hiện hành: 1 Lời giải ChatGPT đã duyệt")).toBeVisible();
  const examList = await (await request.get(`${API}/exams?q=${encodeURIComponent(exam.title)}`)).json();
  expect(examList.data[0].approved_explanation_count).toBe(1);
  const attemptList = await (await request.get(`${API}/attempts?exam_id=${exam.id}`)).json();
  expect(attemptList.data[0].approved_explanation_count).toBe(1);
  await request.patch(`${API}/questions/${question.id}`, { data: { question_text: "雨が降っているのに、試合は中止になった。" } });
  const staleExamList = await (await request.get(`${API}/exams?q=${encodeURIComponent(exam.title)}`)).json();
  expect(staleExamList.data[0].approved_explanation_count).toBe(0);
  const staleAttemptList = await (await request.get(`${API}/attempts?exam_id=${exam.id}`)).json();
  expect(staleAttemptList.data[0].approved_explanation_count).toBe(0);
});

test("unverified question cannot be explained and links to answer confirmation", async ({ page, request }) => {
  const exam = (await (await request.post(`${API}/exams`, { data: { title: `AI E2E U ${Date.now()}`, category: "grammar" } })).json()).data;
  const q = (
    await (
      await request.post(`${API}/exams/${exam.id}/questions`, {
        data: { question_number: 1, question_type: "grammar_form", question_text: "文（　　）。", options: ["あ", "い"], correct_answer: 1 },
      })
    ).json()
  ).data;
  await page.goto(`/questions/${q.id}/explanation`);
  await expect(page.getByText("Chưa thể chữa câu này")).toBeVisible();
  await expect(page.getByRole("link", { name: "Xác nhận đáp án trong trang đề" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Xuất prompt" })).toHaveCount(0);
});
