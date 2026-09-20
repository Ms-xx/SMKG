import { useEffect, useState } from "react";
import {
  Row,
  Col,
  Card,
  Table,
  Tag,
  Typography,
  Space,
  Button,
  Progress,
  List,
  Avatar,
  Statistic,
} from "antd";
import {
  FileTextOutlined,
  CheckCircleOutlined,
  ClockCircleOutlined,
  ShareAltOutlined,
  RobotOutlined,
  PlusOutlined,
  ArrowRightOutlined,
  CloudUploadOutlined,
  HistoryOutlined,
  TeamOutlined,
  ExperimentOutlined,
} from "@ant-design/icons";
import { useDocumentStore } from "@store/documentStore";
import { useNavigate } from "react-router-dom";
import dayjs from "dayjs";
import relativeTime from "dayjs/plugin/relativeTime";
import { graphApi, taskApi } from "@api/modules";
import { useAuthStore } from "@store/authStore";

dayjs.extend(relativeTime);

const { Title, Text } = Typography;

const statusMap: Record<string, { color: string; text: string }> = {
  uploaded: { color: "default", text: "已上传" },
  parsing: { color: "processing", text: "解析中" },
  parsed: { color: "success", text: "已解析" },
  failed: { color: "error", text: "失败" },
};

const taskStatusMap: Record<string, { color: string; text: string }> = {
  pending: { color: "default", text: "等待中" },
  running: { color: "processing", text: "运行中" },
  completed: { color: "success", text: "已完成" },
  failed: { color: "error", text: "失败" },
};

