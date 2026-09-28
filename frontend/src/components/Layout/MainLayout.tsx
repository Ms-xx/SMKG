import { Layout } from "antd";
import { Outlet } from "react-router-dom";
import AppHeader from "./Header";
import AppSidebar from "./Sidebar";

const { Content } = Layout;

export default function MainLayout() {
  return (
    <Layout style={{ minHeight: "100vh" }}>
      <AppSidebar />
      <Layout>
        <AppHeader />
        <Content
          style={{
            margin: 16,
            padding: 24,
            background: "var(--color-bg-container)",
            borderRadius: 12,
            minHeight: "calc(100vh - 60px - 32px)",
          }}
        >
          <Outlet />
        </Content>
      </Layout>
    </Layout>
  );
}
