import { expect, test } from "@playwright/test";

test("unconfigured app shows only model setup", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "连接你的 AI 模型" })).toBeVisible();
  await expect(page.getByText("工作台")).toHaveCount(0);
  await expect(page.getByText("项目")).toHaveCount(0);
});
