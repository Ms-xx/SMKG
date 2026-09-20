import { describe, it, expect, beforeEach, vi } from "vitest";

vi.mock("@api/modules", () => ({
  authApi: {
    login: vi.fn(),
    getCurrentUser: vi.fn(),
  },
  permissionApi: {
    getMy: vi.fn(),
  },
}));

import { useAuthStore } from "./authStore";
import { authApi, permissionApi } from "@api/modules";

const mockLogin = authApi.login as unknown as ReturnType<typeof vi.fn>;
const mockGetCurrentUser = authApi.getCurrentUser as unknown as ReturnType<typeof vi.fn>;
const mockGetMy = permissionApi.getMy as unknown as ReturnType<typeof vi.fn>;

describe("useAuthStore", () => {
  beforeEach(() => {
    localStorage.clear();
    useAuthStore.setState({
      user: null,
      permissions: [],
      isAuthenticated: false,
      isLoading: false,
      token: null,
    });
    vi.clearAllMocks();
  });

  describe("login", () => {
    it("成功登录存储 token 并拉取用户", async () => {
      mockLogin.mockResolvedValue({
        access_token: "access-1",
        refresh_token: "refresh-1",
      });
      mockGetCurrentUser.mockResolvedValue({
        data: { id: "u1", username: "alice", role: "admin" },
      });
      mockGetMy.mockResolvedValue({ permissions: ["document:read"] });

      await useAuthStore.getState().login("alice", "secret");

      expect(localStorage.getItem("access_token")).toBe("access-1");
      expect(localStorage.getItem("refresh_token")).toBe("refresh-1");
      const state = useAuthStore.getState();
      expect(state.isAuthenticated).toBe(true);
      expect(state.token).toBe("access-1");
      expect(state.user).toEqual({ id: "u1", username: "alice", role: "admin" });
      expect(state.permissions).toEqual(["document:read"]);
      expect(state.isLoading).toBe(false);
    });

    it("无 access_token 抛错且不置为已登录", async () => {
      mockLogin.mockResolvedValue({ refresh_token: "r" });

      await expect(useAuthStore.getState().login("a", "b")).rejects.toThrow("未获取到访问令牌");
      expect(useAuthStore.getState().isAuthenticated).toBe(false);
    });
  });

  describe("logout", () => {
    it("清除所有状态与 localStorage", () => {
      localStorage.setItem("access_token", "a");
      localStorage.setItem("refresh_token", "b");
      useAuthStore.setState({
        user: { id: "u1", username: "x", role: "user" } as any,
        permissions: ["document:read"],
        isAuthenticated: true,
        token: "a",
      });

      useAuthStore.getState().logout();

      expect(localStorage.getItem("access_token")).toBeNull();
      expect(useAuthStore.getState().user).toBeNull();
      expect(useAuthStore.getState().permissions).toEqual([]);
      expect(useAuthStore.getState().isAuthenticated).toBe(false);
      expect(useAuthStore.getState().token).toBeNull();
    });
  });

  describe("fetchUser", () => {
    it("无 token 时重置状态", async () => {
      await useAuthStore.getState().fetchUser();
      expect(useAuthStore.getState().isAuthenticated).toBe(false);
      expect(mockGetCurrentUser).not.toHaveBeenCalled();
    });

    it("有 token 时拉取用户；权限接口失败时降级为空数组", async () => {
      localStorage.setItem("access_token", "tok");
      useAuthStore.setState({ token: "tok" });
      mockGetCurrentUser.mockResolvedValue({
        data: { id: "u1", username: "bob", role: "annotator" },
      });
      mockGetMy.mockRejectedValue(new Error("no permission"));

      await useAuthStore.getState().fetchUser();

      expect(useAuthStore.getState().isAuthenticated).toBe(true);
      expect((useAuthStore.getState().user as any).username).toBe("bob");
      expect(useAuthStore.getState().permissions).toEqual([]);
    });

    it("拉取用户失败时清除凭证", async () => {
      localStorage.setItem("access_token", "tok");
      useAuthStore.setState({ token: "tok" });
      mockGetCurrentUser.mockRejectedValue(new Error("401"));

      await useAuthStore.getState().fetchUser();

      expect(useAuthStore.getState().isAuthenticated).toBe(false);
      expect(localStorage.getItem("access_token")).toBeNull();
    });
  });

  describe("hasPermission", () => {
    it("admin 角色拥有所有权限", () => {
      useAuthStore.setState({
        user: { id: "u1", username: "a", role: "admin" } as any,
        permissions: [],
      });
      expect(useAuthStore.getState().hasPermission("system:user:manage")).toBe(true);
    });

    it("按权限码精确匹配", () => {
      useAuthStore.setState({
        user: { id: "u2", username: "b", role: "annotator" } as any,
        permissions: ["document:read"],
      });
      expect(useAuthStore.getState().hasPermission("document:read")).toBe(true);
      expect(useAuthStore.getState().hasPermission("document:write")).toBe(false);
    });

    it("all 通配符放行", () => {
      useAuthStore.setState({
        user: { id: "u3", username: "c", role: "reviewer" } as any,
        permissions: ["all"],
      });
      expect(useAuthStore.getState().hasPermission("task:write")).toBe(true);
    });
  });
});
