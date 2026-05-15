import { expect, test } from "@playwright/test";

test("configured app opens workbench shell", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("link", { name: "工作台" })).toBeVisible();
  await expect(page.getByRole("link", { name: "开书" })).toBeVisible();
  await expect(page.getByRole("link", { name: "设置" })).toBeVisible();
});
