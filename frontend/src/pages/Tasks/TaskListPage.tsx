import { useState, useEffect, useRef, useCallback } from "react";
import {
  Table,
  Tag,
  Space,
  Button,
  Popconfirm,
  message,
  Drawer,
  Descriptions,
  Progress,
  Select,
  Typography,
  Card,
  Row,
  Col,
  Empty,
  Modal,
  DatePicker,
} from "antd";
import {
  PauseCircleOutlined,
  PlayCircleOutlined,
  ReloadOutlined,
  EyeOutlined,
  DeleteOutlined,
  ScheduleOutlined,
  CheckCircleOutlined,
  ClockCircleOutlined,
  CloseCircleOutlined,
  FileTextOutlined,
  NodeIndexOutlined,
  RobotOutlined,
  ReloadOutlined as RetryIcon,
  UserAddOutlined,
} from "@ant-design/icons";
import { taskApi, userApi } from "@api/modules";
import dayjs from "dayjs";
import relativeTime from "dayjs/plugin/relativeTime";

dayjs.extend(relativeTime);

const { Text, Title } = Typography;

const statusMap: Record<string, { color: string; text: string; icon: React.ReactNode }> = {
  pending: { color: "default", text: "等待中", icon: <ClockCircleOutlined /> },
  running: { color: "processing", text: "运行中", icon: <ScheduleOutlined /> },
  paused: { color: "warning", text: "已暂停", icon: <PauseCircleOutlined /> },
  completed: { color: "success", text: "已完成", icon: <CheckCircleOutlined /> },
  failed: { color: "error", text: "失败", icon: <CloseCircleOutlined /> },
  cancelled: { color: "default", text: "已取消", icon: <CloseCircleOutlined /> },
};

const typeMap: Record<string, { text: string; color: string; icon: React.ReactNode }> = {
  parsing: { text: "文档解析", color: "blue", icon: <FileTextOutlined /> },
  extraction: { text: "信息抽取", color: "purple", icon: <NodeIndexOutlined /> },
  graph: { text: "知识图谱", color: "cyan", icon: <RobotOutlined /> },
  parse_validation: { text: "解析校验", color: "geekblue", icon: <FileTextOutlined /> },
  entity_annotation: { text: "实体标注", color: "purple", icon: <NodeIndexOutlined /> },
  graph_review: { text: "图谱审核", color: "cyan", icon: <RobotOutlined /> },
};

const priorityMap: Record<number, { text: string; color: string }> = {
  0: { text: "普通", color: "default" },
  1: { text: "低", color: "green" },
  2: { text: "中", color: "orange" },
  3: { text: "高", color: "red" },
  4: { text: "紧急", color: "magenta" },
};

