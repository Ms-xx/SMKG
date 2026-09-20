import { useState, useEffect } from "react";
import {
  Card,
  Tabs,
  Form,
  Input,
  Button,
  Avatar,
  message,
  Statistic,
  Row,
  Col,
  Descriptions,
  Divider,
  Spin,
} from "antd";
import { UserOutlined, LockOutlined, BarChartOutlined } from "@ant-design/icons";
import { useAuthStore } from "@store/authStore";
import { userApi, documentApi, annotationApi } from "@api/modules";
import type { User } from "@/types";
import dayjs from "dayjs";

const roleLabels: Record<string, string> = {
  admin: "管理员",
  annotator: "标注员",
  reviewer: "审核员",
  user: "普通用户",
};

function ProfileInfoTab({ user, onUpdated }: { user: User; onUpdated: () => void }) {
  const [form] = Form.useForm();
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    form.setFieldsValue({
      full_name: user.full_name || "",
      email: user.email,
      avatar_url: user.avatar_url || "",
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user.id]);

  const handleSave = async (values: {
    full_name?: string;
    email?: string;
    avatar_url?: string;
  }) => {
    setSaving(true);
    try {
      await userApi.updateProfile(user.id, values);
      message.success("保存成功");
      onUpdated();
    } catch {
      message.error("保存失败，请重试");
    } finally {
      setSaving(false);
    }
  };

  return (
    <Card>
      <div style={{ display: "flex", alignItems: "center", gap: 24, marginBottom: 32 }}>
        <Avatar
          size={80}
          src={user.avatar_url}
          icon={<UserOutlined />}
          style={{ backgroundColor: "#1890ff" }}
        />
        <div>
          <div style={{ fontSize: 18, fontWeight: 600 }}>{user.full_name || user.username}</div>
          <div style={{ color: "#888", marginTop: 4 }}>@{user.username}</div>
          <div style={{ marginTop: 6 }}>
            <span
              style={{
                background:
                  user.role === "admin"
                    ? "#ff4d4f"
                    : user.role === "reviewer"
                      ? "#722ed1"
                      : user.role === "annotator"
                        ? "#1890ff"
                        : "#52c41a",
                color: "#fff",
                padding: "2px 10px",
                borderRadius: 10,
                fontSize: 12,
              }}
            >
              {roleLabels[user.role] || user.role}
            </span>
          </div>
        </div>
      </div>
      <Divider />
      <Form form={form} layout="vertical" onFinish={handleSave} style={{ maxWidth: 480 }}>
        <Form.Item label="用户名">
          <Input disabled value={user.username} />
        </Form.Item>
        <Form.Item
          label="姓名"
          name="full_name"
          rules={[{ max: 50, message: "姓名不能超过50个字符" }]}
        >
          <Input placeholder="请输入姓名" />
        </Form.Item>
        <Form.Item
          label="邮箱"
          name="email"
          rules={[
            { required: true, message: "请输入邮箱" },
            { type: "email", message: "请输入正确的邮箱格式" },
          ]}
        >
          <Input placeholder="请输入邮箱" />
        </Form.Item>
        <Form.Item label="头像 URL" name="avatar_url">
          <Input placeholder="https://example.com/avatar.jpg" />
        </Form.Item>
        <Form.Item>
          <Button type="primary" htmlType="submit" loading={saving}>
            保存修改
          </Button>
        </Form.Item>
      </Form>
    </Card>
  );
}

function PasswordTab() {
  const [form] = Form.useForm();
  const [loading, setLoading] = useState(false);

  const handleChange = async (values: {
    old_password: string;
    new_password: string;
    confirm_password: string;
  }) => {
    if (values.new_password !== values.confirm_password) {
      message.error("两次输入的新密码不一致");
      return;
    }
    setLoading(true);
    try {
      await userApi.changePassword(values.old_password, values.new_password);
      message.success("密码修改成功");
      form.resetFields();
    } catch (e: any) {
      message.error(e?.response?.data?.detail || "修改失败，请检查原密码");
    } finally {
      setLoading(false);
    }
  };

  return (
    <Card title="修改密码" style={{ maxWidth: 480 }}>
      <Form form={form} layout="vertical" onFinish={handleChange}>
        <Form.Item
          label="原密码"
          name="old_password"
          rules={[{ required: true, message: "请输入原密码" }]}
        >
          <Input.Password placeholder="请输入当前密码" />
        </Form.Item>
        <Form.Item
          label="新密码"
          name="new_password"
          rules={[
            { required: true, message: "请输入新密码" },
            { min: 6, message: "新密码长度不能少于6位" },
          ]}
        >
          <Input.Password placeholder="请输入新密码（至少6位）" />
        </Form.Item>
        <Form.Item
          label="确认新密码"
          name="confirm_password"
          rules={[
            { required: true, message: "请确认新密码" },
            ({ getFieldValue }) => ({
              validator(_, value) {
                if (!value || getFieldValue("new_password") === value) return Promise.resolve();
                return Promise.reject(new Error("两次输入的密码不一致"));
              },
            }),
          ]}
        >
          <Input.Password placeholder="请再次输入新密码" />
        </Form.Item>
        <Form.Item>
          <Button type="primary" htmlType="submit" loading={loading}>
            修改密码
          </Button>
        </Form.Item>
      </Form>
    </Card>
  );
}

