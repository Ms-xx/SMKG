import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

vi.mock("@api/modules", () => ({
  operationLogApi: { getList: vi.fn() },
}));

import OperationLogsPage from "./OperationLogsPage";
import { operationLogApi } from "@api/modules";

const mockGetList = operationLogApi.getList as unknown as ReturnType<typeof vi.fn>;

const samples = [
  {
    id: "1",
    user_id: "u1",
    action: "create",
    resource_type: "annotation",
    resource_id: "a1",
    ip_address: "1.2.3.4",
    created_at: "2026-01-01T00:00:00",
    details: { note: "hello" },
  },
];

describe("OperationLogsPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockGetList.mockResolvedValue({ items: [], total: 0 });
  });

  it("渲染标题、副标题与刷新按钮", () => {
    render(
      <MemoryRouter>
        <OperationLogsPage />
      </MemoryRouter>,
    );
    expect(screen.getByText("操作日志")).toBeInTheDocument();
    expect(screen.getByText("记录所有标注、修改与审核操作的审计日志")).toBeInTheDocument();
    expect(screen.getByText("刷新")).toBeInTheDocument();
  });

  it("加载并展示日志列表数据", async () => {
    mockGetList.mockResolvedValue({ items: samples, total: 1 });
    render(
      <MemoryRouter>
        <OperationLogsPage />
      </MemoryRouter>,
    );
    expect(await screen.findByText("u1")).toBeInTheDocument();
    expect(screen.getByText("创建标注")).toBeInTheDocument();
    expect(screen.getByText("标注")).toBeInTheDocument();
    expect(screen.getByText("1.2.3.4")).toBeInTheDocument();
    expect(mockGetList).toHaveBeenCalled();
  });

  it("无数据时展示空态", async () => {
    render(
      <MemoryRouter>
        <OperationLogsPage />
      </MemoryRouter>,
    );
    expect(await screen.findByText("暂无操作日志")).toBeInTheDocument();
  });

  it("点击详情按钮打开操作日志详情抽屉", async () => {
    mockGetList.mockResolvedValue({ items: samples, total: 1 });
    const { container } = render(
      <MemoryRouter>
        <OperationLogsPage />
      </MemoryRouter>,
    );
    await screen.findByText("u1");

    const detailButton = container.querySelector(".ant-table-tbody .ant-btn") as HTMLElement;
    fireEvent.click(detailButton);

    expect(await screen.findByText("操作日志详情")).toBeInTheDocument();
    expect(screen.getByText("日志ID")).toBeInTheDocument();
    expect(screen.getByText("操作详情")).toBeInTheDocument();
  });
});
