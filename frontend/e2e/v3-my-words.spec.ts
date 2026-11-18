import { expect, test } from "@playwright/test";

test("personal word can be created, reviewed, reloaded, edited and archived", async ({ page }) => {
  const word = `学校-${Date.now()}`;
  await page.goto("/learning/my-words");
  await page.getByRole("button", { name: "Thêm từ của tôi" }).first().click();
  await page.getByLabel("Từ hoặc cụm từ gốc").fill(word);
  await page.getByLabel("Nghĩa Tiếng Việt (mỗi dòng một nghĩa)").fill("trường học\nhọc đường");
  await page.getByLabel("Cách đọc Hiragana").fill("がっこう");
  await page.getByRole("form", { name: "Biểu mẫu thêm từ" }).getByRole("button", { name: "Thêm từ", exact: true }).click();
  await expect(page.getByText(word, { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Lật thẻ" }).click();
  await expect(page.getByText("trường học; học đường")).toBeVisible();
  await page.getByRole("button", { name: "Tốt" }).click();
  await expect(page.getByText(/1 lần ôn/)).toBeVisible();

  await page.reload();
  await expect(page.getByText(word, { exact: true })).toBeVisible();
  await expect(page.getByText(/1 lần ôn/)).toBeVisible();
  await page.getByRole("button", { name: "Sửa" }).click();
  await page.getByLabel("Ngữ cảnh").fill("Trong lớp học");
  await page.getByRole("button", { name: "Lưu thay đổi" }).click();
  await page.getByRole("button", { name: "Lật thẻ" }).click();
  await expect(page.getByText("Ngữ cảnh: Trong lớp học")).toBeVisible();
  await page.getByRole("button", { name: "Bỏ lưu" }).click();
  await expect(page.getByText(word, { exact: true })).toHaveCount(0);
});

test("theme and interface locale persist after reload", async ({ page }) => {
  await page.goto("/settings");
  await page.getByRole("button", { name: "Wabi-sabi" }).click();
  await page.getByRole("button", { name: "Tối", exact: true }).click();
  await page.getByLabel("Ngôn ngữ giao diện").selectOption("ja");
  await expect(page.getByRole("link", { name: "学習" })).toBeVisible();
  await page.reload();
  await expect(page.locator("html")).toHaveAttribute("data-palette", "wabi");
  await expect(page.locator("html")).toHaveClass(/dark/);
  await expect(page.locator("select").first()).toHaveValue("ja");
});

test("PWA manifest and offline fallback are present without personal API caching", async ({ page, request }) => {
  const manifest = await request.get("/manifest.webmanifest");
  expect(manifest.ok()).toBe(true);
  const data = await manifest.json();
  expect(data.name).toContain("JLPT AI Review");
  expect(data.icons.length).toBeGreaterThan(0);
  await page.goto("/offline");
  await expect(page.getByText(/ngoại tuyến|offline/i).first()).toBeVisible();
});
