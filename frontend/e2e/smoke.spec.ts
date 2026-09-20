import { test, expect } from "@playwright/test";

test.describe("冒烟测试", () => {
  test("未登录访问首页重定向到登录页", async ({ page }) => {
    await page.goto("/");
    await expect(page).toHaveURL(/\/login/, { timeout: 15000 });
    await expect(page.getByText("科学文献智能解析平台")).toBeVisible();
  });

  test("访问不存在的路由展示 404 页面", async ({ page }) => {
    await page.goto("/non-existent-route");
    await expect(page.getByText("抱歉，您访问的页面不存在")).toBeVisible();
  });
});