export default function DashboardPage() {
  const { documents, total, fetchDocuments } = useDocumentStore();
  const { user } = useAuthStore();
  const navigate = useNavigate();
  const [graphStats, setGraphStats] = useState<any>(null);
  const [recentTasks, setRecentTasks] = useState<any[]>([]);

  useEffect(() => {
    fetchDocuments();
    fetchGraphStats();
    fetchRecentTasks();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const fetchGraphStats = async () => {
    try {
      const res: any = await graphApi.ragGraphStats();
      setGraphStats(res.data || res);
    } catch {
      // ignore
    }
  };

  const fetchRecentTasks = async () => {
    try {
      const res: any = await taskApi.getList({ page: 1, page_size: 5 });
      const data = res.data || res;
      setRecentTasks(data.items || []);
    } catch {
      // ignore
    }
  };

  const parsedCount = documents.filter((d) => d.status === "parsed").length;
  const parsingCount = documents.filter((d) => d.status === "parsing").length;

  const quickActions = [
    {
      icon: <CloudUploadOutlined />,
      title: "上传文档",
      description: "支持 PDF 文档解析",
      color: "#1890ff",
      path: "/documents",
    },
    {
      icon: <ShareAltOutlined />,
      title: "知识图谱",
      description: "探索实体关系",
      color: "#52c41a",
      path: "/knowledge-graph",
    },
    {
      icon: <RobotOutlined />,
      title: "智能问答",
      description: "GraphRAG 问答",
      color: "#722ed1",
      path: "/knowledge-graph/rag",
    },
    {
      icon: <HistoryOutlined />,
      title: "任务管理",
      description: "查看处理进度",
      color: "#faad14",
      path: "/tasks",
    },
  ];

  const recentDocsColumns = [
    {
      title: "标题",
      dataIndex: "title",
      ellipsis: true,
      render: (text: string, r: any) => (
        <a onClick={() => navigate(`/documents/${r.id}`)} style={{ fontWeight: 500 }}>
          {text}
        </a>
      ),
    },
    {
      title: "状态",
      dataIndex: "status",
      width: 100,
      render: (s: string) => <Tag color={statusMap[s]?.color}>{statusMap[s]?.text}</Tag>,
    },
    {
      title: "上传时间",
      dataIndex: "created_at",
      width: 120,
      render: (d: string) => (
        <Text type="secondary" style={{ fontSize: 12 }}>
          {dayjs(d).fromNow()}
        </Text>
      ),
    },
  ];

  return (
    <div style={{ padding: 24, background: "#f0f2f5", minHeight: "100vh" }}>
      {/* 欢迎区域 */}
      <div style={{ marginBottom: 24 }}>
        <Title level={4} style={{ margin: 0 }}>
          欢迎回来，{user?.full_name || user?.username || "用户"} 👋
        </Title>
        <Text type="secondary">今天是 {dayjs().format("YYYY年MM月DD日 dddd")}，开始您的工作吧</Text>
      </div>

      {/* 统计卡片 */}
      <Row gutter={16} style={{ marginBottom: 24 }}>
        <Col span={6}>
          <Card
            style={{
              borderRadius: 12,
              background: "linear-gradient(135deg, #1890ff 0%, #096dd9 100%)",
              border: "none",
            }}
            styles={{ body: { padding: "20px" } }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
              <div
                style={{
                  width: 56,
                  height: 56,
                  borderRadius: 14,
                  background: "rgba(255,255,255,0.2)",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                }}
              >
                <FileTextOutlined style={{ fontSize: 28, color: "#fff" }} />
              </div>
              <div>
                <Text style={{ color: "rgba(255,255,255,0.8)", fontSize: 13 }}>文档总数</Text>
                <div style={{ color: "#fff", fontSize: 28, fontWeight: "bold", lineHeight: 1.2 }}>
                  {total}
                </div>
              </div>
            </div>
          </Card>
        </Col>
        <Col span={6}>
          <Card
            style={{
              borderRadius: 12,
              background: "linear-gradient(135deg, #52c41a 0%, #389e0d 100%)",
              border: "none",
            }}
            styles={{ body: { padding: "20px" } }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
              <div
                style={{
                  width: 56,
                  height: 56,
                  borderRadius: 14,
                  background: "rgba(255,255,255,0.2)",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                }}
              >
                <CheckCircleOutlined style={{ fontSize: 28, color: "#fff" }} />
              </div>
              <div>
                <Text style={{ color: "rgba(255,255,255,0.8)", fontSize: 13 }}>已解析</Text>
                <div style={{ color: "#fff", fontSize: 28, fontWeight: "bold", lineHeight: 1.2 }}>
                  {parsedCount}
                </div>
              </div>
            </div>
          </Card>
        </Col>
        <Col span={6}>
          <Card
            style={{
              borderRadius: 12,
              background: "linear-gradient(135deg, #faad14 0%, #d48806 100%)",
              border: "none",
            }}
            styles={{ body: { padding: "20px" } }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
              <div
                style={{
                  width: 56,
                  height: 56,
                  borderRadius: 14,
                  background: "rgba(255,255,255,0.2)",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                }}
              >
                <ClockCircleOutlined style={{ fontSize: 28, color: "#fff" }} />
              </div>
              <div>
                <Text style={{ color: "rgba(255,255,255,0.8)", fontSize: 13 }}>解析中</Text>
                <div style={{ color: "#fff", fontSize: 28, fontWeight: "bold", lineHeight: 1.2 }}>
                  {parsingCount}
                </div>
              </div>
            </div>
          </Card>
        </Col>
        <Col span={6}>
          <Card
            style={{
              borderRadius: 12,
              background: "linear-gradient(135deg, #722ed1 0%, #531d93 100%)",
              border: "none",
            }}
            styles={{ body: { padding: "20px" } }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
              <div
                style={{
                  width: 56,
                  height: 56,
                  borderRadius: 14,
                  background: "rgba(255,255,255,0.2)",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                }}
              >
                <ShareAltOutlined style={{ fontSize: 28, color: "#fff" }} />
              </div>
              <div>
                <Text style={{ color: "rgba(255,255,255,0.8)", fontSize: 13 }}>图谱实体</Text>
                <div style={{ color: "#fff", fontSize: 28, fontWeight: "bold", lineHeight: 1.2 }}>
                  {graphStats?.total_nodes || 0}
                </div>
              </div>
            </div>
          </Card>
        </Col>
      </Row>

      {/* 快捷操作 */}
      <Row gutter={16} style={{ marginBottom: 24 }}>
        <Col span={24}>
          <Card
            size="small"
            title={
              <Space>
                <ExperimentOutlined style={{ color: "#1890ff" }} />
                <span>快捷操作</span>
              </Space>
            }
            style={{ borderRadius: 12 }}
            styles={{ body: { padding: "12px 16px" } }}
          >
            <Space size={12} wrap>
              {quickActions.map((action) => (
                <Card
                  key={action.path}
                  size="small"
                  hoverable
                  onClick={() => navigate(action.path)}
                  style={{
                    width: 160,
                    borderRadius: 10,
                    cursor: "pointer",
                    transition: "all 0.3s",
                  }}
                  styles={{ body: { padding: "16px", textAlign: "center" } }}
                >
                  <div
                    style={{
                      width: 48,
                      height: 48,
                      borderRadius: 12,
                      background: `${action.color}15`,
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      margin: "0 auto 12px",
                    }}
                  >
                    <div style={{ fontSize: 24, color: action.color }}>{action.icon}</div>
                  </div>
                  <div style={{ fontWeight: 500, marginBottom: 4 }}>{action.title}</div>
                  <div style={{ fontSize: 12, color: "#8c8c8c" }}>{action.description}</div>
                </Card>
              ))}
            </Space>
          </Card>
        </Col>
      </Row>

      {/* 最近文档和最近任务 */}
      <Row gutter={16}>
        <Col span={14}>
          <Card
            title={
              <Space>
                <HistoryOutlined style={{ color: "#1890ff" }} />
                <span>最近文档</span>
              </Space>
            }
            extra={
              <Button type="link" size="small" onClick={() => navigate("/documents")}>
                查看全部 <ArrowRightOutlined />
              </Button>
            }
            style={{ borderRadius: 12, height: "100%" }}
          >
            {documents.length === 0 ? (
              <div style={{ textAlign: "center", padding: "40px 0" }}>
                <CloudUploadOutlined style={{ fontSize: 48, color: "#d9d9d9" }} />
                <div style={{ marginTop: 16 }}>
                  <Text type="secondary">暂无文档</Text>
                </div>
                <Button
                  type="primary"
                  icon={<PlusOutlined />}
                  onClick={() => navigate("/documents")}
                  style={{ marginTop: 16 }}
                >
                  上传文档
                </Button>
              </div>
            ) : (
              <Table
                dataSource={documents.slice(0, 5)}
                rowKey="id"
                pagination={false}
                columns={recentDocsColumns}
                size="small"
              />
            )}
          </Card>
        </Col>
        <Col span={10}>
          <Card
            title={
              <Space>
                <TeamOutlined style={{ color: "#722ed1" }} />
                <span>最近任务</span>
              </Space>
            }
            extra={
              <Button type="link" size="small" onClick={() => navigate("/tasks")}>
                查看全部 <ArrowRightOutlined />
              </Button>
            }
            style={{ borderRadius: 12, height: "100%" }}
          >
            {recentTasks.length === 0 ? (
              <div style={{ textAlign: "center", padding: "40px 0" }}>
                <ClockCircleOutlined style={{ fontSize: 48, color: "#d9d9d9" }} />
                <div style={{ marginTop: 16 }}>
                  <Text type="secondary">暂无任务</Text>
                </div>
              </div>
            ) : (
              <List
                dataSource={recentTasks}
                renderItem={(item: any) => (
                  <List.Item>
                    <List.Item.Meta
                      avatar={
                        <Avatar
                          style={{
                            background:
                              taskStatusMap[item.status]?.color === "success"
                                ? "#52c41a"
                                : taskStatusMap[item.status]?.color === "processing"
                                  ? "#1890ff"
                                  : taskStatusMap[item.status]?.color === "error"
                                    ? "#ff4d4f"
                                    : "#d9d9d9",
                          }}
                          icon={<ClockCircleOutlined />}
                        />
                      }
                      title={
                        <Space>
                          <Tag>
                            {item.task_type === "parsing"
                              ? "文档解析"
                              : item.task_type === "extraction"
                                ? "信息抽取"
                                : "知识图谱"}
                          </Tag>
                          <Tag color={taskStatusMap[item.status]?.color}>
                            {taskStatusMap[item.status]?.text}
                          </Tag>
                        </Space>
                      }
                      description={
                        <Space>
                          <Text type="secondary" style={{ fontSize: 12 }}>
                            {dayjs(item.created_at).fromNow()}
                          </Text>
                          {item.status === "running" && (
                            <Progress
                              percent={item.progress || 0}
                              size="small"
                              style={{ width: 100 }}
                            />
                          )}
                        </Space>
                      }
                    />
                  </List.Item>
                )}
              />
            )}
          </Card>
        </Col>
      </Row>

      {/* 图谱概览 */}
      {graphStats?.total_nodes > 0 && (
        <Row gutter={16} style={{ marginTop: 24 }}>
          <Col span={24}>
            <Card
              title={
                <Space>
                  <ShareAltOutlined style={{ color: "#52c41a" }} />
                  <span>知识图谱概览</span>
                </Space>
              }
              extra={
                <Button type="link" onClick={() => navigate("/knowledge-graph")}>
                  进入图谱 <ArrowRightOutlined />
                </Button>
              }
              style={{ borderRadius: 12 }}
            >
              <Row gutter={16}>
                <Col span={8}>
                  <Card
                    size="small"
                    style={{ background: "#f0f5ff", border: "none", borderRadius: 8 }}
                  >
                    <Statistic
                      title="实体总数"
                      value={graphStats.total_nodes}
                      valueStyle={{ color: "#1890ff", fontSize: 24 }}
                    />
                  </Card>
                </Col>
                <Col span={8}>
                  <Card
                    size="small"
                    style={{ background: "#f6ffed", border: "none", borderRadius: 8 }}
                  >
                    <Statistic
                      title="关系总数"
                      value={graphStats.total_relations}
                      valueStyle={{ color: "#52c41a", fontSize: 24 }}
                    />
                  </Card>
                </Col>
                <Col span={8}>
                  <Card
                    size="small"
                    style={{ background: "#fff7e6", border: "none", borderRadius: 8 }}
                  >
                    <div style={{ fontSize: 14, color: "#8c8c8c", marginBottom: 8 }}>
                      节点类型分布
                    </div>
                    <Space wrap size={4}>
                      {Object.entries(graphStats.node_labels || {}).map(
                        ([label, count]: [string, any]) => (
                          <Tag key={label} style={{ borderRadius: 8 }}>
                            {label} ({count})
                          </Tag>
                        ),
                      )}
                    </Space>
                  </Card>
                </Col>
              </Row>
            </Card>
          </Col>
        </Row>
      )}
    </div>
  );
}
