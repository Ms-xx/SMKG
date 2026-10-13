import { test, expect } from "@playwright/test";

test.describe("冒烟测试", () => {
  test("未登录访问首页展示免鉴权展示页，受保护路由重定向到登录页", async ({ page }) => {
    // 站点入口 `/` 自 v6.3 起为无需鉴权的展示页（router/index.tsx 中 LandingPage），
    // 不再直接重定向到登录页；此处断言展示页可见 + 受保护路由仍会拦到登录页。
    await page.goto("/");
    await expect(page).toHaveURL(/\/$/, { timeout: 15000 });
    await expect(page.getByText("科学文献智能解析平台").first()).toBeVisible();

    await page.goto("/dashboard");
    await expect(page).toHaveURL(/\/login/, { timeout: 15000 });
  });

  test("访问不存在的路由展示 404 页面", async ({ page }) => {
    await page.goto("/non-existent-route");
    await expect(page.getByText("抱歉，您访问的页面不存在")).toBeVisible();
  });
});