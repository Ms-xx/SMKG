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
    const textarea = screen.getByPlaceholderText(
      "输入问题，按 Enter 或点击发送... (Shift+Enter 换行)",
    );
    await userEvent.type(textarea, "问题内容");
    await userEvent.click(screen.getByRole("button", { name: /发\s*送/ }));

    expect(await screen.findByText("回答内容")).toBeInTheDocument();
    expect(apiHolder.graphApi.ragQuery).toHaveBeenCalledWith("问题内容", true);
  });

  it("清空对话回到空状态", async () => {
    render(
      <MemoryRouter>
        <GraphRAGPage />
      </MemoryRouter>,
    );

    await screen.findByText("GraphRAG 已连接");
    const textarea = screen.getByPlaceholderText(
      "输入问题，按 Enter 或点击发送... (Shift+Enter 换行)",
    );
    await userEvent.type(textarea, "问题内容");
    await userEvent.click(screen.getByRole("button", { name: /发\s*送/ }));
    await screen.findByText("回答内容");

    await userEvent.click(screen.getByRole("button", { name: /清\s*空/ }));
    expect(screen.getByText("输入问题开始 GraphRAG 问答")).toBeInTheDocument();
  });
});
