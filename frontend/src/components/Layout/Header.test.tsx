import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import AppHeader from "./Header";

const mockList = vi.fn();
const mockMarkAllRead = vi.fn();
const mockLogout = vi.fn();
const mockNavigate = vi.fn();

vi.mock("@store/authStore", () => ({
  useAuthStore: vi.fn(() => ({
    user: { id: "u1", username: "alice", full_name: "Alice" },
    logout: mockLogout,
  })),
}));
vi.mock("@api/modules", () => ({
  notificationApi: {
    list: (...args: any[]) => mockList(...args),
    markAllRead: (...args: any[]) => mockMarkAllRead(...args),
  },
}));
vi.mock("react-router-dom", () => ({
  useNavigate: () => mockNavigate,
}));

describe("AppHeader", () => {
  beforeEach(() => {
    mockList.mockReset().mockResolvedValue({ items: [], unread_count: 0 });
    mockMarkAllRead.mockReset().mockResolvedValue({});
    mockLogout.mockReset();
    mockNavigate.mockReset();
  });

  it("渲染平台标题与用户名", async () => {
    render(<AppHeader />);
    expect(screen.getByText("科学文献智能解析平台")).toBeInTheDocument();
    await waitFor(() => expect(mockList).toHaveBeenCalled());
    expect(screen.getByText("Alice")).toBeInTheDocument();
  });

  it("有未读通知时展示未读徽标", async () => {
    mockList.mockResolvedValue({
      items: [
        {
          id: "n1",
          title: "通知标题",
          content: "内容",
          is_read: false,
          created_at: "2026-01-01T00:00:00Z",
        },
      ],
      unread_count: 1,
    });
    render(<AppHeader />);
    await waitFor(() => expect(mockList).toHaveBeenCalled());
    await waitFor(() => expect(document.querySelector(".ant-badge-count")?.textContent).toBe("1"));
  });
});
