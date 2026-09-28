import { Layout, Menu } from "antd";
import {
  HomeOutlined,
  FileTextOutlined,
  ShareAltOutlined,
  RobotOutlined,
  ScheduleOutlined,
  ControlOutlined,
  SettingOutlined,
  AuditOutlined,
  BarChartOutlined,
  AimOutlined,
  ApartmentOutlined,
  FileSearchOutlined,
  EditOutlined,
  CopyOutlined,
} from "@ant-design/icons";
import { useNavigate, useLocation } from "react-router-dom";
import { useUIStore } from "@store/uiStore";
import { useAuthStore } from "@store/authStore";
import BrandLogo from "@components/BrandLogo";

const { Sider } = Layout;

export default function AppSidebar() {
  const navigate = useNavigate();
  const location = useLocation();
  const { sidebarCollapsed } = useUIStore();
  const user = useAuthStore((s) => s.user);
  const permissions = useAuthStore((s) => s.permissions);

  const hasPerm = (perm: string) =>
    user?.role === "admin" || permissions.includes("all") || permissions.includes(perm);

  const menuItems = [
    { key: "/home", icon: <HomeOutlined />, label: "主页" },
    ...(hasPerm("document:read")
      ? [{ key: "/documents", icon: <FileTextOutlined />, label: "文档管理" }]
      : []),
    ...(hasPerm("annotation:read")
      ? [{ key: "/active-learning", icon: <AimOutlined />, label: "优先标注" }]
      : []),
    ...(hasPerm("document:read")
      ? [
          {
            key: "/knowledge-graph-menu",
            icon: <ShareAltOutlined />,
            label: "知识图谱",
            children: [
              { key: "/knowledge-graph", label: "图谱探索", icon: <ShareAltOutlined /> },
              { key: "/knowledge-graph/rag", label: "GraphRAG 问答", icon: <RobotOutlined /> },
              { key: "/multi-agent", label: "多 Agent 协作", icon: <ApartmentOutlined /> },
            ],
          },
        ]
      : []),
    ...(hasPerm("document:read")
      ? [
          {
            key: "/research-tools-menu",
            icon: <FileSearchOutlined />,
            label: "科研工具",
            children: [
              { key: "/citation-graph", label: "引用图谱", icon: <ApartmentOutlined /> },
              { key: "/paper-retrieval", label: "论文检索推荐", icon: <FileSearchOutlined /> },
              { key: "/writing-assistant", label: "写作辅助", icon: <EditOutlined /> },
              { key: "/deduplication", label: "语义去重", icon: <CopyOutlined /> },
            ],
          },
        ]
      : []),
    ...(hasPerm("task:read")
      ? [{ key: "/tasks", icon: <ScheduleOutlined />, label: "任务管理" }]
      : []),
    ...(hasPerm("system:audit:read")
      ? [{ key: "/operation-logs", icon: <AuditOutlined />, label: "操作日志" }]
      : []),
    { key: "/statistics", icon: <BarChartOutlined />, label: "工作量统计" },
    ...(hasPerm("system:role:manage")
      ? [{ key: "/settings/roles", icon: <ControlOutlined />, label: "角色权限" }]
      : []),
    { key: "/settings/profile", icon: <SettingOutlined />, label: "系统设置" },
  ];

  return (
    <Sider
      collapsible
      collapsed={sidebarCollapsed}
      onCollapse={() => useUIStore.getState().toggleSidebar()}
      theme="light"
    >
      <div
        style={{
          height: 40,
          margin: "16px 16px 8px",
          display: "flex",
          alignItems: "center",
          justifyContent: sidebarCollapsed ? "center" : "flex-start",
          gap: 10,
          overflow: "hidden",
        }}
      >
        <BrandLogo size={30} />
        {!sidebarCollapsed && (
          <span
            style={{ fontSize: 16, fontWeight: 700, color: "#0f172a", letterSpacing: "0.02em" }}
          >
            SDP
          </span>
        )}
      </div>
      <Menu
        mode="inline"
        selectedKeys={[location.pathname.split("/").slice(0, 3).join("/")]}
        items={menuItems}
        onClick={({ key }) => navigate(key)}
      />
    </Sider>
  );
}
