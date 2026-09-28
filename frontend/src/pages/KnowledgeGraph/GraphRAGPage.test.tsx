import { describe, it, expect, beforeEach, beforeAll, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import GraphRAGPage from "./GraphRAGPage";

const apiHolder = vi.hoisted(() => ({
  graphApi: {
    ragHealth: vi.fn(),
    ragGraphStats: vi.fn(),
    ragStatus: vi.fn(),
    ragQuery: vi.fn(),
  },
}));

vi.mock("@api/modules", () => ({
  graphApi: apiHolder.graphApi,
}));

// 输入框占位文案（与组件保持一致）
const PLACEHOLDER = "就图谱中的论文与关系提问（引用 / 结构 / 属性均可），按 Enter 发送";

describe("GraphRAGPage", () => {
  beforeAll(() => {
    // jsdom 未实现 Element.scrollIntoView
    Object.defineProperty(Element.prototype, "scrollIntoView", {
      writable: true,
      value: () => {},
    });
  });

  beforeEach(() => {
    vi.clearAllMocks();
    apiHolder.graphApi.ragHealth.mockResolvedValue({ data: { status: "connected" } });
    apiHolder.graphApi.ragGraphStats.mockResolvedValue({
      data: { total_nodes: 3, total_relations: 2, node_labels: { Material: 1 } },
    });
    apiHolder.graphApi.ragStatus.mockResolvedValue({
      data: { current_model: "qwen2.5", base_url: "http://localhost:1234/v1" },
    });
    apiHolder.graphApi.ragQuery.mockResolvedValue({
      data: { answer: "回答内容", keywords: ["性能"], context: {} },
    });
  });

  it("渲染标题、连接状态与图谱统计", async () => {
    render(
      <MemoryRouter>
        <GraphRAGPage />
      </MemoryRouter>,
    );

    expect(screen.getByText("GraphRAG 智能问答")).toBeInTheDocument();
    expect(await screen.findByText("GraphRAG 已连接")).toBeInTheDocument();
    expect(screen.getByText("图谱统计")).toBeInTheDocument();
    expect(screen.getByText("LLM 状态")).toBeInTheDocument();
    expect(screen.getByText("节点总数")).toBeInTheDocument();
    expect(await screen.findByText("当前模型")).toBeInTheDocument();
    expect(await screen.findByText("LLM: qwen2.5")).toBeInTheDocument();
  });

  it("服务未连接时显示警告", async () => {
    apiHolder.graphApi.ragHealth.mockResolvedValue({ data: { status: "disconnected" } });
    apiHolder.graphApi.ragGraphStats.mockResolvedValue({ data: {} });

    render(
      <MemoryRouter>
        <GraphRAGPage />
      </MemoryRouter>,
    );

    expect(await screen.findByText("GraphRAGTest 服务未连接")).toBeInTheDocument();
    expect(screen.getByText("未连接")).toBeInTheDocument();
  });

  it("输入问题并发送调用 ragQuery 并展示回答", async () => {
    render(
      <MemoryRouter>
        <GraphRAGPage />
      </MemoryRouter>,
    );

    await screen.findByText("GraphRAG 已连接");
    const textarea = screen.getByPlaceholderText(PLACEHOLDER);
    await userEvent.type(textarea, "问题内容");
    await userEvent.click(screen.getByRole("button", { name: /发\s*送/ }));

    expect(await screen.findByText("回答内容")).toBeInTheDocument();
    expect(apiHolder.graphApi.ragQuery).toHaveBeenCalledWith("问题内容", true);
  });

  it("溯源来源含 page_number 时展示页码标签", async () => {
    apiHolder.graphApi.ragQuery.mockResolvedValue({
      data: {
        answer: "有来源的回答",
        keywords: [],
        sources: [
          {
            document_id: "doc1",
            page_number: 5,
            snippet: "钙钛矿效率提升",
            score: 0.92,
          },
        ],
      },
    });

    render(
      <MemoryRouter>
        <GraphRAGPage />
      </MemoryRouter>,
    );

    await screen.findByText("GraphRAG 已连接");
    const textarea = screen.getByPlaceholderText(PLACEHOLDER);
    await userEvent.type(textarea, "页码问题");
    await userEvent.click(screen.getByRole("button", { name: /发\s*送/ }));

    expect(await screen.findByText("第 5 页")).toBeInTheDocument();
    // 组件当前文案为「溯源来源 (1)」（无尾冒号），用正则容错空格与拆分的文本节点
    expect(screen.getByText(/溯源来源\s*\(1\)/)).toBeInTheDocument();
  });

  it("清空对话回到空状态", async () => {
    render(
      <MemoryRouter>
        <GraphRAGPage />
      </MemoryRouter>,
    );

    await screen.findByText("GraphRAG 已连接");
    const textarea = screen.getByPlaceholderText(PLACEHOLDER);
    await userEvent.type(textarea, "问题内容");
    await userEvent.click(screen.getByRole("button", { name: /发\s*送/ }));
    await screen.findByText("回答内容");

    await userEvent.click(screen.getByRole("button", { name: /清\s*空/ }));
    // 清空后回到空态引导卡片（与组件当前文案一致）
    expect(screen.getByText("开始一次知识图谱问答")).toBeInTheDocument();
  });

  it("示例问题仅 3 条且均可在图谱中回答", async () => {
    render(
      <MemoryRouter>
        <GraphRAGPage />
      </MemoryRouter>,
    );
    await screen.findByText("GraphRAG 已连接");

    // 三类图谱查询类型均有呈现
    expect(screen.getByText(/支持\s*引用关系\s*\/\s*结构关系\s*\/\s*节点关系/)).toBeInTheDocument();

    // 三条示例问题分别对应：CITES 引用边、CONTAINS 结构、节点一跳关系
    // 注：空态引导与底部提示各渲染一份，故用 getAllByText
    const questions = [
      /《Attention Is All You Need》引用了图谱中的哪些论文/,
      /图谱中论文与正文分段（Chunk）是如何关联的/,
      /Layer Normalization 在图谱中与哪些节点存在关系/,
    ];
    questions.forEach((q) => expect(screen.getAllByText(q).length).toBeGreaterThan(0));

    // 底部提示区恰好 3 条（不再包含纯关系库字段型问题）
    expect(screen.getAllByTestId("graphrag-example-tag").length).toBe(3);
    expect(screen.queryByText(/是哪一年发表的？$/)).not.toBeInTheDocument();
    expect(screen.queryByText(/的作者有哪些？$/)).not.toBeInTheDocument();
    expect(screen.queryByText(/钙钛矿|太阳能电池|材料类实体/)).not.toBeInTheDocument();
  });

  it("点击示例问题填入输入框", async () => {
    render(
      <MemoryRouter>
        <GraphRAGPage />
      </MemoryRouter>,
    );
    await screen.findByText("GraphRAG 已连接");

    await userEvent.click(
      screen.getAllByText(/《Attention Is All You Need》引用了图谱中的哪些论文/)[0],
    );
    expect((screen.getByPlaceholderText(PLACEHOLDER) as HTMLTextAreaElement).value).toBe(
      "《Attention Is All You Need》引用了图谱中的哪些论文？",
    );
  });
});
