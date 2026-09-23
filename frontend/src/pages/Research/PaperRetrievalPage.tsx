import { useState } from "react";
import {
  Card,
  Button,
  Input,
  Typography,
  Space,
  Tag,
  Table,
  Segmented,
  message,
  Empty,
  Alert,
} from "antd";
import { SearchOutlined, BulbOutlined, DownloadOutlined } from "@ant-design/icons";
import { paperRetrievalApi } from "@api/modules";
import type { PaperResult, PaperRecommendation } from "@/types";

const { Title, Text, Paragraph } = Typography;

export default function PaperRetrievalPage() {
  const [query, setQuery] = useState("graph neural network");
  const [source, setSource] = useState<string | number>("arxiv");
  const [maxResults, setMaxResults] = useState(10);
  const [searchLoading, setSearchLoading] = useState(false);
  const [results, setResults] = useState<PaperResult[]>([]);
  const [searchError, setSearchError] = useState<string | null>(null);
  const [localRefs, setLocalRefs] = useState("");
  const [recLoading, setRecLoading] = useState(false);
  const [recommendations, setRecommendations] = useState<PaperRecommendation[]>([]);
  const [ingesting, setIngesting] = useState<string | null>(null);

  const runSearch = async () => {
    if (!query.trim()) {
      message.warning("请输入检索关键词");
      return;
    }
    setSearchLoading(true);
    setSearchError(null);
    try {
      const res = await paperRetrievalApi.search({
        query,
        source: source as string,
        max_results: maxResults,
      });
      setResults(res.results || []);
      setSearchError(res.error || null);
    } finally {
      setSearchLoading(false);
    }
  };

  const runRecommend = async () => {
    if (results.length === 0) {
      message.warning("请先检索获取候选论文");
      return;
    }
    let refs: Record<string, any>[] = [];
    if (localRefs.trim()) {
      try {
        refs = JSON.parse(localRefs);
      } catch {
        message.error("本地文献库需为 JSON 数组");
        return;
      }
    }
    setRecLoading(true);
    try {
      const res = await paperRetrievalApi.recommend({
        local_references: refs,
        candidates: results,
      });
      setRecommendations(res.recommendations || []);
    } finally {
      setRecLoading(false);
    }
  };

  const runIngest = async (rec: PaperResult) => {
    const key = rec.arxiv_id || rec.pubmed_id || rec.title || "";
    setIngesting(key);
    try {
      const res = await paperRetrievalApi.downloadAndIngest({
        result: {
          source: rec.source,
          arxiv_id: rec.arxiv_id,
          pubmed_id: rec.pubmed_id,
          title: rec.title,
        },
      });
      if (res.ingested) {
        message.success(
          `已入库：文档 ${res.document_id?.slice(0, 8)}…，解析 ${res.parsing?.status}`,
        );
      } else {
        message.warning(`下载入库失败（已降级）：${res.download?.error || "无直接 PDF"}`);
      }
    } catch {
      message.error("入库请求失败，请检查权限/网络");
    } finally {
      setIngesting(null);
    }
  };

  const columns = [
    {
      title: "标题",
      dataIndex: "title",
      ellipsis: true,
      render: (v: string) => <Text strong>{v || "-"}</Text>,
    },
    {
      title: "作者",
      dataIndex: "authors",
      width: 220,
      ellipsis: true,
      render: (a: string[]) => <Text type="secondary">{(a || []).join(", ") || "-"}</Text>,
    },
    {
      title: "来源",
      dataIndex: "source",
      width: 90,
      render: (s: string) => <Tag color={s === "arxiv" ? "red" : "blue"}>{s}</Tag>,
    },
    {
      title: "发布时间",
      dataIndex: "published",
      width: 150,
      render: (v: string) => v?.slice(0, 10) || "-",
    },
    {
      title: "ID",
      dataIndex: "arxiv_id",
      width: 140,
      render: (_: any, r: PaperResult) => r.arxiv_id || r.pubmed_id || "-",
    },
    {
      title: "操作",
      key: "action",
      width: 130,
      fixed: "right" as const,
      render: (_: any, r: PaperResult) => {
        const key = r.arxiv_id || r.pubmed_id || r.title || "";
        return (
          <Button
            type="link"
            icon={<DownloadOutlined />}
            loading={ingesting === key}
            disabled={!r.arxiv_id && !r.pubmed_id}
            onClick={() => runIngest(r)}
          >
            下载入库
          </Button>
        );
      },
    },
  ];

  const recColumns = [
    {
      title: "标题",
      dataIndex: "title",
      ellipsis: true,
      render: (v: string) => <Text strong>{v || "-"}</Text>,
    },
    { title: "来源", dataIndex: "source", width: 90, render: (s: string) => <Tag>{s || "-"}</Tag> },
    { title: "相关度", dataIndex: "score", width: 100, render: (v: number) => v?.toFixed(3) },
    {
      title: "推荐理由",
      dataIndex: "reason",
      width: 240,
      render: (v: string) => <Text type="secondary">{v}</Text>,
    },
  ];

  return (
    <div style={{ padding: 24, background: "#f0f2f5", minHeight: "100vh" }}>
      <div style={{ marginBottom: 24 }}>
        <Title level={4} style={{ margin: 0, display: "flex", alignItems: "center", gap: 8 }}>
          <SearchOutlined style={{ color: "#eb2f96" }} />
          论文检索与推荐
        </Title>
        <Text type="secondary">
          调用 arXiv / PubMed 公开接口检索论文，并基于本地文献库做相关性推荐
        </Text>
      </div>

      <Card size="small" title="论文检索" style={{ marginBottom: 16, borderRadius: 12 }}>
        <Space wrap>
          <Input
            style={{ width: 360 }}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onPressEnter={runSearch}
            placeholder="检索关键词"
          />
          <Segmented
            value={source}
            onChange={setSource}
            options={[
              { label: "arXiv", value: "arxiv" },
              { label: "PubMed", value: "pubmed" },
            ]}
          />
          <Space.Compact>
            <Input defaultValue="数量" disabled style={{ width: 64, textAlign: "center" }} />
            <Input
              type="number"
              min={1}
              max={50}
              value={maxResults}
              onChange={(e) => setMaxResults(Number(e.target.value))}
              style={{ width: 90 }}
            />
          </Space.Compact>
          <Button
            type="primary"
            icon={<SearchOutlined />}
            onClick={runSearch}
            loading={searchLoading}
          >
            检索
          </Button>
        </Space>
        {searchError && (
          <Alert
            style={{ marginTop: 12 }}
            type="warning"
            showIcon
            message={searchError}
            description="网络请求失败（本地环境可能无法访问公开接口），接口已做降级处理。"
          />
        )}
      </Card>

      <Card
        title={`检索结果（${results.length}）`}
        style={{ borderRadius: 12, boxShadow: "0 2px 12px rgba(0,0,0,0.08)" }}
      >
        <Table
          columns={columns}
          dataSource={results}
          rowKey={(r) => r.arxiv_id || r.pubmed_id || r.title}
          loading={searchLoading}
          pagination={{ pageSize: 10, showTotal: (t) => `共 ${t} 条` }}
          scroll={{ x: 900 }}
          locale={{
            emptyText: <Empty description="暂无检索结果" image={Empty.PRESENTED_IMAGE_SIMPLE} />,
          }}
          expandable={{
            expandedRowRender: (r: PaperResult) => (
              <Paragraph type="secondary" style={{ margin: 0 }}>
                {r.summary || "（无摘要）"}
              </Paragraph>
            ),
          }}
        />
      </Card>

      <Card size="small" title="相关性推荐" style={{ marginTop: 16, borderRadius: 12 }}>
        <Input.TextArea
          rows={3}
          value={localRefs}
          onChange={(e) => setLocalRefs(e.target.value)}
          placeholder='本地文献库 JSON 数组（可选），如 [{"title":"Attention Is All You Need","journal":"NIPS"}]'
        />
        <Button
          type="primary"
          icon={<BulbOutlined />}
          onClick={runRecommend}
          loading={recLoading}
          style={{ marginTop: 12 }}
        >
          生成推荐
        </Button>
        {recommendations.length > 0 && (
          <Table
            style={{ marginTop: 12 }}
            columns={recColumns}
            dataSource={recommendations}
            rowKey={(r) => r.title || r.source || r.reason}
            pagination={false}
            size="small"
          />
        )}
      </Card>
    </div>
  );
}
