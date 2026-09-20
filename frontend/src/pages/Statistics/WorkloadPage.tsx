import { useState, useEffect, useCallback } from "react";
import {
  Card,
  Col,
  Row,
  Table,
  Tag,
  Space,
  Button,
  Typography,
  Empty,
  message,
  Progress,
} from "antd";
import {
  ReloadOutlined,
  BarChartOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  TeamOutlined,
  UserOutlined,
} from "@ant-design/icons";
import { statisticsApi } from "@api/modules";

const { Title, Text } = Typography;

const roleMap: Record<string, { text: string; color: string }> = {
  admin: { text: "管理员", color: "geekblue" },
  reviewer: { text: "审核员", color: "purple" },
  annotator: { text: "标注员", color: "blue" },
  user: { text: "普通用户", color: "default" },
};

export default function WorkloadPage() {
  const [personal, setPersonal] = useState<any>(null);
  const [team, setTeam] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);

  const fetchData = useCallback(() => {
    setLoading(true);
    Promise.all([statisticsApi.getPersonal(), statisticsApi.getTeam()])
      .then(([pRes, tRes]: any[]) => {
        setPersonal(pRes.data || pRes);
        const tData = tRes.data || tRes;
        setTeam(tData.items || []);
      })
      .catch(() => message.error("加载工作量统计失败"))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const accuracy = personal?.accuracy_rate;

  const statCards = [
    {
      title: "标注总数",
      value: personal?.annotation_total ?? 0,
      color: "#1890ff",
      icon: <BarChartOutlined />,
    },
    {
      title: "审核通过",
      value: personal?.annotation_approved ?? 0,
      color: "#52c41a",
      icon: <CheckCircleOutlined />,
    },
    {
      title: "审核驳回",
      value: personal?.annotation_rejected ?? 0,
      color: "#ff4d4f",
      icon: <CloseCircleOutlined />,
    },
    {
      title: "待审核",
      value: personal?.annotation_pending ?? 0,
      color: "#faad14",
      icon: <UserOutlined />,
    },
    {
      title: "任务完成",
      value: personal?.task_completed ?? 0,
      color: "#13c2c2",
      icon: <CheckCircleOutlined />,
    },
    {
      title: "任务进行中",
      value: personal?.task_in_progress ?? 0,
      color: "#722ed1",
      icon: <ReloadOutlined />,
    },
  ];

  const columns = [
    {
      title: "用户",
      dataIndex: "username",
      width: 180,
      render: (v: string, r: any) => (
        <Space>
          <Text strong>{r.full_name || v}</Text>
          {r.full_name && (
            <Text type="secondary" style={{ fontSize: 12 }}>
              ({v})
            </Text>
          )}
        </Space>
      ),
    },
    {
      title: "角色",
      dataIndex: "role",
      width: 100,
      render: (role: string) => {
        const info = roleMap[role] || { text: role, color: "default" };
        return (
          <Tag color={info.color} style={{ borderRadius: 10 }}>
            {info.text}
          </Tag>
        );
      },
    },
    { title: "标注总数", dataIndex: "annotation_total", width: 90, align: "center" as const },
    { title: "通过", dataIndex: "annotation_approved", width: 70, align: "center" as const },
    { title: "驳回", dataIndex: "annotation_rejected", width: 70, align: "center" as const },
    {
      title: "准确率",
      dataIndex: "accuracy_rate",
      width: 150,
      render: (v: number | null) => {
        if (v === null || v === undefined) return <Text type="secondary">-</Text>;
        const color = v >= 80 ? "#52c41a" : v >= 60 ? "#faad14" : "#ff4d4f";
        return (
          <Space>
            <Progress type="circle" percent={v} size={28} strokeColor={color} />
            <Text style={{ color, fontWeight: 600 }}>{v}%</Text>
          </Space>
        );
      },
    },
    { title: "任务完成", dataIndex: "task_completed", width: 90, align: "center" as const },
    { title: "进行中", dataIndex: "task_in_progress", width: 80, align: "center" as const },
    { title: "失败", dataIndex: "task_failed", width: 70, align: "center" as const },
  ];

  return (
    <div style={{ padding: 24, background: "#f0f2f5", minHeight: "100vh" }}>
      <div style={{ marginBottom: 24 }}>
        <Title level={4} style={{ margin: 0, display: "flex", alignItems: "center", gap: 8 }}>
          <TeamOutlined style={{ color: "#722ed1" }} />
          工作量统计
        </Title>
        <Text type="secondary">个人完成量、准确率与团队看板</Text>
      </div>

      {/* 个人统计卡片 */}
      <div
        style={{
          marginBottom: 16,
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
        }}
      >
        <Title level={5} style={{ margin: 0 }}>
          我的工作量
        </Title>
        <Button icon={<ReloadOutlined />} onClick={fetchData} loading={loading}>
          刷新
        </Button>
      </div>
      <Row gutter={16} style={{ marginBottom: 24 }}>
        {statCards.map((c) => (
          <Col span={4} key={c.title}>
            <Card
              size="small"
              style={{ borderRadius: 12, border: "none", boxShadow: "0 2px 8px rgba(0,0,0,0.06)" }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                <div
                  style={{
                    width: 44,
                    height: 44,
                    borderRadius: 10,
                    background: `${c.color}1a`,
                    color: c.color,
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    fontSize: 20,
                  }}
                >
                  {c.icon}
                </div>
                <div>
                  <Text type="secondary" style={{ fontSize: 12 }}>
                    {c.title}
                  </Text>
                  <div style={{ fontSize: 22, fontWeight: "bold", color: "#262626" }}>
                    {c.value}
                  </div>
                </div>
              </div>
            </Card>
          </Col>
        ))}
      </Row>

      {/* 准确率卡片 */}
      <Card
        size="small"
        style={{ marginBottom: 24, borderRadius: 12 }}
        styles={{ body: { padding: "16px 20px" } }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 24 }}>
          <div>
            <Text type="secondary">我的标注准确率</Text>
            <div
              style={{
                fontSize: 28,
                fontWeight: "bold",
                color:
                  accuracy === null || accuracy === undefined
                    ? "#bfbfbf"
                    : accuracy >= 80
                      ? "#52c41a"
                      : accuracy >= 60
                        ? "#faad14"
                        : "#ff4d4f",
              }}
            >
              {accuracy === null || accuracy === undefined ? "-" : `${accuracy}%`}
            </div>
            <Text type="secondary" style={{ fontSize: 12 }}>
              通过 {personal?.annotation_approved ?? 0} / 驳回 {personal?.annotation_rejected ?? 0}
            </Text>
          </div>
          <Progress
            type="dashboard"
            percent={accuracy ?? 0}
            size={120}
            strokeColor={
              accuracy === null || accuracy === undefined
                ? "#d9d9d9"
                : accuracy >= 80
                  ? "#52c41a"
                  : accuracy >= 60
                    ? "#faad14"
                    : "#ff4d4f"
            }
            format={() => (accuracy === null || accuracy === undefined ? "-" : `${accuracy}%`)}
          />
        </div>
      </Card>

      {/* 团队看板 */}
      <Title level={5} style={{ marginBottom: 16 }}>
        团队看板
      </Title>
      <Card style={{ borderRadius: 12, boxShadow: "0 2px 12px rgba(0,0,0,0.08)" }}>
        <Table
          columns={columns}
          dataSource={team}
          rowKey="user_id"
          loading={loading}
          pagination={false}
          scroll={{ x: 900 }}
          locale={{
            emptyText: (
              <Empty description="暂无团队成员数据" image={Empty.PRESENTED_IMAGE_SIMPLE} />
            ),
          }}
          size="middle"
        />
      </Card>
    </div>
  );
}
