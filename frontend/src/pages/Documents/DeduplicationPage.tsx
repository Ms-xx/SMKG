import { useState } from "react";
import {
  Card,
  Button,
  Input,
  Typography,
  Space,
  Tag,
  Table,
  Alert,
  message,
  Slider,
  Empty,
} from "antd";
import { CopyOutlined, ClusterOutlined, TeamOutlined } from "@ant-design/icons";
import { dedupApi } from "@api/modules";
import type { DedupCluster, DedupDetectResult } from "@/types";

const { Title, Text, Paragraph } = Typography;
const { TextArea } = Input;

const demoText = [
  "Attention Is All You Need (v1)",
  "Attention Is All You Need (arXiv 1706.03762v7)",
  "BERT: Pre-training of Deep Bidirectional Transformers",
  "Deep residual learning for image recognition",
].join("\n");

export default function DeduplicationPage() {
  const [text, setText] = useState(demoText);
  const [threshold, setThreshold] = useState(0.85);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<DedupDetectResult | null>(null);
  const [affText, setAffText] = useState("");
  const [affLoading, setAffLoading] = useState(false);
  const [affiliations, setAffiliations] = useState<string[]>([]);

  const runDetect = async () => {
    const lines = text
      .split("\n")
      .map((l) => l.trim())
      .filter(Boolean);
    if (lines.length < 2) {
      message.warning("请至少输入两行文档标题");
      return;
    }
    const documents = lines.map((title, i) => ({
      id: `doc-${i + 1}`,
      title,
      abstract: title,
    }));
    setLoading(true);
    try {
      const res = await dedupApi.detect({ documents, threshold });
      setResult(res);
    } finally {
      setLoading(false);
    }
  };

  const runAffiliations = async () => {
    if (!affText.trim()) {
      message.warning("请粘贴作者/通讯信息文本");
      return;
    }
    setAffLoading(true);
    try {
      const res = await dedupApi.affiliations(affText);
      setAffiliations(res.affiliations || []);
    } finally {
      setAffLoading(false);
    }
  };

  const clusterColumns = [
    {
      title: "相似簇",
      dataIndex: "size",
      width: 80,
      render: (v: number) => <Tag color="red">{v} 篇</Tag>,
    },
    {
      title: "文档版本",
      dataIndex: "documents",
      render: (docs: DedupCluster["documents"]) => (
        <Space direction="vertical" size={2}>
          {docs.map((d) => (
            <Text key={d.id} type={d.version ? "secondary" : undefined}>
              {d.title} {d.version && <Tag color="blue">{d.version}</Tag>}
            </Text>
          ))}
        </Space>
      ),
    },
    {
      title: "保留建议",
      dataIndex: "suggestion",
      width: 320,
      render: (s: DedupCluster["suggestion"]) => (
        <Space direction="vertical" size={2}>
          <Text strong>保留：{s.keep || "-"}</Text>
          <Text type="secondary" style={{ fontSize: 12 }}>
            {s.reason}
          </Text>
        </Space>
      ),
    },
  ];

  return (
    <div style={{ padding: 24, background: "#f0f2f5", minHeight: "100vh" }}>
      <div style={{ marginBottom: 24 }}>
        <Title level={4} style={{ margin: 0, display: "flex", alignItems: "center", gap: 8 }}>
          <CopyOutlined style={{ color: "#722ed1" }} />
          语义去重与版本管理
        </Title>
        <Text type="secondary">基于 SimHash 指纹识别同源论文的不同版本，给出保留建议</Text>
      </div>

      <Card size="small" title="文档集合" style={{ marginBottom: 16, borderRadius: 12 }}>
        <TextArea
          rows={5}
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="每行一篇文档标题（可含 arXiv 版本号，如 1706.03762v7）"
        />
        <div style={{ marginTop: 12, maxWidth: 360 }}>
          <Text type="secondary" style={{ fontSize: 12 }}>
            相似度阈值：{threshold.toFixed(2)}
          </Text>
          <Slider min={0.5} max={0.99} step={0.01} value={threshold} onChange={setThreshold} />
        </div>
        <Button type="primary" icon={<ClusterOutlined />} onClick={runDetect} loading={loading}>
          检测重复
        </Button>
      </Card>

      {result && (
        <Card
          title="检测结果"
          style={{ borderRadius: 12, boxShadow: "0 2px 12px rgba(0,0,0,0.08)" }}
        >
          <Space wrap style={{ marginBottom: 16 }}>
            <Tag color="purple">后端：{result.backend}</Tag>
            <Tag>文档总数：{result.total_documents}</Tag>
            <Tag color={result.cluster_count > 0 ? "red" : "green"}>
              相似簇：{result.cluster_count}
            </Tag>
            <Tag>相似对：{result.duplicate_pairs.length}</Tag>
          </Space>
          {result.cluster_count === 0 ? (
            <Empty description="未发现语义重复的文档" image={Empty.PRESENTED_IMAGE_SIMPLE} />
          ) : (
            <Table
              columns={clusterColumns}
              dataSource={result.clusters}
              rowKey={(r) => r.document_ids.join("-")}
              pagination={false}
              size="middle"
            />
          )}
        </Card>
      )}

      <Card size="small" title="作者机构抽取" style={{ marginTop: 16, borderRadius: 12 }}>
        <TextArea
          rows={4}
          value={affText}
          onChange={(e) => setAffText(e.target.value)}
          placeholder="粘贴作者通讯信息，如：John Doe, Department of Computer Science, MIT (jdoe@mit.edu)"
        />
        <Button
          type="primary"
          icon={<TeamOutlined />}
          onClick={runAffiliations}
          loading={affLoading}
          style={{ marginTop: 12 }}
        >
          抽取机构
        </Button>
        {affiliations.length > 0 && (
          <Paragraph style={{ marginTop: 12 }}>
            {affiliations.map((a) => (
              <Tag key={a} color="geekblue" style={{ marginBottom: 4 }}>
                {a}
              </Tag>
            ))}
          </Paragraph>
        )}
        {affiliations.length === 0 && affText && !affLoading && (
          <Alert style={{ marginTop: 12 }} type="info" message="未识别到机构信息" showIcon />
        )}
      </Card>
    </div>
  );
}
