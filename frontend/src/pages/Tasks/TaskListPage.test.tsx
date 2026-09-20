import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import TaskListPage from "./TaskListPage";
import { taskApi, userApi } from "@api/modules";

vi.mock("@api/modules", () => ({
  taskApi: {
    getList: vi.fn(),
    getById: vi.fn(),
    getProgress: vi.fn(),
    pause: vi.fn(),
    resume: vi.fn(),
    cancel: vi.fn(),
    retry: vi.fn(),
    terminate: vi.fn(),
    assign: vi.fn(),
  },
  userApi: { getList: vi.fn() },
}));

const task = (over: Record<string, any> = {}) => ({
  id: "t1",
  task_type: "parsing",
  status: "completed",
  progress: 100,
  priority: 1,
  created_at: "2026-01-01T00:00:00Z",
  ...over,
});

describe("TaskListPage", () => {
  beforeEach(() => {
    (taskApi.getList as any).mockReset().mockResolvedValue({ items: [], total: 0 });
    (taskApi.getById as any).mockReset().mockResolvedValue(task());
    (userApi.getList as any).mockReset().mockResolvedValue({ items: [] });
  });

  it("渲染标题与空状态", async () => {
    render(<TaskListPage />);
    expect(screen.getByText("任务管理")).toBeInTheDocument();
    expect(await screen.findByText("暂无任务")).toBeInTheDocument();
  });

  it("渲染任务列表与各状态标签", async () => {
    (taskApi.getList as any).mockResolvedValue({
      items: [
        task({ id: "a", task_type: "parsing", status: "completed" }),
        task({
          id: "b",
          task_type: "extraction",
          status: "running",
          progress: 50,
          current_step: "抽取中",
        }),
        task({ id: "c", task_type: "graph", status: "failed", progress: 20 }),
        task({ id: "d", task_type: "graph", status: "pending", progress: 0 }),
      ],
      total: 4,
    });
    render(<TaskListPage />);
    expect(await screen.findByText("文档解析")).toBeInTheDocument();
    expect(screen.getByText("信息抽取")).toBeInTheDocument();
    expect(screen.getAllByText("知识图谱").length).toBeGreaterThan(0);
    expect(screen.getByText("抽取中")).toBeInTheDocument();
    expect(screen.getByText("排队中")).toBeInTheDocument();
  });

  it("点击刷新重新加载", async () => {
    render(<TaskListPage />);
    await screen.findByText("暂无任务");
    fireEvent.click(screen.getByText("刷新"));
    await waitFor(() => expect(taskApi.getList).toHaveBeenCalledTimes(2));
  });

  it("点击详情打开抽屉", async () => {
    (taskApi.getList as any).mockResolvedValue({ items: [task({ id: "d1" })], total: 1 });
    render(<TaskListPage />);
    await screen.findByText("文档解析");
    const eyeBtn = document.querySelector(".anticon-eye");
    fireEvent.click(eyeBtn!.closest("button")!);
    expect(await screen.findByText("任务详情")).toBeInTheDocument();
    expect(screen.getByText("基本信息")).toBeInTheDocument();
  });
});
