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
        <Content style={{ margin: "24px 16px", padding: 24, background: "#fff" }}>
          <Outlet />
        </Content>
      </Layout>
    </Layout>
  );
}
