import { readFileSync } from "node:fs";
import path from "node:path";

import { expect, test, type Page } from "@playwright/test";

// Self-authored fixtures (copied from backend/tests/fixtures/imports).
const fixture = (name: string) => readFileSync(path.join(__dirname, "fixtures", name), "utf-8");
const API = "http://127.0.0.1:8001/api/v1";

async function stat(page: Page, id: string) {
  return page.getByTestId(`import-stat-${id}`);
}

test("paste text → preview → confirm answers → save → exam opens in PR1 view", async ({ page }) => {
  const url = `https://example.com/e2e-text-${Date.now()}`;
  await page.goto("/exams/new");
  await expect(page.getByRole("tab", { name: "Dán văn bản" })).toHaveAttribute("aria-selected", "true");

  // Validation: empty submit
  await page.getByRole("button", { name: "Phân tích & xem trước" }).click();
  await expect(page.getByText("Vui lòng dán nội dung đề")).toBeVisible();

  await page.getByLabel("URL đề gốc").fill(url);
  await page.getByLabel("Nội dung đề").fill(fixture("text_basic.txt"));
  await page.getByRole("button", { name: "Phân tích & xem trước" }).click();

  await expect(page).toHaveURL(/\/imports\/[0-9a-f-]{36}$/);
  await expect(await stat(page, "recognized")).toHaveText("3");
  await expect(await stat(page, "missing-answer")).toHaveText("1");
  await expect(await stat(page, "verified")).toHaveText("0"); // never pre-confirmed
  const cards = page.getByTestId("import-question");
  await expect(cards).toHaveCount(3);
  await expect(cards.nth(0).locator("u")).toHaveText("深い"); // inline markup rendered safely

  // Confirm Q1's site answer explicitly; give Q2 an answer by editing, then confirm it
  await cards.nth(0).getByRole("button", { name: /Xác nhận đáp án 1/ }).click();
  await cards.nth(1).getByRole("button", { name: "Sửa" }).click();
  await cards.nth(1).getByRole("combobox", { name: "Đáp án chuẩn" }).click();
  await page.getByRole("option", { name: "1", exact: true }).click();
  await cards.nth(1).getByRole("button", { name: /Xác nhận đáp án 1/ }).click();
  await page.getByRole("button", { name: "Lưu thay đổi" }).click();
  await expect(page.getByText("Đã lưu bản nháp.")).toBeVisible();
  await expect(await stat(page, "verified")).toHaveText("2");

  // Reload keeps the draft (stored server-side)
  await page.reload();
  await expect(await stat(page, "verified")).toHaveText("2");

  await page.getByRole("button", { name: "Lưu thành đề" }).click();
  await expect(page.getByRole("dialog")).toContainText("2 đáp án đã xác nhận, 1 chưa xác nhận, 0 chưa có đáp án");
  await page.getByRole("button", { name: "Xác nhận lưu" }).click();

  await expect(page).toHaveURL(/\/exams\/[0-9a-f-]{36}$/);
  await expect(page.getByRole("heading", { name: "N3 模擬テスト（自作）第１回" })).toBeVisible();
  await expect(page.getByTestId("question-item")).toHaveCount(3);
  await expect(page.getByText("Đáp án chuẩn", { exact: true })).toHaveCount(2);
});

test("paste HTML (dethitiengnhat layout) → attempt created from the user's own answers", async ({ page, request }) => {
  const html = fixture("dethitiengnhat_like_scored.html").replace(
    "https://dethitiengnhat.com/jlpt/N3/99/3",
    `https://dethitiengnhat.com/jlpt/N3/99/3?e2e=${Date.now()}`,
  );
  await page.goto("/exams/new?tab=html");
  await page.getByLabel("Mã HTML").fill(html);
  await page.getByRole("button", { name: "Phân tích & xem trước" }).click();

  await expect(page).toHaveURL(/\/imports\//);
  await expect(page.getByText("Dethitiengnhat (cấu trúc đã kiểm chứng)")).toBeVisible();
  await expect(await stat(page, "recognized")).toHaveText("6");
  await expect(await stat(page, "included")).toHaveText("5");
  const cards = page.getByTestId("import-question");
  await expect(cards.nth(1)).toContainText("Bạn đã chọn");

  // Attempt needs times supplied by the user
  await page.getByText("Tạo bài làm khi lưu").click();
  const now = new Date(Date.now() - 60_000);
  const start = new Date(now.getTime() - 30 * 60_000);
  const local = (d: Date) => new Date(d.getTime() - d.getTimezoneOffset() * 60_000).toISOString().slice(0, 16);
  await page.getByLabel("Bắt đầu làm lúc *").fill(local(start));
  await page.getByLabel("Nộp bài lúc *").fill(local(now));
  for (let i = 1; i < 6; i++) {
    await cards.nth(i).getByRole("button", { name: /Xác nhận đáp án/ }).click();
  }
  await page.getByRole("button", { name: "Lưu thay đổi" }).click();
  await expect(page.getByText("Đã lưu bản nháp.")).toBeVisible();
  await expect(page.getByRole("button", { name: "Lưu thành đề" })).toBeEnabled();
  await page.getByRole("button", { name: "Lưu thành đề" }).click();
  await page.getByRole("button", { name: "Xác nhận lưu" }).click();
  await expect(page).toHaveURL(/\/exams\/[0-9a-f-]{36}$/);

  const examId = page.url().split("/").pop();
  const attempts = await (await request.get(`${API}/attempts?exam_id=${examId}`)).json();
  expect(attempts.meta.total).toBe(1);
  expect(attempts.data[0].source).toBe("import");
  // Q2 wrong, Q3 right, Q4 blank, Q5 wrong, Q6 right
  expect([attempts.data[0].correct_count, attempts.data[0].incorrect_count, attempts.data[0].unanswered_count]).toEqual([2, 2, 1]);

  // Importing the same page again is detected and can reuse the exam
  await page.goto("/exams/new?tab=html");
  await page.getByLabel("Mã HTML").fill(html);
  await page.getByRole("button", { name: "Phân tích & xem trước" }).click();
  await expect(page.getByText(/Đã có đề .* với cùng URL nguồn/)).toBeVisible();
});

test("upload tab explains OCR state and validates files client-side", async ({ page, request }) => {
  const caps = await (await request.get(`${API}/imports/capabilities`)).json();
  await page.goto("/exams/new?tab=images");
  if (caps.data.ocr.available) {
    await expect(page.getByText(/OCR khả dụng/)).toBeVisible();
    await page.getByLabel("Ảnh chụp (theo thứ tự đọc)").setInputFiles({ name: "x.gif", mimeType: "image/gif", buffer: Buffer.from("GIF89a") });
    await expect(page.getByText("“x.gif”: chỉ hỗ trợ PNG, JPG, WEBP.")).toBeVisible();
  } else {
    await expect(page.getByText("OCR chưa khả dụng")).toBeVisible();
    await expect(page.getByRole("button", { name: "Tải lên & nhận dạng" })).toBeDisabled();
  }
});

test("unified exam library draft tab shows imports", async ({ page }) => {
  await page.goto("/exams?tab=drafts");
  await expect(page.getByRole("tab", { name: "Bản nháp nhập" })).toHaveAttribute("aria-selected", "true");
  await expect(page.getByTestId("import-drafts")).toBeVisible();
  await expect(page.getByRole("link", { name: "N3 模擬テスト（自作）第１回" }).first()).toBeVisible();
});
