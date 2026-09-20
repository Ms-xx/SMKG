import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { useAuthStore } from "@store/authStore";
import { authGuard, roleGuard, permGuard } from "./guards";

const resetAuth = () => {
  useAuthStore.setState({
    user: null,
    permissions: [],
    isAuthenticated: false,
    isLoading: false,
    token: null,
  });
};

const adminUser = { id: "u1", username: "a", role: "admin" } as any;
const annotatorUser = { id: "u2", username: "b", role: "annotator" } as any;

describe("路由守卫", () => {
  it("authGuard 未登录时跳转 /login", () => {
    resetAuth();
    render(<MemoryRouter>{authGuard(<div>protected</div>)}</MemoryRouter>);
    expect(screen.queryByText("protected")).toBeNull();
  });

  it("authGuard 已登录时渲染子组件", () => {
    resetAuth();
    useAuthStore.setState({ isAuthenticated: true });
    render(<MemoryRouter>{authGuard(<div>protected</div>)}</MemoryRouter>);
    expect(screen.getByText("protected")).toBeInTheDocument();
  });

  it("roleGuard 无匹配角色时跳转 /dashboard", () => {
    resetAuth();
    useAuthStore.setState({ user: annotatorUser });
    render(<MemoryRouter>{roleGuard(<div>admin-only</div>, ["admin"])}</MemoryRouter>);
    expect(screen.queryByText("admin-only")).toBeNull();
  });

  it("roleGuard 匹配角色时渲染", () => {
    resetAuth();
    useAuthStore.setState({ user: adminUser });
    render(<MemoryRouter>{roleGuard(<div>admin-only</div>, ["admin"])}</MemoryRouter>);
    expect(screen.getByText("admin-only")).toBeInTheDocument();
  });

  it("permGuard 未登录时跳转 /login", () => {
    resetAuth();
    render(<MemoryRouter>{permGuard(<div>perm-target</div>, "system:audit:read")}</MemoryRouter>);
    expect(screen.queryByText("perm-target")).toBeNull();
  });

  it("permGuard admin 角色直接放行", () => {
    resetAuth();
    useAuthStore.setState({ isAuthenticated: true, user: adminUser, permissions: [] });
    render(<MemoryRouter>{permGuard(<div>perm-target</div>, "system:audit:read")}</MemoryRouter>);
    expect(screen.getByText("perm-target")).toBeInTheDocument();
  });

  it("permGuard 拥有权限时渲染", () => {
    resetAuth();
    useAuthStore.setState({
      isAuthenticated: true,
      user: annotatorUser,
      permissions: ["document:read"],
    });
    render(<MemoryRouter>{permGuard(<div>perm-target</div>, "document:read")}</MemoryRouter>);
    expect(screen.getByText("perm-target")).toBeInTheDocument();
  });

  it("permGuard 缺少权限时跳转 /dashboard", () => {
    resetAuth();
    useAuthStore.setState({
      isAuthenticated: true,
      user: annotatorUser,
      permissions: ["document:read"],
    });
    render(<MemoryRouter>{permGuard(<div>perm-target</div>, "system:audit:read")}</MemoryRouter>);
    expect(screen.queryByText("perm-target")).toBeNull();
  });

  it("permGuard 用户尚未加载时返回空", () => {
    resetAuth();
    useAuthStore.setState({ isAuthenticated: true, user: null });
    render(<MemoryRouter>{permGuard(<div>perm-target</div>, "document:read")}</MemoryRouter>);
    expect(screen.queryByText("perm-target")).toBeNull();
  });
});
