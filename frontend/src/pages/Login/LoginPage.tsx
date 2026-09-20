import { Form, Input, Button, Card, Modal, message } from "antd";
import { UserOutlined, LockOutlined, MailOutlined } from "@ant-design/icons";
import { useAuthStore } from "@store/authStore";
import { useNavigate } from "react-router-dom";
import { useState } from "react";
import { authApi } from "@api/modules";

export default function LoginPage() {
  const [form] = Form.useForm();
  const [registerForm] = Form.useForm();
  const { login, isLoading } = useAuthStore();
  const navigate = useNavigate();
  const [error, setError] = useState("");
  const [registerVisible, setRegisterVisible] = useState(false);
  const [registerLoading, setRegisterLoading] = useState(false);

  const handleSubmit = async (values: { username: string; password: string }) => {
    try {
      setError("");
      await login(values.username, values.password);
      navigate("/dashboard");
    } catch {
      setError("用户名或密码错误");
    }
  };

  const handleRegister = async (values: {
    username: string;
    email: string;
    password: string;
    full_name?: string;
  }) => {
    try {
      setRegisterLoading(true);
      await authApi.register(values);
      message.success("注册成功，请登录");
      setRegisterVisible(false);
      registerForm.resetFields();
      // 自动填充用户名
      form.setFieldsValue({ username: values.username });
    } catch (e: any) {
      const errMsg = e?.response?.data?.detail || "注册失败，请重试";
      message.error(errMsg);
    } finally {
      setRegisterLoading(false);
    }
  };

  return (
    <div
      style={{
        display: "flex",
        justifyContent: "center",
        alignItems: "center",
        minHeight: "100vh",
        background: "#f0f2f5",
      }}
    >
      <Card title="科学文献智能解析平台" style={{ width: 400 }}>
        <Form form={form} onFinish={handleSubmit}>
          {error && (
            <div style={{ color: "red", marginBottom: 16, textAlign: "center" }}>{error}</div>
          )}
          <Form.Item name="username" rules={[{ required: true, message: "请输入用户名" }]}>
            <Input prefix={<UserOutlined />} placeholder="用户名" size="large" />
          </Form.Item>
          <Form.Item name="password" rules={[{ required: true, message: "请输入密码" }]}>
            <Input.Password prefix={<LockOutlined />} placeholder="密码" size="large" />
          </Form.Item>
          <Form.Item>
            <Button type="primary" htmlType="submit" loading={isLoading} block size="large">
              登录
            </Button>
          </Form.Item>
          <Form.Item style={{ marginBottom: 0 }}>
            <Button type="link" block onClick={() => setRegisterVisible(true)}>
              没有账号？立即注册
            </Button>
          </Form.Item>
        </Form>
      </Card>

      {/* 注册弹窗 */}
      <Modal
        title="用户注册"
        open={registerVisible}
        onCancel={() => {
          setRegisterVisible(false);
          registerForm.resetFields();
        }}
        footer={null}
        destroyOnHidden
      >
        <Form form={registerForm} onFinish={handleRegister} layout="vertical">
          <Form.Item
            name="username"
            label="用户名"
            rules={[
              { required: true, message: "请输入用户名" },
              { min: 3, message: "用户名至少3个字符" },
            ]}
          >
            <Input prefix={<UserOutlined />} placeholder="请输入用户名" />
          </Form.Item>
          <Form.Item
            name="email"
            label="邮箱"
            rules={[
              { required: true, message: "请输入邮箱" },
              { type: "email", message: "请输入有效的邮箱地址" },
            ]}
          >
            <Input prefix={<MailOutlined />} placeholder="请输入邮箱" />
          </Form.Item>
          <Form.Item name="full_name" label="姓名（可选）">
            <Input placeholder="请输入姓名（可选）" />
          </Form.Item>
          <Form.Item
            name="password"
            label="密码"
            rules={[
              { required: true, message: "请输入密码" },
              { min: 6, message: "密码至少6个字符" },
            ]}
          >
            <Input.Password prefix={<LockOutlined />} placeholder="请输入密码" />
          </Form.Item>
          <Form.Item
            name="confirm"
            label="确认密码"
            dependencies={["password"]}
            rules={[
              { required: true, message: "请确认密码" },
              ({ getFieldValue }) => ({
                validator(_, value) {
                  if (!value || getFieldValue("password") === value) {
                    return Promise.resolve();
                  }
                  return Promise.reject(new Error("两次输入的密码不一致"));
                },
              }),
            ]}
          >
            <Input.Password prefix={<LockOutlined />} placeholder="请再次输入密码" />
          </Form.Item>
          <Form.Item style={{ marginBottom: 0 }}>
            <Button type="primary" htmlType="submit" loading={registerLoading} block>
              注册
            </Button>
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