interface Stats {
  documentCount: number;
  annotationCount: number;
  pendingAnnotationCount: number;
  approvedAnnotationCount: number;
}

function StatsTab({ user }: { user: User }) {
  const [stats, setStats] = useState<Stats>({
    documentCount: 0,
    annotationCount: 0,
    pendingAnnotationCount: 0,
    approvedAnnotationCount: 0,
  });
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    documentApi.getList({ page: 1, page_size: 1 }).then((res: any) => {
      const data = res.data || res;
      setStats((prev) => ({ ...prev, documentCount: data.total || 0 }));
    });

    documentApi
      .getList({ page: 1, page_size: 100 })
      .then(async (res: any) => {
        const docs = (res.data || res).items || [];
        let total = 0,
          pending = 0,
          approved = 0;
        for (const doc of docs) {
          try {
            const annRes = await annotationApi.getByDocument(doc.id);
            const anns = Array.isArray(annRes.data) ? annRes.data : annRes;
            total += anns.length;
            pending += anns.filter(
              (a: any) => a.status === "submitted" || a.status === "draft",
            ).length;
            approved += anns.filter((a: any) => a.status === "approved").length;
          } catch {
            /* skip */
          }
        }
        setStats((prev) => ({
          ...prev,
          annotationCount: total,
          pendingAnnotationCount: pending,
          approvedAnnotationCount: approved,
        }));
      })
      .finally(() => setLoading(false));
  }, []);

  return (
    <Card loading={loading}>
      <Row gutter={24}>
        <Col span={6}>
          <Statistic title="上传文档" value={stats.documentCount} />
        </Col>
        <Col span={6}>
          <Statistic title="总标注数" value={stats.annotationCount} />
        </Col>
        <Col span={6}>
          <Statistic
            title="待审核"
            value={stats.pendingAnnotationCount}
            valueStyle={{ color: "#faad14" }}
          />
        </Col>
        <Col span={6}>
          <Statistic
            title="已通过"
            value={stats.approvedAnnotationCount}
            valueStyle={{ color: "#52c41a" }}
          />
        </Col>
      </Row>
      <Divider />
      <Descriptions column={2} bordered size="small">
        <Descriptions.Item label="账号创建时间">
          {user.created_at ? dayjs(user.created_at).format("YYYY-MM-DD HH:mm") : "-"}
        </Descriptions.Item>
        <Descriptions.Item label="最后登录">
          {user.last_login ? dayjs(user.last_login).format("YYYY-MM-DD HH:mm") : "-"}
        </Descriptions.Item>
        <Descriptions.Item label="账户状态">
          <span style={{ color: user.is_active ? "#52c41a" : "#ff4d4f" }}>
            {user.is_active ? "正常" : "已禁用"}
          </span>
        </Descriptions.Item>
        <Descriptions.Item label="用户角色">{roleLabels[user.role] || user.role}</Descriptions.Item>
      </Descriptions>
    </Card>
  );
}

export default function ProfilePage() {
  const { user, fetchUser } = useAuthStore();

  useEffect(() => {
    if (!user) fetchUser();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  if (!user) return <Spin style={{ display: "block", margin: "60px auto" }} />;

  const items = [
    {
      key: "profile",
      label: (
        <span>
          <UserOutlined /> 个人信息
        </span>
      ),
      children: <ProfileInfoTab user={user} onUpdated={fetchUser} />,
    },
    {
      key: "password",
      label: (
        <span>
          <LockOutlined /> 修改密码
        </span>
      ),
      children: <PasswordTab />,
    },
    {
      key: "stats",
      label: (
        <span>
          <BarChartOutlined /> 账户统计
        </span>
      ),
      children: <StatsTab user={user} />,
    },
  ];

  return (
    <div>
      <h2 style={{ marginBottom: 16 }}>个人设置</h2>
      <Tabs defaultActiveKey="profile" items={items} />
    </div>
  );
}
