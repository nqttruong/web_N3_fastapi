import { expect, test, type Page } from "@playwright/test";

const unique = () => Date.now().toString(36);

async function addQuestion(
  page: Page,
  { text, options, correct }: { text: string; options: string[]; correct: number },
) {
  const form = page.getByRole("form", { name: "Thêm câu hỏi" });
  const previousCount = await page.getByTestId("question-item").count();
  await form.getByLabel("Nội dung câu hỏi").fill(text);
  for (const [i, option] of options.entries()) {
    await form.getByLabel(`Lựa chọn ${i + 1}`, { exact: true }).fill(option);
  }
  await form.getByLabel(`Đáp án đúng · Lựa chọn ${correct}`).check();
  await form.getByRole("button", { name: "Thêm câu hỏi" }).click();
  await expect(page.getByTestId("question-item")).toHaveCount(previousCount + 1);
  await expect(form.getByLabel("Nội dung câu hỏi")).toHaveValue("");
}

test("full flow: create exam, add questions, take it, results persist", async ({ page }) => {
  const title = `E2E 文法テスト ${unique()}`;

  // The overview intentionally focuses on learning activity; exam metrics live in Analytics.
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Tổng quan" })).toBeVisible();
  await expect(page.getByText("Danh ngôn Nhật hôm nay", { exact: true })).toBeVisible();

  // Create exam
  await page.goto("/exams");
  await page.getByText("Thêm đề", { exact: true }).click();
  await page.getByRole("link", { name: "Tạo đề thủ công" }).click();
  await expect(page.getByRole("heading", { name: "Nhập đề" })).toBeVisible();
  await page.getByRole("tab", { name: "Tạo đề thủ công" }).click();
  await page.getByRole("textbox", { name: "Tên đề", exact: true }).fill(title);
  await page.getByRole("combobox", { name: "Loại đề" }).click();
  await page.getByRole("option", { name: "Ngữ pháp" }).click();
  await page.getByLabel("URL nguồn").fill("https://example.com/n3/grammar-e2e");
  await page.getByRole("button", { name: "Tạo đề" }).click();

  await expect(page.getByRole("heading", { name: title })).toBeVisible();
  await expect(page.getByText("Đề chưa có câu hỏi")).toBeVisible();

  // Add two questions with verified answers
  await addQuestion(page, {
    text: "毎日練習した（　　）、試合に勝てた。",
    options: ["おかげで", "せいで", "くせに", "わりに"],
    correct: 1,
  });
  await expect(page.getByTestId("question-item")).toHaveCount(1);
  await expect(page.getByLabel("Số câu")).toHaveValue("2");
  await addQuestion(page, {
    text: "ドアを開けた（　　）、猫が飛び出した。",
    options: ["うちに", "ばかりに", "とたん", "最中に"],
    correct: 3,
  });
  await addQuestion(page, {
    text: "今日は雨です。",
    options: ["はい", "いいえ"],
    correct: 1,
  });
  await expect(page.getByTestId("question-item")).toHaveCount(3);
  await expect(page.getByText("Đáp án chuẩn", { exact: true })).toHaveCount(3);

  // Take the exam: Q1 correct, Q2 wrong
  await page.getByRole("link", { name: "Làm bài" }).first().click();
  await expect(page.getByTestId("practice-question")).toHaveCount(1);
  await page.getByTestId("practice-question").getByLabel("おかげで").check();
  await page.getByRole("button", { name: "Câu tiếp" }).click();
  await page.getByTestId("practice-question").getByLabel("うちに").check();
  await page.getByRole("button", { name: "Câu tiếp" }).click();
  await expect(page.getByText("Câu 3/3", { exact: false })).toBeVisible();
  page.once("dialog", (dialog) => dialog.accept());
  await page.getByRole("button", { name: "Nộp bài" }).click();

  // Server-graded result
  await expect(page).toHaveURL(/\/attempts\/[0-9a-f-]{36}$/);
  await expect(page.getByTestId("summary-Đúng")).toHaveText("1");
  await expect(page.getByTestId("summary-Sai")).toHaveText("1");
  await expect(page.getByTestId("summary-Độ chính xác đã chấm")).toHaveText("50%");
  await expect(page.getByTestId("summary-Đúng trên tổng câu")).toHaveText("33,3%");
  await expect(page.getByRole("link", { name: /Đề gốc/ })).toHaveAttribute(
    "href",
    "https://example.com/n3/grammar-e2e",
  );

  // Reload: data comes back from the backend
  await page.reload();
  await expect(page.getByTestId("summary-Đúng")).toHaveText("1");
  await expect(page.getByTestId("attempt-answer")).toHaveCount(3);

  await page.goto("/mistakes");
  await expect(page.getByRole("heading", { name: "Sổ lỗi sai" })).toBeVisible();
  const mistakeCard = page.getByTestId("mistake-card").filter({ hasText: "ドアを開けた（　　）、猫が飛び出した。" }).first();
  await expect(mistakeCard.getByText(/Sai 1 lần/)).toBeVisible();
  await expect(mistakeCard.getByRole("link", { name: "Chữa câu sai bằng ChatGPT" })).toBeVisible();

  await page.goto("/analytics/jlpt");
  await expect(page).toHaveURL("/analytics/jlpt");
  await expect(page.getByRole("heading", { name: "Phân tích JLPT" })).toBeVisible();
  await expect(page.getByText(/Attempt từ Android: chưa được đồng bộ/)).toBeVisible();
  await expect(page.getByText("Kết quả theo kỹ năng")).toBeVisible();

  // The overview remains a learning summary and does not duplicate Analytics.
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Tổng quan" })).toBeVisible();
  await expect(page.getByText("Danh ngôn Nhật hôm nay", { exact: true })).toBeVisible();

  await page.goto("/exams");
  await expect(page.getByRole("tab", { name: "Đề đã lưu" })).toBeVisible();
  await page.getByRole("link", { name: title }).click();
  await expect(page.getByRole("heading", { name: "Lịch sử", exact: true })).toBeVisible();
  await expect(page.getByText("Lời giải hiện hành: chưa có lời giải hiện hành")).toBeVisible();
  await page.getByRole("link", { name: "Chữa bằng ChatGPT" }).click();
  await expect(page).toHaveURL(/\/attempts\/[0-9a-f-]{36}#ai-review$/);
  await expect(page.locator("#ai-review")).toBeVisible();
});

test("exam library search and category filter", async ({ page, request }) => {
  const tag = unique();
  for (const [title, category] of [
    [`Kanji ${tag}`, "kanji"],
    [`読解 ${tag}`, "reading"],
  ] as const) {
    const res = await request.post("http://127.0.0.1:8001/api/v1/exams", { data: { title, category } });
    expect(res.status()).toBe(201);
  }

  await page.goto("/exams");
  await page.getByText("Thêm đề", { exact: true }).click();
  await page.getByRole("link", { name: /Chrome Extension/ }).click();
  await expect(page).toHaveURL("/exams?tab=drafts");
  await page.getByRole("tab", { name: "Đề đã lưu" }).click();
  await page.getByRole("button", { name: "Đọc hiểu" }).click();
  await expect(page).toHaveURL(/category=reading/);
  await expect(page.getByRole("link", { name: `読解 ${tag}` })).toBeVisible();
  await expect(page.getByRole("link", { name: `Kanji ${tag}` })).toHaveCount(0);

  await page.getByRole("button", { name: "Tất cả" }).click();
  await page.getByRole("searchbox", { name: "Tìm kiếm đề" }).fill(`Kanji ${tag}`);
  await expect(page).toHaveURL(/q=Kanji/);
  await expect(page.getByRole("link", { name: `Kanji ${tag}` })).toBeVisible();
  await expect(page.getByRole("link", { name: `読解 ${tag}` })).toHaveCount(0);

  await page.getByRole("searchbox", { name: "Tìm kiếm đề" }).fill(`không-tồn-tại-${tag}`);
  await expect(page.getByText("Không có đề phù hợp")).toBeVisible();
});

test("create form shows validation errors and does not submit", async ({ page }) => {
  await page.goto("/exams/new?tab=manual");
  await page.getByLabel("URL nguồn").fill("ftp://example.com");
  await page.getByRole("button", { name: "Tạo đề" }).click();
  await expect(page.getByText("Vui lòng nhập tên đề")).toBeVisible();
  await expect(page.getByText("Vui lòng chọn loại đề")).toBeVisible();
  await expect(page.getByText("URL phải bắt đầu bằng http:// hoặc https://")).toBeVisible();
  await expect(page).toHaveURL(/\/exams\/new\?tab=manual$/);
});

test("unknown exam shows a not-found error state", async ({ page }) => {
  await page.goto("/exams/00000000-0000-4000-8000-000000000000");
  await expect(page.getByText("Không tìm thấy dữ liệu")).toBeVisible();
});

test("V3 navigation separates overview and analysis; mistakes stay inside analysis", async ({ page }) => {
  await page.goto("/");
  const nav = page.getByRole("navigation", { name: "Điều hướng chính" });
  await expect(nav.getByRole("link")).toHaveText([
    "Tổng quan",
    "Học tập",
    "Kho đề",
    "Phân tích JLPT",
    "Cài đặt",
    "Hướng dẫn sử dụng",
  ]);
  await expect(nav.getByRole("link", { name: /Sổ lỗi sai|Kho kiến thức|Ôn tập|Bài làm|Nhập đề|Bản nháp/ })).toHaveCount(0);
  await page.goto("/mistakes");
  await expect(page).toHaveURL("/analytics/jlpt?tab=mistakes");
  await expect(page.getByRole("heading", { name: "Sổ lỗi sai" })).toBeVisible();
  await page.goto("/knowledge");
  await expect(page.getByRole("heading", { name: "Kho kiến thức" })).toBeVisible();
  await expect(page.getByTestId("weakness-summary")).toBeVisible();
  await expect(page.getByTestId("knowledge-list").or(page.getByText("Chưa có kiến thức được lưu"))).toBeVisible();

  await page.goto("/reviews");
  await expect(page).toHaveURL("/exams");
  await page.goto("/imports");
  await expect(page).toHaveURL("/exams?tab=drafts");
  await page.goto("/attempts");
  await expect(page).toHaveURL("/exams");
});

test("mobile layout renders navigation and dashboard @mobile", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("navigation", { name: "Điều hướng chính" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Tổng quan" })).toBeVisible();
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth);
  expect(overflow).toBe(false);
});
