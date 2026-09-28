/* eslint-disable react-refresh/only-export-components */
import React, { useEffect } from "react";
import ReactDOM from "react-dom/client";
import { RouterProvider } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ConfigProvider } from "antd";
import zhCN from "antd/locale/zh_CN";
import { router } from "./router";
import { useAuthStore } from "./store/authStore";
import "./styles/global.css";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
});

// 应用启动引导：刷新页面时依据已存 token 重新拉取当前用户与权限码，
// 避免 user/permissions 在刷新后被清空导致侧边栏/权限路由缺项。
function AuthBootstrap() {
  const fetchUser = useAuthStore((s) => s.fetchUser);
  const token = useAuthStore((s) => s.token);

  useEffect(() => {
    if (token && !useAuthStore.getState().user) {
      fetchUser();
    }
  }, [token, fetchUser]);

  return <RouterProvider router={router} future={{ v7_startTransition: true }} />;
}

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <ConfigProvider
        locale={zhCN}
        theme={{
          token: {
            // 品牌主色：与落地页/Logo 一致的靛蓝
            colorPrimary: "#4f46e5",
            colorInfo: "#4f46e5",
            colorLink: "#4f46e5",
            colorSuccess: "#10b981",
            colorWarning: "#f59e0b",
            colorError: "#ef4444",
            borderRadius: 10,
            fontFamily:
              '-apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", "Helvetica Neue", Arial, sans-serif',
            colorBgLayout: "#f4f6fb",
          },
          components: {
            Layout: {
              headerBg: "#ffffff",
              siderBg: "#ffffff",
              bodyBg: "#f4f6fb",
              headerHeight: 60,
            },
            Menu: {
              itemSelectedColor: "#4f46e5",
              itemSelectedBg: "rgba(79,70,229,0.10)",
              itemHoverBg: "rgba(79,70,229,0.06)",
              itemBorderRadius: 8,
              itemHeight: 42,
            },
            Button: { fontWeight: 500, controlHeight: 36 },
            Card: { borderRadiusLG: 12, paddingLG: 20 },
            Table: { headerBg: "#f8fafc" },
          },
        }}
      >
        <AuthBootstrap />
      </ConfigProvider>
    </QueryClientProvider>
  </React.StrictMode>,
);
