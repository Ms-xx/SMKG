import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

vi.mock("@api/modules", () => ({
  permissionApi: {
    getRoles: vi.fn(),
    getDefinitions: vi.fn(),
    updateRolePermissions: vi.fn(),
  },
}));

import RolePermissionPage from "./RolePermissionPage";
import { permissionApi } from "@api/modules";

const mockGetRoles = permissionApi.getRoles as unknown as ReturnType<typeof vi.fn>;
const mockGetDefinitions = permissionApi.getDefinitions as unknown as ReturnType<typeof vi.fn>;
const mockUpdateRolePermissions = permissionApi.updateRolePermissions as unknown as ReturnType<
  typeof vi.fn
>;

const roles = [
  { id: "r1", name: "admin", description: "管理员", permissions: ["all"] },
  { id: "r2", name: "reviewer", description: "负责审核", permissions: ["document:read"] },
];

const definitions = [
  { code: "document:read", description: "查看文档" },
  { code: "document:write", description: "编辑文档" },
];

describe("RolePermissionPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockGetRoles.mockResolvedValue({ items: roles, total: 2 });
    mockGetDefinitions.mockResolvedValue({ items: definitions, total: 2 });
    mockUpdateRolePermissions.mockResolvedValue({});
  });

  it("渲染标题与刷新按钮", () => {
    render(
      <MemoryRouter>
        <RolePermissionPage />
      </MemoryRouter>,
    );
    expect(screen.getByText("角色权限管理")).toBeInTheDocument();
    expect(screen.getByText("刷新")).toBeInTheDocument();
  });

  it("加载并展示角色与权限码", async () => {
    render(
      <MemoryRouter>
        <RolePermissionPage />
      </MemoryRouter>,
    );
    expect(await screen.findByText("系统管理员")).toBeInTheDocument();
    expect(screen.getByText("审核员")).toBeInTheDocument();
    expect(screen.getByText("document:read")).toBeInTheDocument();
    expect(screen.getByText("负责审核")).toBeInTheDocument();
  });

  it("编辑非管理员角色并保存权限", async () => {
    render(
      <MemoryRouter>
        <RolePermissionPage />
      </MemoryRouter>,
    );
    await screen.findByText("系统管理员");

    const editButtons = screen.getAllByRole("button", { name: /编辑/ });
    fireEvent.click(editButtons[1]);

    expect(await screen.findByText(/编辑权限：审核员/)).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /保\s*存/ }));

    await waitFor(() => {
      expect(mockUpdateRolePermissions).toHaveBeenCalledWith("reviewer", ["document:read"]);
    });
  });
});
