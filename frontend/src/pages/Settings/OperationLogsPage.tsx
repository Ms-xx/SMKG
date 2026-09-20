import { useState, useEffect, useCallback } from "react";
import {
  Table,
  Tag,
  Space,
  Input,
  Select,
  DatePicker,
  Button,
  Card,
  Typography,
  Empty,
  message,
  Drawer,
  Descriptions,
} from "antd";
import { ReloadOutlined, AuditOutlined, EyeOutlined } from "@ant-design/icons";
import { operationLogApi } from "@api/modules";
import dayjs from "dayjs";

const { Title, Text } = Typography;

const actionMap: Record<string, { text: string; color: string }> = {
  create: { text: "创建标注", color: "green" },
  update: { text: "修改标注", color: "blue" },
  submit: { text: "提交审核", color: "cyan" },
  first_review: { text: "初审", color: "orange" },
  final_review: { text: "终审", color: "purple" },
  delete: { text: "删除标注", color: "red" },
};

const resourceTypeMap: Record<string, { text: string; color: string }> = {
  annotation: { text: "标注", color: "geekblue" },
  task: { text: "任务", color: "blue" },
  document: { text: "文档", color: "green" },
  user: { text: "用户", color: "cyan" },
};

export default function OperationLogsPage() {
  const [logs, setLogs] = useState<any[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);
  const [loading, setLoading] = useState(false);

  const [userFilter, setUserFilter] = useState<string | undefined>(undefined);
  const [actionFilter, setActionFilter] = useState<string | undefined>(undefined);
  const [resourceTypeFilter, setResourceTypeFilter] = useState<string | undefined>(undefined);
  const [range, setRange] = useState<[dayjs.Dayjs | null, dayjs.Dayjs | null] | null>(null);

  const [detailLog, setDetailLog] = useState<any>(null);

  const fetchLogs = useCallback(() => {
    setLoading(true);
    const [start, end] = range || [null, null];
    operationLogApi
      .getList({
        page,
        page_size: pageSize,
        user_id: userFilter,
        action: actionFilter,
        resource_type: resourceTypeFilter,
        start_date: start ? start.toISOString() : undefined,
        end_date: end ? end.toISOString() : undefined,
      })
      .then((res: any) => {
        const data = res.data || res;
        setLogs(data.items || []);
        setTotal(data.total || 0);
      })
      .catch(() => message.error("加载操作日志失败"))
      .finally(() => setLoading(false));
  }, [page, pageSize, userFilter, actionFilter, resourceTypeFilter, range]);

  useEffect(() => {
    fetchLogs();
  }, [fetchLogs]);

  const columns = [
    {
      title: "操作人",
      dataIndex: "user_id",
      width: 180,
      render: (v: string) => (
        <Text style={{ fontFamily: "monospace", fontSize: 12 }}>{v || "-"}</Text>
      ),
    },
    {
      title: "操作类型",
      dataIndex: "action",
      width: 110,
      render: (a: string) => {
        const info = actionMap[a] || { text: a, color: "default" };
        return (
          <Tag color={info.color} style={{ borderRadius: 10 }}>
            {info.text}
          </Tag>
        );
      },
    },
    {
      title: "资源类型",
      dataIndex: "resource_type",
      width: 100,
      render: (t: string) => {
        const info = resourceTypeMap[t] || { text: t, color: "default" };
        return (
          <Tag color={info.color} style={{ borderRadius: 10 }}>
            {info.text}
          </Tag>
        );
      },
    },
    {
      title: "资源ID",
      dataIndex: "resource_id",
      width: 180,
      render: (v: string) => (
        <Text style={{ fontFamily: "monospace", fontSize: 12 }}>{v || "-"}</Text>
      ),
    },
    {
      title: "IP 地址",
      dataIndex: "ip_address",
      width: 130,
      render: (v: string) => (
        <Text style={{ fontFamily: "monospace", fontSize: 12 }}>{v || "-"}</Text>
      ),
    },
    {
      title: "操作时间",
      dataIndex: "created_at",
      width: 170,
      render: (d: string) => (
        <Text style={{ fontSize: 12 }}>{dayjs(d).format("YYYY-MM-DD HH:mm:ss")}</Text>
      ),
    },
    {
      title: "详情",
      key: "detail",
      width: 80,
      render: (_: any, r: any) => (
        <Button
          type="link"
          size="small"
          icon={<EyeOutlined />}
          onClick={() => setDetailLog(r)}
          style={{ padding: "0 4px" }}
        />
      ),
    },
  ];

  const actionOptions = Object.entries(actionMap).map(([v, { text }]) => ({
    value: v,
    label: text,
  }));
  const resourceTypeOptions = Object.entries(resourceTypeMap).map(([v, { text }]) => ({
    value: v,
    label: text,
  }));

  return (
    <div style={{ padding: 24, background: "#f0f2f5", minHeight: "100vh" }}>
      <div style={{ marginBottom: 24 }}>
        <Title level={4} style={{ margin: 0, display: "flex", alignItems: "center", gap: 8 }}>
          <AuditOutlined style={{ color: "#722ed1" }} />
          操作日志
        </Title>
        <Text type="secondary">记录所有标注、修改与审核操作的审计日志</Text>
      </div>

      {/* 筛选栏 */}
      <Card
        size="small"
        style={{ marginBottom: 16, borderRadius: 12 }}
        styles={{ body: { padding: "12px 16px" } }}
      >
        <Space wrap size={12}>
          <Input
            placeholder="按用户ID筛选"
            allowClear
            style={{ width: 200 }}
            onChange={(e) => {
              setUserFilter(e.target.value || undefined);
              setPage(1);
            }}
          />
          <Select
            placeholder="操作类型"
            allowClear
            style={{ width: 130 }}
            options={actionOptions}
            onChange={(v) => {
              setActionFilter(v);
              setPage(1);
            }}
          />
          <Select
            placeholder="资源类型"
            allowClear
            style={{ width: 120 }}
            options={resourceTypeOptions}
            onChange={(v) => {
              setResourceTypeFilter(v);
              setPage(1);
            }}
          />
          <DatePicker.RangePicker
            showTime
            onChange={(v) => {
              setRange(v as any);
              setPage(1);
            }}
          />
          <Button icon={<ReloadOutlined />} onClick={fetchLogs}>
            刷新
          </Button>
        </Space>
      </Card>

      {/* 日志列表 */}
      <Card style={{ borderRadius: 12, boxShadow: "0 2px 12px rgba(0,0,0,0.08)" }}>
        <Table
          columns={columns}
          dataSource={logs}
          rowKey="id"
          loading={loading}
          scroll={{ x: 1000 }}
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
            emptyText: <Empty description="暂无操作日志" image={Empty.PRESENTED_IMAGE_SIMPLE} />,
          }}
          size="middle"
        />
      </Card>

      {/* 详情抽屉 */}
      <Drawer
        title={
          <Space>
            <AuditOutlined style={{ color: "#722ed1" }} />
            操作日志详情
          </Space>
        }
        open={!!detailLog}
        onClose={() => setDetailLog(null)}
        width={480}
      >
        {detailLog && (
          <Descriptions column={1} size="small" bordered>
            <Descriptions.Item label="日志ID">
              <Text copyable style={{ fontFamily: "monospace", fontSize: 12 }}>
                {detailLog.id}
              </Text>
            </Descriptions.Item>
            <Descriptions.Item label="操作人">
              <Text style={{ fontFamily: "monospace", fontSize: 12 }}>
                {detailLog.user_id || "-"}
              </Text>
            </Descriptions.Item>
            <Descriptions.Item label="操作类型">
              <Tag color={actionMap[detailLog.action]?.color}>
                {actionMap[detailLog.action]?.text || detailLog.action}
              </Tag>
            </Descriptions.Item>
            <Descriptions.Item label="资源类型">{detailLog.resource_type}</Descriptions.Item>
            <Descriptions.Item label="资源ID">
              <Text style={{ fontFamily: "monospace", fontSize: 12 }}>
                {detailLog.resource_id || "-"}
              </Text>
            </Descriptions.Item>
            <Descriptions.Item label="IP 地址">{detailLog.ip_address || "-"}</Descriptions.Item>
            <Descriptions.Item label="操作时间">
              {dayjs(detailLog.created_at).format("YYYY-MM-DD HH:mm:ss")}
            </Descriptions.Item>
            <Descriptions.Item label="操作详情">
              <pre
                style={{ margin: 0, fontSize: 12, fontFamily: "monospace", whiteSpace: "pre-wrap" }}
              >
                {JSON.stringify(detailLog.details || {}, null, 2)}
              </pre>
            </Descriptions.Item>
          </Descriptions>
        )}
      </Drawer>
    </div>
  );
}
