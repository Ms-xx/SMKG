import { describe, it, expect, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import AppSidebar from "./Sidebar";
import { useAuthStore } from "@store/authStore";
import { useUIStore } from "@store/uiStore";

const reset = () => {
  useAuthStore.setState({ user: null, permissions: [], isAuthenticated: false });
  useUIStore.setState({ sidebarCollapsed: false });
};

describe("AppSidebar 菜单权限", () => {
  beforeEach(reset);

  it("管理员显示全部菜单", () => {
    useAuthStore.setState({ user: { id: "u1", username: "a", role: "admin" } as any });
    render(
      <MemoryRouter>
        <AppSidebar />
      </MemoryRouter>,
    );
    for (const t of ["主页", "文档管理", "任务管理", "角色权限", "系统设置"]) {
      expect(screen.getByText(t)).toBeInTheDocument();
    }
  });

  it("无权限普通用户隐藏受控菜单", () => {
    useAuthStore.setState({
      user: { id: "u2", username: "b", role: "annotator" } as any,
      permissions: [],
    });
    render(
      <MemoryRouter>
        <AppSidebar />
      </MemoryRouter>,
    );
    expect(screen.getByText("主页")).toBeInTheDocument();
    expect(screen.queryByText("文档管理")).toBeNull();
    expect(screen.queryByText("任务管理")).toBeNull();
    expect(screen.queryByText("角色权限")).toBeNull();
    expect(screen.getByText("系统设置")).toBeInTheDocument();
  });

  it("按权限码显示对应菜单", () => {
    useAuthStore.setState({
      user: { id: "u3", username: "c", role: "annotator" } as any,
      permissions: ["document:read"],
    });
    render(
      <MemoryRouter>
        <AppSidebar />
      </MemoryRouter>,
    );
    expect(screen.getByText("文档管理")).toBeInTheDocument();
    expect(screen.queryByText("任务管理")).toBeNull();
  });
});
