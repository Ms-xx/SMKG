import { useState, useEffect, useCallback } from "react";
import {
  Card,
  Table,
  Tag,
  Space,
  Button,
  Typography,
  Empty,
  message,
  Select,
  Progress,
} from "antd";
import { AimOutlined, ReloadOutlined, ArrowRightOutlined } from "@ant-design/icons";
import { useNavigate } from "react-router-dom";
import { activeLearningApi } from "@api/modules";
import type { ActiveLearningSuggestionItem } from "@/types";

const { Title, Text } = Typography;

const typeMap: Record<string, { text: string; color: string }> = {
  title: { text: "标题", color: "blue" },
  author: { text: "作者", color: "cyan" },
  abstract: { text: "摘要", color: "geekblue" },
  text: { text: "正文", color: "default" },
  table: { text: "表格", color: "purple" },
  figure: { text: "图表", color: "green" },
  formula: { text: "公式", color: "orange" },
};

function confidenceColor(v: number): string {
  if (v < 0.4) return "#ff4d4f";
  if (v < 0.7) return "#faad14";
  return "#52c41a";
}

export default function ActiveLearningPage() {
  const navigate = useNavigate();
  const [data, setData] = useState<ActiveLearningSuggestionItem[]>([]);
  const [total, setTotal] = useState(0);
  const [topK, setTopK] = useState(20);
  const [loading, setLoading] = useState(false);

  const fetchSuggest = useCallback(() => {
    setLoading(true);
    activeLearningApi
      .suggest({ top_k: topK })
      .then((res: any) => {
        const body = res.data || res;
        setData(body.results || []);
        setTotal(body.total || 0);
      })
      .catch(() => message.error("加载低置信度样本失败"))
      .finally(() => setLoading(false));
  }, [topK]);

  useEffect(() => {
    fetchSuggest();
  }, [fetchSuggest]);

  const columns = [
    {
      title: "排序",
      dataIndex: "rank",
      width: 60,
      align: "center" as const,
      render: (v: number) => (
        <Tag color={v <= 3 ? "red" : "default"} style={{ borderRadius: 12, fontWeight: 600 }}>
          {v}
        </Tag>
      ),
    },
    {
      title: "文档标题",
      dataIndex: "document_title",
      ellipsis: true,
      render: (v: string | null) => <Text strong>{v || "-"}</Text>,
    },
    {
      title: "元素类型",
      dataIndex: "element_type",
      width: 100,
      render: (t: string) => {
        const info = typeMap[t] || { text: t, color: "default" };
        return (
          <Tag color={info.color} style={{ borderRadius: 8 }}>
            {info.text}
          </Tag>
        );
      },
    },
    { title: "页码", dataIndex: "page_number", width: 70, align: "center" as const },
    {
      title: "置信度",
      dataIndex: "confidence",
      width: 160,
      render: (v: number) => {
        const percent = Math.round(v * 100);
        const color = confidenceColor(v);
        return (
          <Space>
            <Progress
              type="circle"
              percent={percent}
              size={28}
              strokeColor={color}
              format={() => `${percent}%`}
            />
            <Text type="secondary" style={{ fontSize: 12 }}>
              {v}
            </Text>
          </Space>
        );
      },
    },
    {
      title: "内容预览",
      dataIndex: "text",
      ellipsis: true,
      render: (v: string) => <Text type="secondary">{v || "-"}</Text>,
    },
    {
      title: "操作",
      key: "action",
      width: 110,
      render: (_: any, r: ActiveLearningSuggestionItem) => (
        <Button
          type="primary"
          size="small"
          icon={<ArrowRightOutlined />}
          onClick={() => navigate(`/annotation/${r.document_id}`)}
        >
          去标注
        </Button>
      ),
    },
  ];

  return (
    <div style={{ padding: 24, background: "#f0f2f5", minHeight: "100vh" }}>
      <div style={{ marginBottom: 24 }}>
        <Title level={4} style={{ margin: 0, display: "flex", alignItems: "center", gap: 8 }}>
          <AimOutlined style={{ color: "#eb2f96" }} />
          优先标注
        </Title>
        <Text type="secondary">基于低置信度的主动学习样本推送，越靠前越应优先标注</Text>
      </div>

      <Card
        size="small"
        style={{ marginBottom: 16, borderRadius: 12 }}
        styles={{ body: { padding: "12px 16px" } }}
      >
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <Space wrap size={12}>
            <Text type="secondary">推进数量</Text>
            <Select
              value={topK}
              style={{ width: 100 }}
              options={[10, 20, 50, 100].map((n) => ({ value: n, label: `Top ${n}` }))}
              onChange={setTopK}
            />
            <Text type="secondary" style={{ fontSize: 12 }}>
              待标注池共 {total} 条
            </Text>
          </Space>
          <Button icon={<ReloadOutlined />} onClick={fetchSuggest} loading={loading}>
            刷新
          </Button>
        </div>
      </Card>

      <Card style={{ borderRadius: 12, boxShadow: "0 2px 12px rgba(0,0,0,0.08)" }}>
        <Table
          columns={columns}
          dataSource={data}
          rowKey="element_id"
          loading={loading}
          pagination={{
            pageSize: 20,
            showTotal: (t: number) => `共 ${t} 条`,
            showSizeChanger: false,
          }}
          scroll={{ x: 980 }}
          locale={{
            emptyText: (
              <Empty
                description="暂无待标注样本，全部已标注完成"
                image={Empty.PRESENTED_IMAGE_SIMPLE}
              />
            ),
          }}
          size="middle"
        />
      </Card>
    </div>
  );
}
