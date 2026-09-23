import { useMemo, useRef, useState } from "react";
import ForceGraph2D from "react-force-graph-2d";
import { Card, Button, Input, Typography, Space, Tag, Table, message, Empty } from "antd";
import { ApartmentOutlined, BulbOutlined } from "@ant-design/icons";
import { citationGraphApi } from "@api/modules";
import type { CitationNetwork, KeyPaper, SurveyResult } from "@/types";

const { Title, Text, Paragraph } = Typography;

const demoRefs = [
  { index: 1, title: "Attention Is All You Need", year: "2017", doi: "10.5555/1" },
  {
    index: 2,
    title: "Semi-Supervised Classification with Graph Convolutional Networks",
    year: "2017",
    doi: "10.5555/2",
  },
  { index: 3, title: "Graph Attention Networks", year: "2018", doi: "10.5555/3" },
  {
    index: 4,
    title: "BERT: Pre-training of Deep Bidirectional Transformers",
    year: "2019",
    doi: "10.5555/4",
  },
  {
    index: 5,
    title: "Deep Residual Learning for Image Recognition",
    year: "2016",
    doi: "10.5555/5",
  },
];

export default function CitationGraphPage() {
  const graphRef = useRef<any>();
  const [refsText, setRefsText] = useState(JSON.stringify(demoRefs, null, 2));
  const [loading, setLoading] = useState(false);
  const [network, setNetwork] = useState<CitationNetwork | null>(null);
  const [keyPapers, setKeyPapers] = useState<KeyPaper[]>([]);
  const [survey, setSurvey] = useState<SurveyResult | null>(null);

  const parseRefs = (): Record<string, any>[] | null => {
    try {
      const arr = JSON.parse(refsText);
      if (!Array.isArray(arr)) throw new Error("not array");
      return arr;
    } catch {
      message.error("参考文献需为 JSON 数组");
      return null;
    }
  };

  const run = async () => {
    const refs = parseRefs();
    if (!refs) return;
    setLoading(true);
    try {
      const net = await citationGraphApi.network(refs);
      setNetwork(net);
      const kp = await citationGraphApi.keyPapers(net);
      setKeyPapers(kp.key_papers || []);
      const sv = await citationGraphApi.survey({ references: refs });
      setSurvey(sv);
    } finally {
      setLoading(false);
    }
  };

  const graphData = useMemo(() => {
    if (!network) return { nodes: [], links: [] };
    return {
      nodes: network.nodes.map((n) => ({ id: n.id, label: n.label, year: n.year })),
      links: network.edges.map((e) => ({ source: e.source, target: e.target, type: e.type })),
    };
  }, [network]);

  const kpColumns = [
    {
      title: "排名",
      key: "rank",
      width: 60,
      render: (_: any, __: any, i: number) => (
        <Tag color={i < 3 ? "red" : "default"} style={{ fontWeight: 600 }}>
          {i + 1}
        </Tag>
      ),
    },
    {
      title: "文献",
      dataIndex: "label",
      ellipsis: true,
      render: (v: string) => <Text strong>{v || "-"}</Text>,
    },
    { title: "年份", dataIndex: "year", width: 70 },
    { title: "PageRank", dataIndex: "page_rank", width: 110, render: (v: number) => v?.toFixed(5) },
    { title: "介数", dataIndex: "betweenness", width: 110, render: (v: number) => v?.toFixed(5) },
  ];

  return (
    <div style={{ padding: 24, background: "#f0f2f5", minHeight: "100vh" }}>
      <div style={{ marginBottom: 24 }}>
        <Title level={4} style={{ margin: 0, display: "flex", alignItems: "center", gap: 8 }}>
          <ApartmentOutlined style={{ color: "#722ed1" }} />
          引用图谱挖掘与综述
        </Title>
        <Text type="secondary">PageRank + 介数中心性挖掘基石文献，规则模板生成综述</Text>
      </div>

      <Card size="small" title="参考文献输入" style={{ marginBottom: 16, borderRadius: 12 }}>
        <Input.TextArea rows={6} value={refsText} onChange={(e) => setRefsText(e.target.value)} />
        <Button
          type="primary"
          icon={<BulbOutlined />}
          onClick={run}
          loading={loading}
          style={{ marginTop: 12 }}
        >
          构建图谱
        </Button>
      </Card>

      {network && (
        <>
          <Card
            title="引用网络"
            style={{ borderRadius: 12, boxShadow: "0 2px 12px rgba(0,0,0,0.08)" }}
          >
            <Space wrap style={{ marginBottom: 12 }}>
              <Tag color="purple">节点：{network.node_count}</Tag>
              <Tag color="blue">边：{network.edge_count}</Tag>
            </Space>
            <div
              style={{ width: "100%", height: 420, border: "1px solid #f0f0f0", borderRadius: 8 }}
            >
              <ForceGraph2D
                ref={graphRef}
                graphData={graphData as any}
                nodeLabel="label"
                nodeColor={() => "#1890ff"}
                nodeRelSize={8}
                linkWidth={1.5}
                linkDirectionalParticles={2}
                linkDirectionalParticleWidth={2}
                backgroundColor="#fafafa"
                nodeCanvasObject={(node: any, ctx: any, globalScale: number) => {
                  const label = (node.label as string) || node.id;
                  const fontSize = 12 / globalScale;
                  ctx.font = `${fontSize}px Sans-Serif`;
                  ctx.fillStyle = "#1890ff";
                  ctx.beginPath();
                  ctx.arc(node.x, node.y, 8, 0, 2 * Math.PI);
                  ctx.fill();
                  ctx.textAlign = "center";
                  ctx.textBaseline = "middle";
                  ctx.fillStyle = "#fff";
                  ctx.fillText(label.slice(0, 3), node.x, node.y);
                  ctx.fillStyle = "#333";
                  ctx.fillText(label, node.x, node.y + 14);
                }}
              />
            </div>
          </Card>

          <Card
            title="基石文献（PageRank + 介数中心性）"
            style={{ marginTop: 16, borderRadius: 12 }}
          >
            <Table
              columns={kpColumns}
              dataSource={keyPapers}
              rowKey="id"
              pagination={false}
              size="middle"
              locale={{
                emptyText: <Empty description="暂无结果" image={Empty.PRESENTED_IMAGE_SIMPLE} />,
              }}
            />
          </Card>

          {survey && (
            <Card title="自动综述（规则模板）" style={{ marginTop: 16, borderRadius: 12 }}>
              <Paragraph>{survey.survey}</Paragraph>
              <Space wrap>
                {survey.timeline.map((t) => (
                  <Tag key={t.year} color="cyan">
                    {t.year}：{t.count} 篇
                  </Tag>
                ))}
              </Space>
            </Card>
          )}
        </>
      )}
    </div>
  );
}
