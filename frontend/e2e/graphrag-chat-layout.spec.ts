import { test, expect, type Page, type Route } from "@playwright/test";

/**
 * 回归测试：GraphRAG 问答对话的布局不再"跑版"。
 *
 * 历史缺陷：antd Card 的 `.ant-card-body` 默认是 block 且高度随内容增长，
 * 内层「flex:1 + overflowY:auto」的消息列表拿不到高度约束 → 不滚动。
 * 结果长答案会撑破 480px 卡片，把输入框挤出卡片外并与下方"示例问题"重叠。
 */
const LONG_ANSWER = [
  "《Attention Is All You Need》引用了以下论文:",
  "1. Layer Normalization",
  "2. Neural Machine Translation by Jointly Learning to Align and Translate",
  "3. Massive Exploration of Neural Machine Translation Architectures",
  "4. Long Short-Term Memory-Networks for Machine Reading",
  "5. Learning Phrase Representations using RNN Encoder-Decoder for Statistical Machine Translation",
  "6. Xception: Deep Learning with Depthwise Separable Convolutions",
  "7. Empirical Evaluation of Gated Recurrent Neural Networks on Sequence Modeling",
  "8. Convolutional Sequence to Sequence Learning",
  "9. Generating Sequences With Recurrent Neural Networks",
  "10. Exploring the Limits of Language Modeling",
  "11. Neural Machine Translation in Linear Time",
  "12. Factorization tricks for LSTM networks",
  "13. A Structured Self-attentive Sentence Embedding",
  "14. Multi-task Sequence to Sequence Learning",
  "15. Effective Approaches to Attention-based Neural Machine Translation",
].join("\n");

const json = (route: Route, body: unknown) =>
  route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(body) });

/** 后端地址：认证走真实登录，仅 RAG 问答链路用 mock 保证确定性。 */
const BACKEND = process.env.E2E_BACKEND_URL || "http://127.0.0.1:8000";

/**
 * 用真实 token 注入登录态。
 * 注意：**不能**只 mock /auth/me 后塞假 token——App 外壳还会请求
 * /notifications 等未 mock 的接口，假 token 会被后端判 401，
 * axios 拦截器随即尝试 refresh，失败后硬跳 /login，页面根本进不去。
 */
async function seedAuth(page: Page, token: string) {
  await page.addInitScript((t) => {
    localStorage.setItem("access_token", t);
    localStorage.setItem("refresh_token", "");
  }, token);
}

/** 只 mock RAG 问答相关接口，避免依赖 GraphRAGTest 与 LLM 的响应时延 */
async function mockRag(page: Page) {
  await page.route("**/api/v1/knowledge-graph/rag/health", (r) => json(r, { status: "connected" }));
  await page.route("**/api/v1/knowledge-graph/rag/graph/stats", (r) =>
    json(r, { total_nodes: 302, total_relations: 192, node_types: [] }),
  );
  await page.route("**/api/v1/knowledge-graph/rag/llm/status", (r) =>
    json(r, { provider: "LM Studio", model: "mock", endpoint: "http://localhost:1234" }),
  );
  await page.route("**/api/v1/knowledge-graph/rag/query", (r) =>
    json(r, {
      answer: LONG_ANSWER,
      keywords: ["引用", "机器学习"],
      context: { nodes: [], relations: [] },
      sources: [],
    }),
  );
}

async function ask(page: Page) {
  await page.goto("/knowledge-graph/rag");
  const box = page.locator('textarea[placeholder*="就图谱中的论文与关系提问"]');
  await expect(box).toBeEnabled({ timeout: 15000 });
  await box.fill("长答案布局回归");
  await box.press("Enter");
  // 等长答案真正渲染出来
  await expect
    .poll(
      async () =>
        page.evaluate(() => {
          const bubble = [...document.querySelectorAll(".ant-card div")].find(
            (d) =>
              getComputedStyle(d).whiteSpace === "pre-wrap" &&
              d.textContent.includes("15. Effective Approaches"),
          );
          return bubble ? bubble.textContent.length : 0;
        }),
      { timeout: 15000 },
    )
    .toBeGreaterThan(200);
}

/** 采集布局关键尺寸 */
async function measure(page: Page) {
  return page.evaluate(() => {
    const card = [...document.querySelectorAll(".ant-card")].find((c) =>
      c.textContent.includes("问答对话"),
    )!;
    const body = card.querySelector(".ant-card-body")!;
    const list = body.children[0] as HTMLElement;
    const inputRow = body.children[body.children.length - 1] as HTMLElement;
    const cardRect = card.getBoundingClientRect();
    const inputRect = inputRow.getBoundingClientRect();
    const tag = document.querySelector('[data-testid="graphrag-example-tag"]')!;
    return {
      cardClientHeight: (card as HTMLElement).clientHeight,
      cardScrollHeight: (card as HTMLElement).scrollHeight,
      cardBottom: cardRect.bottom,
      listClientHeight: list.clientHeight,
      listScrollHeight: list.scrollHeight,
      listOverflowY: getComputedStyle(list).overflowY,
      bodyDisplay: getComputedStyle(body).display,
      inputBottom: inputRect.bottom,
      exampleTagTop: tag.getBoundingClientRect().top,
    };
  });
}

test.describe("GraphRAG 问答对话布局", () => {
  test("长答案不撑破卡片：消息区可滚动、输入框留在卡片内、示例问题不重叠", async ({
    page,
    request,
  }) => {
    // 认证走真实登录；后端未就绪时跳过（避免把环境问题误报为布局缺陷）。
    // 账号口令可通过环境变量覆盖，默认取本地开发默认值。
    const username = process.env.E2E_ADMIN_USERNAME || "admin";
    const password = process.env.E2E_ADMIN_PASSWORD || "admin123";
    const res = await request
      .post(`${BACKEND}/api/v1/auth/login`, {
        data: { username, password },
      })
      .catch(() => null);
    test.skip(!res || !res.ok(), "后端未就绪，跳过该布局回归测试");
    const token = (await res!.json()).access_token;

    await seedAuth(page, token);
    await mockRag(page);
    await ask(page);
    const m = await measure(page);

    // 卡片内容不再溢出（修复前 scrollHeight 会到 768，而 clientHeight 只有 478）
    expect(m.cardScrollHeight).toBeLessThanOrEqual(m.cardClientHeight + 2);

    // 消息列表是真正可滚动的容器
    expect(m.listOverflowY).toBe("auto");
    expect(m.listScrollHeight).toBeGreaterThan(m.listClientHeight);

    // 卡片 body 已成为受约束的 flex 列
    expect(m.bodyDisplay).toBe("flex");

    // 输入框不再被挤出卡片（修复前底部在卡片外 234px）
    expect(m.inputBottom).toBeLessThanOrEqual(m.cardBottom + 1);

    // 下方"示例问题"标签不被卡片内容压住
    expect(m.exampleTagTop).toBeGreaterThanOrEqual(m.cardBottom - 1);
  });
});
