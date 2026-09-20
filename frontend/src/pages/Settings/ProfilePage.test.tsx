import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

vi.mock("@api/modules", () => ({
  authApi: { login: vi.fn(), getCurrentUser: vi.fn() },
  permissionApi: { getMy: vi.fn() },
  userApi: { updateProfile: vi.fn(), changePassword: vi.fn() },
  documentApi: { getList: vi.fn() },
  annotationApi: { getByDocument: vi.fn() },
}));

import ProfilePage from "./ProfilePage";
import { useAuthStore } from "@store/authStore";
import { userApi, documentApi, annotationApi } from "@api/modules";

const mockUpdateProfile = userApi.updateProfile as unknown as ReturnType<typeof vi.fn>;
const mockChangePassword = userApi.changePassword as unknown as ReturnType<typeof vi.fn>;
const mockGetList = documentApi.getList as unknown as ReturnType<typeof vi.fn>;
const mockGetByDocument = annotationApi.getByDocument as unknown as ReturnType<typeof vi.fn>;

const user = {
  id: "u1",
  username: "alice",
  email: "alice@example.com",
  full_name: "Alice",
  avatar_url: null,
  role: "admin" as const,
  is_active: true,
  created_at: "2026-01-01T00:00:00",
  last_login: "2026-01-02T00:00:00",
};

describe("ProfilePage", () => {
  beforeEach(() => {
    localStorage.clear();
    vi.clearAllMocks();
    useAuthStore.setState({
      user,
      permissions: [],
      isAuthenticated: true,
      isLoading: false,
      token: "token-1",
    });
    mockUpdateProfile.mockResolvedValue({});
    mockChangePassword.mockResolvedValue({});
    mockGetList.mockResolvedValue({ items: [], total: 5 });
    mockGetByDocument.mockResolvedValue([]);
  });

  it("渲染个人信息与用户数据", () => {
    render(
      <MemoryRouter>
        <ProfilePage />
      </MemoryRouter>,
    );
    expect(screen.getByText("个人设置")).toBeInTheDocument();
    expect(screen.getByText("个人信息")).toBeInTheDocument();
    expect(screen.getByText("Alice")).toBeInTheDocument();
    expect(screen.getByText("@alice")).toBeInTheDocument();
    expect(screen.getByDisplayValue("alice")).toBeInTheDocument();
    expect(screen.getByDisplayValue("alice@example.com")).toBeInTheDocument();
  });

  it("提交个人信息表单调用 updateProfile", async () => {
    render(
      <MemoryRouter>
        <ProfilePage />
      </MemoryRouter>,
    );
    fireEvent.change(screen.getByPlaceholderText("请输入姓名"), {
      target: { value: "Alice Updated" },
    });
    fireEvent.click(screen.getByRole("button", { name: "保存修改" }));

    await waitFor(() => {
      expect(mockUpdateProfile).toHaveBeenCalledWith(
        "u1",
        expect.objectContaining({ full_name: "Alice Updated" }),
      );
    });
  });

  it("切换修改密码标签并提交调用 changePassword", async () => {
    render(
      <MemoryRouter>
        <ProfilePage />
      </MemoryRouter>,
    );
    fireEvent.click(screen.getByText("修改密码"));

    fireEvent.change(screen.getByPlaceholderText("请输入当前密码"), {
      target: { value: "oldpass" },
    });
    fireEvent.change(screen.getByPlaceholderText("请输入新密码（至少6位）"), {
      target: { value: "newpass1" },
    });
    fireEvent.change(screen.getByPlaceholderText("请再次输入新密码"), {
      target: { value: "newpass1" },
    });
    fireEvent.click(screen.getByRole("button", { name: "修改密码" }));

    await waitFor(() => {
      expect(mockChangePassword).toHaveBeenCalledWith("oldpass", "newpass1");
    });
  });

  it("账户统计标签展示各维度统计", async () => {
    render(
      <MemoryRouter>
        <ProfilePage />
      </MemoryRouter>,
    );
    fireEvent.click(screen.getByText("账户统计"));

    expect(await screen.findByText("上传文档")).toBeInTheDocument();
    expect(screen.getByText("总标注数")).toBeInTheDocument();
    expect(screen.getByText("待审核")).toBeInTheDocument();
    expect(screen.getByText("已通过")).toBeInTheDocument();
  });
});
