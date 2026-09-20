import { create } from "zustand";
import { authApi, permissionApi } from "@api/modules";
import type { User } from "@/types";

interface AuthState {
  user: User | null;
  permissions: string[];
  isAuthenticated: boolean;
  isLoading: boolean;
  token: string | null;
  login: (username: string, password: string) => Promise<void>;
  logout: () => void;
  fetchUser: () => Promise<void>;
  hasPermission: (permission: string) => boolean;
}

export const useAuthStore = create<AuthState>()((set, get) => ({
  user: null,
  permissions: [],
  isAuthenticated: false,
  isLoading: false,
  token: null,

  login: async (username: string, password: string) => {
    set({ isLoading: true });
    try {
      const data = await authApi.login(username, password);
      const tokenData = data.access_token ? data : data.data || data;
      const accessToken = tokenData.access_token;
      const refreshToken = tokenData.refresh_token;
      if (!accessToken) {
        throw new Error("登录失败：未获取到访问令牌");
      }
      // 存储到 localStorage
      localStorage.setItem("access_token", accessToken);
      localStorage.setItem("refresh_token", refreshToken || "");
      set({ isAuthenticated: true, token: accessToken });
      // 拉取当前用户信息与权限码
      await get().fetchUser();
    } finally {
      set({ isLoading: false });
    }
  },

  logout: () => {
    localStorage.removeItem("access_token");
    localStorage.removeItem("refresh_token");
    set({ user: null, permissions: [], isAuthenticated: false, token: null });
  },

  fetchUser: async () => {
    const token = get().token || localStorage.getItem("access_token");
    if (!token) {
      set({ user: null, permissions: [], isAuthenticated: false });
      return;
    }
    try {
      const user = await authApi.getCurrentUser();
      set({ user, isAuthenticated: true });
      // 拉取角色权限码，供前端菜单/路由守卫做细粒度权限控制
      try {
        const res: any = await permissionApi.getMy();
        const permissions = res?.permissions || [];
        set({ permissions });
      } catch {
        set({ permissions: [] });
      }
    } catch {
      localStorage.removeItem("access_token");
      localStorage.removeItem("refresh_token");
      set({ user: null, permissions: [], isAuthenticated: false, token: null });
    }
  },

  hasPermission: (permission: string) => {
    const { user, permissions } = get();
    if (user?.role === "admin") return true;
    return permissions.includes("all") || permissions.includes(permission);
  },
}));

// 初始化时检查 token
const initToken = localStorage.getItem("access_token");
if (initToken) {
  useAuthStore.setState({ token: initToken, isAuthenticated: true });
}
