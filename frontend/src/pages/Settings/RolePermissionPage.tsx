import { useState, useEffect, useCallback } from "react";
import { Table, Tag, Button, Card, Typography, Modal, Checkbox, message, Empty, Space } from "antd";
import { ControlOutlined, EditOutlined, ReloadOutlined } from "@ant-design/icons";
import { permissionApi } from "@api/modules";
import type { PermissionInfo, RoleItem } from "@/types";

const { Title, Text } = Typography;

const roleNameMap: Record<string, string> = {
  admin: "系统管理员",
  reviewer: "审核员",
  annotator: "标注员",
  user: "普通用户",
};

export default function RolePermissionPage() {
  const [roles, setRoles] = useState<RoleItem[]>([]);
  const [definitions, setDefinitions] = useState<PermissionInfo[]>([]);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [editingRole, setEditingRole] = useState<RoleItem | null>(null);
  const [selected, setSelected] = useState<string[]>([]);

  const fetchData = useCallback(() => {
    setLoading(true);
    Promise.all([permissionApi.getRoles(), permissionApi.getDefinitions()])
      .then(([rolesRes, defRes]) => {
        setRoles((rolesRes as any).items || []);
        setDefinitions((defRes as any).items || []);
      })
      .catch(() => message.error("加载权限数据失败"))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const openEdit = (role: RoleItem) => {
    setEditingRole(role);
    setSelected(role.permissions || []);
  };

  const savePermissions = () => {
    if (!editingRole) return;
    setSaving(true);
    permissionApi
      .updateRolePermissions(editingRole.name, selected)
      .then(() => {
        message.success(`角色「${roleNameMap[editingRole.name] || editingRole.name}」权限已更新`);
        setEditingRole(null);
        fetchData();
      })
      .catch(() => message.error("保存失败"))
      .finally(() => setSaving(false));
  };

  const columns = [
    {
      title: "角色",
      dataIndex: "name",
      width: 140,
      render: (name: string) => <Text strong>{name}</Text>,
    },
    {
      title: "中文名",
      dataIndex: "name",
      width: 120,
      render: (name: string) => roleNameMap[name] || name,
    },
    {
      title: "说明",
      dataIndex: "description",
      render: (d: string) => d || "-",
    },
    {
      title: "权限码",
      dataIndex: "permissions",
      render: (perms: string[]) => (
        <Space wrap size={4}>
          {(perms || []).map((p) => (
            <Tag key={p} color="geekblue" style={{ borderRadius: 10 }}>
              {p}
            </Tag>
          ))}
        </Space>
      ),
    },
    {
      title: "操作",
      key: "action",
      width: 100,
      render: (_: any, role: RoleItem) => (
        <Button
          type="link"
          icon={<EditOutlined />}
          onClick={() => openEdit(role)}
          disabled={role.name === "admin"}
          style={{ padding: "0 4px" }}
        >
          编辑
        </Button>
      ),
    },
  ];

  return (
    <div style={{ padding: 24, background: "#f0f2f5", minHeight: "100vh" }}>
      <div
        style={{
          marginBottom: 24,
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
        }}
      >
        <div>
          <Title level={4} style={{ margin: 0, display: "flex", alignItems: "center", gap: 8 }}>
            <ControlOutlined style={{ color: "#722ed1" }} />
            角色权限管理
          </Title>
          <Text type="secondary">配置各角色的文档级 / 任务级 / 系统级权限码</Text>
        </div>
        <Button icon={<ReloadOutlined />} onClick={fetchData}>
          刷新
        </Button>
      </div>

      <Card style={{ borderRadius: 12, boxShadow: "0 2px 12px rgba(0,0,0,0.08)" }}>
        <Table
          columns={columns}
          dataSource={roles}
          rowKey="id"
          loading={loading}
          pagination={false}
          locale={{
            emptyText: <Empty description="暂无角色数据" image={Empty.PRESENTED_IMAGE_SIMPLE} />,
          }}
          size="middle"
          scroll={{ x: 800 }}
        />
      </Card>

      <Modal
        title={
          editingRole
            ? `编辑权限：${roleNameMap[editingRole.name] || editingRole.name}（${editingRole.name}）`
            : ""
        }
        open={!!editingRole}
        onOk={savePermissions}
        onCancel={() => setEditingRole(null)}
        confirmLoading={saving}
        okText="保存"
        cancelText="取消"
        width={560}
      >
        <Text type="secondary" style={{ display: "block", marginBottom: 12 }}>
          勾选授予该角色的权限码（格式：资源:操作）
        </Text>
        <Checkbox.Group
          options={definitions.map((d) => ({
            label: `${d.code}（${d.description}）`,
            value: d.code,
          }))}
          value={selected}
          onChange={(vals) => setSelected(vals as string[])}
          style={{ display: "flex", flexDirection: "column", gap: 8 }}
        />
      </Modal>
    </div>
  );
}