export default function TaskListPage() {
  const [tasks, setTasks] = useState<any[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);
  const [loading, setLoading] = useState(false);
  const [actionId, setActionId] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState<string | undefined>(undefined);
  const [typeFilter, setTypeFilter] = useState<string | undefined>(undefined);
  const [detailTask, setDetailTask] = useState<any>(null);
  const [_detailLoading, setDetailLoading] = useState(false);

  const [assignTask, setAssignTask] = useState<any>(null);
  const [assignUser, setAssignUser] = useState<string | undefined>(undefined);
  const [assignPriority, setAssignPriority] = useState<number>(0);
  const [assignDueAt, setAssignDueAt] = useState<string | null>(null);
  const [users, setUsers] = useState<any[]>([]);
  const [assignLoading, setAssignLoading] = useState(false);

  const pollingRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const fetchTasks = useCallback(() => {
    setLoading(true);
    taskApi
      .getList({ page, page_size: pageSize, status: statusFilter, task_type: typeFilter })
      .then((res: any) => {
        const data = res.data || res;
        setTasks(data.items || []);
        setTotal(data.total || 0);
      })
      .catch(() => message.error("加载任务列表失败"))
      .finally(() => setLoading(false));
  }, [page, pageSize, statusFilter, typeFilter]);

  useEffect(() => {
    fetchTasks();
  }, [fetchTasks]);

  const fetchTaskProgress = useCallback(async (taskId: string) => {
    try {
      const res: any = await taskApi.getProgress(taskId);
      const progressData = res.data || res;
      setTasks((prev) =>
        prev.map((task) => {
          if (task.id === taskId) {
            return {
              ...task,
              progress: progressData.progress ?? task.progress,
              status: progressData.status ?? task.status,
            };
          }
          return task;
        }),
      );
      return progressData;
    } catch {
      return null;
    }
  }, []);

  useEffect(() => {
    const runningTasks = tasks.filter((t) => t.status === "pending" || t.status === "running");
    if (runningTasks.length > 0) {
      pollingRef.current = setInterval(() => {
        runningTasks.forEach((task) => fetchTaskProgress(task.id));
      }, 2000);
    } else if (pollingRef.current) {
      clearInterval(pollingRef.current);
      pollingRef.current = null;
    }
    return () => {
      if (pollingRef.current) clearInterval(pollingRef.current);
    };
  }, [tasks, fetchTaskProgress]);

  const openDetail = async (task: any) => {
    setDetailTask(task);
    setDetailLoading(true);
    try {
      const res: any = await taskApi.getById(task.id);
      setDetailTask(res.data || res);
    } catch {
      setDetailTask(task);
    } finally {
      setDetailLoading(false);
    }
  };

  const openAssign = async (task: any) => {
    setAssignTask(task);
    setAssignUser(task.assigned_to || undefined);
    setAssignPriority(task.priority ?? 0);
    setAssignDueAt(task.due_at || null);
    try {
      const res: any = await userApi.getList({ page_size: 100 });
      const data = res.data || res;
      setUsers(data.items || []);
    } catch {
      setUsers([]);
    }
  };

  const submitAssign = async () => {
    if (!assignUser) {
      message.warning("请选择负责人");
      return;
    }
    setAssignLoading(true);
    try {
      await taskApi.assign(assignTask.id, {
        assigned_to: assignUser,
        priority: assignPriority,
        due_at: assignDueAt || undefined,
      });
      message.success("任务已分配");
      setAssignTask(null);
      fetchTasks();
    } catch (e: any) {
      message.error(e?.response?.data?.detail || "分配失败");
    } finally {
      setAssignLoading(false);
    }
  };

  const handleAction = async (
    id: string,
    action: "pause" | "resume" | "cancel" | "retry" | "terminate",
  ) => {
    setActionId(id);
    try {
      if (action === "pause") {
        await taskApi.pause(id);
        message.success("任务已暂停");
      } else if (action === "resume") {
        await taskApi.resume(id);
        message.success("任务已恢复");
      } else if (action === "cancel") {
        await taskApi.cancel(id);
        message.success("任务已取消");
      } else if (action === "retry") {
        const res: any = await taskApi.retry(id);
        const msg = res.data?.message || res.message || "";
        if (msg) message.success(msg);
        else message.error(res.data?.error || res.error || "重试失败");
      } else {
        await taskApi.terminate(id);
        message.success("任务已终止并删除");
      }
      fetchTasks();
    } catch (e: any) {
      message.error(e?.response?.data?.detail || "操作失败");
    } finally {
      setActionId(null);
    }
  };

  // 统计
  const runningCount = tasks.filter((t) => t.status === "running").length;
  const completedCount = tasks.filter((t) => t.status === "completed").length;
  const failedCount = tasks.filter((t) => t.status === "failed").length;

  const columns = [
    {
      title: "任务类型",
      dataIndex: "task_type",
      width: 120,
      render: (t: string) => {
        const info = typeMap[t] || { text: t, color: "default", icon: <ScheduleOutlined /> };
        return (
          <Space>
            <Tag color={info.color} icon={info.icon} style={{ borderRadius: 12 }}>
              {info.text}
            </Tag>
          </Space>
        );
      },
    },
    {
      title: "状态",
      dataIndex: "status",
      width: 110,
      render: (s: string) => {
        const info = statusMap[s] || { text: s, color: "default", icon: <ClockCircleOutlined /> };
        return (
          <Tag color={info.color} icon={info.icon} style={{ borderRadius: 12 }}>
            {info.text}
          </Tag>
        );
      },
    },
    {
      title: "进度",
      dataIndex: "progress",
      width: 180,
      render: (p: number, r: any) => {
        if (r.status === "running") {
          return (
            <div style={{ minWidth: 140 }}>
              <Progress percent={p || 0} size="small" status="active" strokeColor="#1890ff" />
              {r.current_step && (
                <Text type="secondary" style={{ fontSize: 11 }}>
                  {r.current_step}
                </Text>
              )}
            </div>
          );
        }
        return (
          <Space>
            <Text type="secondary">{(p || 0).toFixed(0)}%</Text>
            {r.status === "pending" && (
              <Tag color="default" style={{ fontSize: 10, borderRadius: 8 }}>
                排队中
              </Tag>
            )}
          </Space>
        );
      },
    },
    {
      title: "优先级",
      dataIndex: "priority",
      width: 80,
      render: (p: number) => {
        const info = priorityMap[p] || { text: "普通", color: "default" };
        return (
          <Tag color={info.color} style={{ borderRadius: 8 }}>
            {info.text}
          </Tag>
        );
      },
    },
    {
      title: "创建时间",
      dataIndex: "created_at",
      width: 130,
      render: (d: string) => (
        <Text type="secondary" style={{ fontSize: 12 }}>
          {dayjs(d).fromNow()}
        </Text>
      ),
    },
    {
      title: "操作",
      key: "action",
      width: 160,
      render: (_: any, r: any) => (
        <Space size={4}>
          <Button
            type="link"
            size="small"
            icon={<EyeOutlined />}
            onClick={() => openDetail(r)}
            style={{ padding: "0 4px" }}
          />
          <Button
            type="link"
            size="small"
            icon={<UserAddOutlined />}
            onClick={() => openAssign(r)}
            style={{ padding: "0 4px" }}
          />
          {r.status === "running" && (
            <Button
              type="link"
              size="small"
              icon={<PauseCircleOutlined />}
              onClick={() => handleAction(r.id, "pause")}
              loading={actionId === r.id}
              style={{ padding: "0 4px" }}
            />
          )}
          {r.status === "paused" && (
            <Button
              type="link"
              size="small"
              icon={<PlayCircleOutlined />}
              onClick={() => handleAction(r.id, "resume")}
              loading={actionId === r.id}
              style={{ padding: "0 4px" }}
            />
          )}
          {(r.status === "failed" || r.status === "cancelled") && (
            <Button
              type="link"
              size="small"
              icon={<RetryIcon />}
              onClick={() => handleAction(r.id, "retry")}
              loading={actionId === r.id}
              style={{ padding: "0 4px" }}
            />
          )}
          {(r.status === "running" || r.status === "pending" || r.status === "paused") && (
            <Popconfirm
              title="确定终止？"
              description="终止后任务将被删除"
              onConfirm={() => handleAction(r.id, "terminate")}
              okText="确定"
              cancelText="取消"
            >
              <Button
                type="link"
                size="small"
                danger
                icon={<DeleteOutlined />}
                loading={actionId === r.id}
                style={{ padding: "0 4px" }}
              />
            </Popconfirm>
          )}
        </Space>
      ),
    },
  ];

  const taskTypeOptions = Object.entries(typeMap).map(([v, { text }]) => ({
    value: v,
    label: text,
  }));
  const statusOptions = Object.entries(statusMap).map(([v, { text }]) => ({
    value: v,
    label: text,
  }));

  return (
    <div style={{ padding: 24, background: "#f0f2f5", minHeight: "100vh" }}>
      {/* 页面标题 */}
      <div style={{ marginBottom: 24 }}>
        <Title level={4} style={{ margin: 0, display: "flex", alignItems: "center", gap: 8 }}>
          <ScheduleOutlined style={{ color: "#722ed1" }} />
          任务管理
        </Title>
        <Text type="secondary">管理文档解析、信息抽取和知识图谱构建任务</Text>
      </div>

      {/* 统计卡片 */}
      <Row gutter={16} style={{ marginBottom: 24 }}>
        <Col span={6}>
          <Card
            size="small"
            style={{ borderRadius: 12, border: "none", boxShadow: "0 2px 8px rgba(0,0,0,0.06)" }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
              <div
                style={{
                  width: 48,
                  height: 48,
                  borderRadius: 12,
                  background: "linear-gradient(135deg, #1890ff 0%, #096dd9 100%)",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                }}
              >
                <ScheduleOutlined style={{ fontSize: 24, color: "#fff" }} />
              </div>
              <div>
                <Text type="secondary" style={{ fontSize: 12 }}>
                  任务总数
                </Text>
                <div style={{ fontSize: 24, fontWeight: "bold", color: "#262626" }}>{total}</div>
              </div>
            </div>
          </Card>
        </Col>
        <Col span={6}>
          <Card
            size="small"
            style={{ borderRadius: 12, border: "none", boxShadow: "0 2px 8px rgba(0,0,0,0.06)" }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
              <div
                style={{
                  width: 48,
                  height: 48,
                  borderRadius: 12,
                  background: "linear-gradient(135deg, #1890ff 0%, #40a9ff 100%)",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                }}
              >
                <ScheduleOutlined style={{ fontSize: 24, color: "#fff" }} />
              </div>
              <div>
                <Text type="secondary" style={{ fontSize: 12 }}>
                  运行中
                </Text>
                <div style={{ fontSize: 24, fontWeight: "bold", color: "#1890ff" }}>
                  {runningCount}
                </div>
              </div>
            </div>
          </Card>
        </Col>
        <Col span={6}>
          <Card
            size="small"
            style={{ borderRadius: 12, border: "none", boxShadow: "0 2px 8px rgba(0,0,0,0.06)" }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
              <div
                style={{
                  width: 48,
                  height: 48,
                  borderRadius: 12,
                  background: "linear-gradient(135deg, #52c41a 0%, #73d13d 100%)",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                }}
              >
                <CheckCircleOutlined style={{ fontSize: 24, color: "#fff" }} />
              </div>
              <div>
                <Text type="secondary" style={{ fontSize: 12 }}>
                  已完成
                </Text>
                <div style={{ fontSize: 24, fontWeight: "bold", color: "#52c41a" }}>
                  {completedCount}
                </div>
              </div>
            </div>
          </Card>
        </Col>
        <Col span={6}>
          <Card
            size="small"
            style={{ borderRadius: 12, border: "none", boxShadow: "0 2px 8px rgba(0,0,0,0.06)" }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
              <div
                style={{
                  width: 48,
                  height: 48,
                  borderRadius: 12,
                  background: "linear-gradient(135deg, #ff4d4f 0%, #ff7875 100%)",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                }}
              >
                <CloseCircleOutlined style={{ fontSize: 24, color: "#fff" }} />
              </div>
              <div>
                <Text type="secondary" style={{ fontSize: 12 }}>
                  失败
                </Text>
                <div style={{ fontSize: 24, fontWeight: "bold", color: "#ff4d4f" }}>
                  {failedCount}
                </div>
              </div>
            </div>
          </Card>
        </Col>
      </Row>

      {/* 筛选和操作栏 */}
      <Card
        size="small"
        style={{ marginBottom: 16, borderRadius: 12 }}
        styles={{ body: { padding: "12px 16px" } }}
      >
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <Space wrap size={12}>
            <Select
              placeholder="任务类型"
              allowClear
              style={{ width: 130 }}
              options={taskTypeOptions}
              onChange={(v) => {
                setTypeFilter(v);
                setPage(1);
              }}
            />
            <Select
              placeholder="状态筛选"
              allowClear
              style={{ width: 120 }}
              options={statusOptions}
              onChange={(v) => {
                setStatusFilter(v);
                setPage(1);
              }}
            />
          </Space>
          <Button icon={<ReloadOutlined />} onClick={fetchTasks}>
            刷新
          </Button>
        </div>
      </Card>

      {/* 任务列表 */}
      <Card style={{ borderRadius: 12, boxShadow: "0 2px 12px rgba(0,0,0,0.08)" }}>
        <Table
          columns={columns}
          dataSource={tasks}
          rowKey="id"
          loading={loading}
          pagination={{
            current: page,
            pageSize,
            total,
            showSizeChanger: true,
            showTotal: (t: number) => `共 ${t} 条`,
            onChange: (p, ps) => {
              setPage(p);
              setPageSize(ps);
            },
          }}
          locale={{
            emptyText: <Empty description="暂无任务" image={Empty.PRESENTED_IMAGE_SIMPLE} />,
          }}
          size="middle"
        />
      </Card>

      {/* 任务详情抽屉 */}
      <Drawer
        title={
          <Space>
            <ScheduleOutlined style={{ color: "#722ed1" }} />
            <span>任务详情</span>
            {detailTask && (
              <Tag
                color={typeMap[detailTask.task_type]?.color}
                icon={typeMap[detailTask.task_type]?.icon}
              >
                {typeMap[detailTask.task_type]?.text || detailTask.task_type}
              </Tag>
            )}
          </Space>
        }
        open={!!detailTask}
        onClose={() => setDetailTask(null)}
        width={480}
        styles={{ body: { padding: 0 } }}
      >
        {detailTask && (
          <div>
            {/* 状态头部 */}
            <div
              style={{
                padding: 24,
                background:
                  detailTask.status === "completed"
                    ? "linear-gradient(135deg, #f6ffed 0%, #d9f7be 100%)"
                    : detailTask.status === "failed"
                      ? "linear-gradient(135deg, #fff2f0 0%, #ffccc7 100%)"
                      : detailTask.status === "running"
                        ? "linear-gradient(135deg, #e6f7ff 0%, #bae7ff 100%)"
                        : "#fafafa",
                borderBottom: "1px solid #e8e8e8",
              }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 12 }}>
                <div
                  style={{
                    width: 48,
                    height: 48,
                    borderRadius: 12,
                    background:
                      statusMap[detailTask.status]?.color === "success"
                        ? "#52c41a"
                        : statusMap[detailTask.status]?.color === "error"
                          ? "#ff4d4f"
                          : statusMap[detailTask.status]?.color === "processing"
                            ? "#1890ff"
                            : "#d9d9d9",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                  }}
                >
                  {statusMap[detailTask.status]?.icon || (
                    <ClockCircleOutlined style={{ fontSize: 24, color: "#fff" }} />
                  )}
                </div>
                <div>
                  <Tag
                    color={statusMap[detailTask.status]?.color}
                    style={{ borderRadius: 12, fontSize: 14, padding: "4px 12px" }}
                  >
                    {statusMap[detailTask.status]?.text || detailTask.status}
                  </Tag>
                  <div style={{ marginTop: 8 }}>
                    <Progress
                      percent={detailTask.progress || 0}
                      size="small"
                      status={detailTask.status === "failed" ? "exception" : undefined}
                      strokeColor={detailTask.status === "completed" ? "#52c41a" : "#1890ff"}
                      style={{ width: 200 }}
                    />
                  </div>
                </div>
              </div>
            </div>

            {/* 详情内容 */}
            <div style={{ padding: 20 }}>
              <Title level={5} style={{ marginBottom: 12 }}>
                基本信息
              </Title>
              <Descriptions column={1} size="small" style={{ marginBottom: 24 }}>
                <Descriptions.Item label="任务ID">
                  <Text copyable style={{ fontFamily: "monospace", fontSize: 12 }}>
                    {detailTask.id}
                  </Text>
                </Descriptions.Item>
                <Descriptions.Item label="任务类型">
                  <Space>
                    <Tag
                      color={typeMap[detailTask.task_type]?.color}
                      icon={typeMap[detailTask.task_type]?.icon}
                    >
                      {typeMap[detailTask.task_type]?.text || detailTask.task_type}
                    </Tag>
                    <Tag color={priorityMap[detailTask.priority]?.color}>
                      {priorityMap[detailTask.priority]?.text || "普通"}
                    </Tag>
                  </Space>
                </Descriptions.Item>
                <Descriptions.Item label="创建时间">
                  {detailTask.created_at
                    ? dayjs(detailTask.created_at).format("YYYY-MM-DD HH:mm:ss")
                    : "-"}
                </Descriptions.Item>
                <Descriptions.Item label="开始时间">
                  {detailTask.started_at
                    ? dayjs(detailTask.started_at).format("YYYY-MM-DD HH:mm:ss")
                    : "-"}
                </Descriptions.Item>
                <Descriptions.Item label="完成时间">
                  {detailTask.completed_at
                    ? dayjs(detailTask.completed_at).format("YYYY-MM-DD HH:mm:ss")
                    : "-"}
                </Descriptions.Item>
                {detailTask.document_id && (
                  <Descriptions.Item label="关联文档">
                    <Text copyable style={{ fontFamily: "monospace", fontSize: 12 }}>
                      {detailTask.document_id}
                    </Text>
                  </Descriptions.Item>
                )}
                <Descriptions.Item label="负责人">
                  <Text style={{ fontFamily: "monospace", fontSize: 12 }}>
                    {detailTask.assigned_to || "-"}
                  </Text>
                </Descriptions.Item>
                <Descriptions.Item label="截止日期">
                  {detailTask.due_at ? dayjs(detailTask.due_at).format("YYYY-MM-DD HH:mm") : "-"}
                </Descriptions.Item>
              </Descriptions>

              {detailTask.error_message && (
                <>
                  <Title level={5} style={{ marginBottom: 12, color: "#ff4d4f" }}>
                    错误信息
                  </Title>
                  <div
                    style={{
                      background: "#fff2f0",
                      border: "1px solid #ffccc7",
                      borderRadius: 8,
                      padding: 16,
                      marginBottom: 24,
                    }}
                  >
                    <Text type="danger" style={{ fontFamily: "monospace" }}>
                      {detailTask.error_message}
                    </Text>
                  </div>
                </>
              )}

              {detailTask.result && Object.keys(detailTask.result).length > 0 && (
                <>
                  <Title level={5} style={{ marginBottom: 12 }}>
                    执行结果
                  </Title>
                  <div
                    style={{
                      background: "#f5f5f5",
                      borderRadius: 8,
                      padding: 16,
                      marginBottom: 24,
                      maxHeight: 200,
                      overflow: "auto",
                    }}
                  >
                    <pre style={{ margin: 0, fontSize: 12, fontFamily: "monospace" }}>
                      {JSON.stringify(detailTask.result, null, 2)}
                    </pre>
                  </div>
                </>
              )}

              {detailTask.params && Object.keys(detailTask.params).length > 0 && (
                <>
                  <Title level={5} style={{ marginBottom: 12 }}>
                    任务参数
                  </Title>
                  <div
                    style={{
                      background: "#f5f5f5",
                      borderRadius: 8,
                      padding: 16,
                    }}
                  >
                    <pre style={{ margin: 0, fontSize: 12, fontFamily: "monospace" }}>
                      {JSON.stringify(detailTask.params, null, 2)}
                    </pre>
                  </div>
                </>
              )}

              {/* 操作按钮 */}
              <div style={{ marginTop: 24, display: "flex", gap: 12 }}>
                {detailTask.status === "running" && (
                  <Button
                    type="primary"
                    icon={<PauseCircleOutlined />}
                    onClick={() => {
                      handleAction(detailTask.id, "pause");
                    }}
                  >
                    暂停任务
                  </Button>
                )}
                {detailTask.status === "paused" && (
                  <Button
                    type="primary"
                    icon={<PlayCircleOutlined />}
                    onClick={() => {
                      handleAction(detailTask.id, "resume");
                    }}
                  >
                    恢复任务
                  </Button>
                )}
                {(detailTask.status === "failed" || detailTask.status === "cancelled") && (
                  <Button
                    type="primary"
                    icon={<RetryIcon />}
                    onClick={() => {
                      handleAction(detailTask.id, "retry");
                    }}
                  >
                    重新提交
                  </Button>
                )}
                {(detailTask.status === "running" ||
                  detailTask.status === "pending" ||
                  detailTask.status === "paused") && (
                  <Popconfirm
                    title="确定终止任务？"
                    description="终止后任务将被删除"
                    onConfirm={() => {
                      handleAction(detailTask.id, "terminate");
                      setDetailTask(null);
                    }}
                    okText="确定"
                    cancelText="取消"
                  >
                    <Button danger icon={<DeleteOutlined />}>
                      终止任务
                    </Button>
                  </Popconfirm>
                )}
              </div>
            </div>
          </div>
        )}
      </Drawer>

      {/* 任务分配弹窗 */}
      <Modal
        title={
          <Space>
            <UserAddOutlined />
            分配任务
          </Space>
        }
        open={!!assignTask}
        onCancel={() => setAssignTask(null)}
        onOk={submitAssign}
        confirmLoading={assignLoading}
        okText="确定"
        cancelText="取消"
      >
        <div style={{ display: "flex", flexDirection: "column", gap: 16, paddingTop: 8 }}>
          <div>
            <Text type="secondary">负责人</Text>
            <Select
              showSearch
              style={{ width: "100%", marginTop: 6 }}
              placeholder="选择负责人"
              value={assignUser}
              onChange={setAssignUser}
              optionFilterProp="label"
              options={users.map((u: any) => ({
                value: u.id,
                label: u.username || u.full_name || u.id,
              }))}
            />
          </div>
          <div>
            <Text type="secondary">优先级</Text>
            <Select
              style={{ width: "100%", marginTop: 6 }}
              value={assignPriority}
              onChange={setAssignPriority}
              options={[0, 1, 2, 3, 4].map((p) => ({
                value: p,
                label: priorityMap[p]?.text || "普通",
              }))}
            />
          </div>
          <div>
            <Text type="secondary">截止日期</Text>
            <DatePicker
              showTime
              style={{ width: "100%", marginTop: 6 }}
              value={assignDueAt ? dayjs(assignDueAt) : null}
              onChange={(d: any) => setAssignDueAt(d ? d.toISOString() : null)}
            />
          </div>
        </div>
      </Modal>
    </div>
  );
}
