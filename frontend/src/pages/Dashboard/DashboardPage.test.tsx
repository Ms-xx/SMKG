import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import DashboardPage from "./DashboardPage";
import { useDocumentStore } from "@store/documentStore";
import { useAuthStore } from "@store/authStore";
import { graphApi, taskApi } from "@api/modules";

const mockNavigate = vi.hoisted(() => vi.fn());

vi.mock("react-router-dom", async () => {
  const actual = await vi.importActual<any>("react-router-dom");
  return { ...actual, useNavigate: () => mockNavigate };
});
vi.mock("@api/modules", () => ({
  graphApi: { ragGraphStats: vi.fn() },
  taskApi: { getList: vi.fn() },
}));

const doc = {
  id: "d1",
  title: "示例文档",
  status: "parsed",
  created_at: "2026-01-01T00:00:00Z",
} as any;

describe("DashboardPage", () => {
  beforeEach(() => {
    mockNavigate.mockReset();
    (graphApi.ragGraphStats as any).mockReset().mockResolvedValue({
      total_nodes: 5,
      total_relations: 3,
      node_labels: { Material: 2, Method: 1 },
    });
    (taskApi.getList as any).mockReset().mockResolvedValue({ items: [], total: 0 });
    useDocumentStore.setState({
      documents: [],
      total: 0,
      fetchDocuments: vi.fn().mockResolvedValue(undefined),
    });
    useAuthStore.setState({
      user: { id: "u1", username: "alice", role: "admin" } as any,
    });
  });

  it("渲染欢迎语、统计卡片与图谱概览", async () => {
    render(
      <MemoryRouter>
        <DashboardPage />
      </MemoryRouter>,
    );
    expect(await screen.findByText(/欢迎回来/)).toBeInTheDocument();
    expect(screen.getByText("文档总数")).toBeInTheDocument();
    expect(screen.getByText("暂无文档")).toBeInTheDocument();
    expect(screen.getByText("暂无任务")).toBeInTheDocument();
    // 图谱概览
    expect(await screen.findByText("知识图谱概览")).toBeInTheDocument();
    expect(screen.getByText("实体总数")).toBeInTheDocument();
  });

  it("有文档与任务时展示最近文档和最近任务", async () => {
    useDocumentStore.setState({
      documents: [
        doc,
        { ...doc, id: "d2", title: "文档二", status: "parsing" },
        { ...doc, id: "d3", title: "文档三", status: "failed" },
      ],
      total: 3,
    });
    (taskApi.getList as any).mockResolvedValue({
      items: [
        {
          id: "t1",
          task_type: "parsing",
          status: "running",
          progress: 40,
          created_at: "2026-01-01T00:00:00Z",
        },
      ],
      total: 1,
    });
    render(
      <MemoryRouter>
        <DashboardPage />
      </MemoryRouter>,
    );
    expect(await screen.findByText("示例文档")).toBeInTheDocument();
    expect(await screen.findByText("文档解析")).toBeInTheDocument();
  });

  it("点击快捷操作跳转", async () => {
    render(
      <MemoryRouter>
        <DashboardPage />
      </MemoryRouter>,
    );
    await screen.findByText(/欢迎回来/);
    fireEvent.click(screen.getAllByText("上传文档")[0]);
    expect(mockNavigate).toHaveBeenCalledWith("/documents");
  });
});
