import { useEffect, useState } from "react";
import {
  Layout,
  Avatar,
  Dropdown,
  Badge,
  Popover,
  List,
  Typography,
  Button,
  Empty,
  message,
} from "antd";
import { UserOutlined, LogoutOutlined, ControlOutlined, BellOutlined } from "@ant-design/icons";
import { useAuthStore } from "@store/authStore";
import { useNavigate } from "react-router-dom";
import { notificationApi } from "@api/modules";
import type { AppNotification } from "@/types";
import dayjs from "dayjs";

const { Header: AntHeader } = Layout;
const { Text } = Typography;

export default function AppHeader() {
  const { user, logout } = useAuthStore();
  const navigate = useNavigate();
  const [unread, setUnread] = useState(0);
  const [notifications, setNotifications] = useState<AppNotification[]>([]);

  const refreshNotifications = () => {
    notificationApi
      .list({ page: 1, page_size: 10 })
      .then((res: any) => {
        const data = res || {};
        setNotifications(data.items || []);
        setUnread(data.unread_count || 0);
      })
      .catch(() => {});
  };

  useEffect(() => {
    refreshNotifications();
  }, []);

  const markAllRead = () => {
    notificationApi
      .markAllRead()
      .then(() => {
        message.success("已全部标记为已读");
        refreshNotifications();
      })
      .catch(() => message.error("操作失败"));
  };

  const userMenuItems = [
    {
      key: "profile",
      icon: <ControlOutlined />,
      label: "个人设置",
      onClick: () => navigate("/settings/profile"),
    },
    {
      key: "logout",
      icon: <LogoutOutlined />,
      label: "退出登录",
      onClick: () => {
        logout();
        navigate("/login");
      },
    },
  ];

  const notifyContent = (
    <div style={{ width: 320 }}>
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          marginBottom: 8,
        }}
      >
        <Text strong>通知</Text>
        {unread > 0 && (
          <Button type="link" size="small" onClick={markAllRead}>
            全部已读
          </Button>
        )}
      </div>
      {notifications.length === 0 ? (
        <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无通知" />
      ) : (
        <List
          size="small"
          dataSource={notifications}
          renderItem={(n) => (
            <List.Item style={{ opacity: n.is_read ? 0.6 : 1 }}>
              <div>
                <div>
                  <Text strong={!n.is_read}>{n.title || n.type}</Text>
                </div>
                <Text type="secondary" style={{ fontSize: 12 }}>
                  {n.content}
                </Text>
                <div>
                  <Text type="secondary" style={{ fontSize: 11 }}>
                    {n.sender_name ? `${n.sender_name} · ` : ""}
                    {dayjs(n.created_at).format("MM-DD HH:mm")}
                  </Text>
                </div>
              </div>
            </List.Item>
          )}
        />
      )}
    </div>
  );

  return (
    <AntHeader
      style={{
        padding: "0 24px",
        background: "#fff",
        display: "flex",
        justifyContent: "space-between",
        alignItems: "center",
      }}
    >
      <div style={{ fontSize: 18, fontWeight: 600 }}>科学文献智能解析平台</div>
      <div style={{ display: "flex", alignItems: "center", gap: 20 }}>
        <Popover
          content={notifyContent}
          trigger="click"
          placement="bottomRight"
          onOpenChange={(open) => open && refreshNotifications()}
        >
          <Badge count={unread} size="small" offset={[-2, 2]}>
            <BellOutlined style={{ fontSize: 18, cursor: "pointer" }} />
          </Badge>
        </Popover>
        <Dropdown menu={{ items: userMenuItems }} placement="bottomRight">
          <div style={{ cursor: "pointer", display: "flex", alignItems: "center", gap: 8 }}>
            <Avatar icon={<UserOutlined />} src={user?.avatar_url} />
            <span>{user?.full_name || user?.username}</span>
          </div>
        </Dropdown>
      </div>
    </AntHeader>
  );
}
