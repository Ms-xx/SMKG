import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

vi.mock("@api/modules", () => ({
  statisticsApi: { getPersonal: vi.fn(), getTeam: vi.fn() },
}));

import WorkloadPage from "./WorkloadPage";
import { statisticsApi } from "@api/modules";

const mockGetPersonal = statisticsApi.getPersonal as unknown as ReturnType<typeof vi.fn>;
const mockGetTeam = statisticsApi.getTeam as unknown as ReturnType<typeof vi.fn>;

const personal = {
  user_id: "u1",
  username: "alice",
  full_name: "Alice",
  role: "annotator",
  annotation_total: 10,
  annotation_approved: 8,
  annotation_rejected: 1,
  annotation_pending: 1,
  annotation_draft: 0,
  accuracy_rate: 80,
  task_total: 7,
  task_completed: 5,
  task_in_progress: 2,
  task_failed: 0,
};

const team = [
  {
    user_id: "u1",
    username: "alice",
    full_name: "Alice",
    role: "annotator",
    annotation_total: 10,
    annotation_approved: 8,
    annotation_rejected: 1,
    annotation_pending: 1,
    accuracy_rate: 80,
    task_completed: 5,
    task_in_progress: 2,
    task_failed: 0,
  },
];

describe("WorkloadPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockGetPersonal.mockResolvedValue(personal);
    mockGetTeam.mockResolvedValue({ items: team, total_users: 1 });
  });

  it("渲染标题与各区块", () => {
    render(
      <MemoryRouter>
        <WorkloadPage />
      </MemoryRouter>,
    );
    expect(screen.getByText("工作量统计")).toBeInTheDocument();
    expect(screen.getByText("我的工作量")).toBeInTheDocument();
    expect(screen.getByText("团队看板")).toBeInTheDocument();
    expect(screen.getByText("我的标注准确率")).toBeInTheDocument();
  });

  it("加载并展示个人统计卡片与团队看板", async () => {
    render(
      <MemoryRouter>
        <WorkloadPage />
      </MemoryRouter>,
    );
    expect(await screen.findByText("Alice")).toBeInTheDocument();
    expect(screen.getAllByText("标注总数").length).toBeGreaterThan(0);
    expect(screen.getByText("审核通过")).toBeInTheDocument();
    expect(screen.getAllByText("80%").length).toBeGreaterThan(0);
    expect(screen.getByText("标注员")).toBeInTheDocument();
  });

  it("无团队数据时展示空态", async () => {
    mockGetPersonal.mockResolvedValue(null);
    mockGetTeam.mockResolvedValue({ items: [], total_users: 0 });
    render(
      <MemoryRouter>
        <WorkloadPage />
      </MemoryRouter>,
    );
    expect(await screen.findByText("暂无团队成员数据")).toBeInTheDocument();
    expect(screen.getAllByText("-").length).toBeGreaterThan(0);
  });
});
