import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import {
  Card,
  Tabs,
  Select,
  Button,
  Table,
  Tag,
  Typography,
  Space,
  Empty,
  Tooltip,
  Row,
  Col,
  Statistic,
  InputNumber,
  Input,
} from "antd";
import { BulbOutlined, RocketOutlined, TableOutlined, FilterOutlined } from "@ant-design/icons";
import { documentApi, sourceAnchorApi, citationQualityApi, citationGraphApi } from "@api/modules";
import type {
  Document,
  CompareMatrixCell,
  CompareMatrixResult,
  CitationQualityRef,
  CitationQualityResult,
  FutureWorkIdea,
  FutureWorkResult,
} from "@/types";

const { Title, Text, Paragraph } = Typography;

// 引用含金量档位 → 展示色与中文名
const LABEL_META: Record<string, { color: string; text: string }> = {
  core: { color: "red", text: "核心支撑" },
  supporting: { color: "blue", text: "一般支撑" },
  perfunctory: { color: "default", text: "应付式" },
};

export default function ResearchInsightsPage() {
  const [searchParams] = useSearchParams();
  const [docs, setDocs] = useState<Document[]>([]);
  // 支持 ?docs=id1,id2 预选文献（便于从文档页/引用图谱页深链跳转）
  const [selected, setSelected] = useState<string[]>(() =>
    (searchParams.get("docs") || "").split(",").filter(Boolean),
  );

  // 步骤 19：对比矩阵
  const [matrixLoading, setMatrixLoading] = useState(false);
  const [matrix, setMatrix] = useState<CompareMatrixResult | null>(null);

  // 步骤 20：引用含金量
  const [qualityLoading, setQualityLoading] = useState(false);
  const [quality, setQuality] = useState<CitationQualityResult | null>(null);

  // 步骤 22：前沿探索
  const [domain, setDomain] = useState("");
  const [minYear, setMinYear] = useState<number | null>(null);
  const [maxYear, setMaxYear] = useState<number | null>(null);
  const [fwLoading, setFwLoading] = useState(false);
  const [futureWork, setFutureWork] = useState<FutureWorkResult | null>(null);

  useEffect(() => {
    documentApi
      .getList({ page: 1, page_size: 200 })
      .then((res) => setDocs(res.items || []))
      .catch(() => setDocs([]));
  }, []);

  const docOptions = docs.map((d) => ({ label: d.title || d.id, value: d.id }));

  const runMatrix = async () => {
    setMatrixLoading(true);
    try {
      const res = await sourceAnchorApi.compareMatrix({
        documents: selected.map((id) => ({ document_id: id })),
      });
      setMatrix(res);
    } catch {
      // 错误提示由 axios 拦截器统一处理
    } finally {
      setMatrixLoading(false);
    }
  };

  const runQuality = async () => {
    setQualityLoading(true);
    try {
      const res = await citationQualityApi.score(selected);
      setQuality(res);
    } catch {
      // 错误提示由 axios 拦截器统一处理
    } finally {
      setQualityLoading(false);
    }
  };

  const runFutureWork = async () => {
    setFwLoading(true);
    try {
      const res = await citationGraphApi.futureWork({
        domain: domain || undefined,
        min_year: minYear ?? undefined,
        max_year: maxYear ?? undefined,
      });
      setFutureWork(res);
    } catch {
      // 错误提示由 axios 拦截器统一处理
    } finally {
      setFwLoading(false);
    }
  };

  // ── 步骤 19：矩阵列（维度 + 每篇文献一列） ──────────────────────────
  const matrixColumns = matrix
    ? [
        { title: "演化维度", dataIndex: "dimension", key: "dimension", width: 170 },
        ...matrix.document_columns.map((c, i) => ({
          title: c.title || c.document_id.slice(0, 10),
          dataIndex: `doc_${i}`,
          key: `doc_${i}`,
          render: (cell: CompareMatrixCell) => {
            if (!cell) return "-";
            if (!cell.anchored) {
              return (
                <Tooltip title={cell.note || "无锚点，不出结论"}>
                  <Tag color="default">无锚点</Tag>
                </Tooltip>
              );
            }
            return (
              <Tooltip title={cell.anchors?.[0]?.snippet || ""}>
                <Text>{cell.value}</Text>
                {cell.anchors?.[0]?.page != null && (
                  <Tag color="cyan" style={{ marginLeft: 6 }}>
                    第 {cell.anchors[0].page} 页
                  </Tag>
                )}
              </Tooltip>
            );
          },
        })),
      ]
    : [];

  const matrixRows = (matrix?.rows || []).map((r, ri) => {
    const row: Record<string, any> = { key: `${ri}-${r.dimension}`, dimension: r.dimension };
    r.cells.forEach((cell, ci) => {
      row[`doc_${ci}`] = cell;
    });
    return row;
  });

  // ── 步骤 20：扁平化每条参考文献 ────────────────────────────────────
  const qualityRows = (quality?.documents || []).flatMap((doc) =>
    (doc.refs || []).map((ref, idx) => ({
      key: `${doc.document_id}-${ref.index ?? idx}`,
      docTitle: doc.title || doc.document_id.slice(0, 10),
      ...ref,
    })),
  );

  const signalText = (ref: CitationQualityRef) => {
    const s = ref.signals || [];
    const parts: string[] = [];
    const pos = s.find((x) => x.signal === "position");
    if (pos?.detail) parts.push(`位置:${pos.detail}`);
    const occ = s.find((x) => x.signal === "occurrences");
    if (occ?.detail) parts.push(String(occ.detail));
    const con = s.find((x) => x.signal === "conclusion");
    parts.push(con?.hit ? "含结论表述" : "无结论表述");
    const edge = s.find((x) => x.signal === "cites_edge");
    parts.push(edge?.hit ? "有 CITES 边" : "无 CITES 边");
    return parts.join(" · ");
  };

  const fwIdeaColumns = [
    { title: "提出文献", dataIndex: "title", key: "title", ellipsis: true },
    { title: "年份", dataIndex: "year", key: "year", width: 80 },
    { title: "Future Work 方向", dataIndex: "idea", key: "idea", ellipsis: true },
    {
      title: "置信度",
      dataIndex: "confidence",
      key: "confidence",
      width: 110,
      render: (v: number) => <Tag color={v >= 0.75 ? "green" : "orange"}>{v}</Tag>,
    },
    {
      title: "依据",
      key: "evidence",
      width: 220,
      render: (_: any, r: FutureWorkIdea) => (
        <Text type="secondary" style={{ fontSize: 12 }}>
          {r.reason}
        </Text>
      ),
    },
  ];

  const tabItems = [
    {
      key: "matrix",
      label: (
        <span>
          <TableOutlined /> 跨文献对比矩阵
        </span>
      ),
      children: (
        <>
          <Space style={{ marginBottom: 12 }}>
            <Button
              type="primary"
              icon={<TableOutlined />}
              onClick={runMatrix}
              loading={matrixLoading}
              disabled={selected.length < 1}
            >
              构建对比矩阵
            </Button>
            <Text type="secondary">维度 ≥6 行、单元必带出处锚点；无锚点不出结论。</Text>
          </Space>
          {!matrix && (
            <Empty description="选择至少 1 篇文献后构建对比矩阵" style={{ marginTop: 48 }} />
          )}
          {matrix && (
            <>
              <Space wrap style={{ marginBottom: 12 }}>
                <Tag color="purple">维度：{matrix.dimension_count}</Tag>
                <Tag color="blue">文献：{matrix.document_count}</Tag>
                <Tag color="cyan">锚点覆盖率：{matrix.anchor_coverage.coverage_pct}%</Tag>
                <Tag>后端：{matrix.backend}</Tag>
              </Space>
              {matrix.insight && (
                <Card size="small" title="演化洞察" style={{ marginBottom: 12, borderRadius: 8 }}>
                  <Tag color={matrix.insight.backend === "llm" ? "gold" : "default"}>
                    {matrix.insight.backend === "llm" ? "LLM 生成" : "规则模板"}
                  </Tag>
                  <Paragraph style={{ marginTop: 8 }}>{matrix.insight.insight}</Paragraph>
                  {matrix.insight.note && (
                    <Text type="secondary" style={{ fontSize: 12 }}>
                      {matrix.insight.note}
                    </Text>
                  )}
                </Card>
              )}
              <Table
                columns={matrixColumns}
                dataSource={matrixRows}
                rowKey="key"
                pagination={false}
                size="small"
                scroll={{ x: "max-content" }}
              />
            </>
          )}
        </>
      ),
    },
    {
      key: "quality",
      label: (
        <span>
          <BulbOutlined /> 引用含金量
        </span>
      ),
      children: (
        <>
          <Space style={{ marginBottom: 12 }}>
            <Button
              type="primary"
              icon={<BulbOutlined />}
              onClick={runQuality}
              loading={qualityLoading}
              disabled={selected.length < 1}
            >
              评估引用含金量
            </Button>
            <Text type="secondary">识别应付式引用（仅罗列、无实质承接），只打标不删数据。</Text>
          </Space>
          {!quality && (
            <Empty description="选择文献后评估其参考文献含金量" style={{ marginTop: 48 }} />
          )}
          {quality && (
            <>
              <Row gutter={16} style={{ marginBottom: 16 }}>
                <Col span={6}>
                  <Card size="small">
                    <Statistic title="文献数" value={quality.document_count} />
                  </Card>
                </Col>
                <Col span={6}>
                  <Card size="small">
                    <Statistic title="参考文献总数" value={quality.total_refs} />
                  </Card>
                </Col>
                <Col span={6}>
                  <Card size="small">
                    <Statistic
                      title="核心支撑"
                      value={quality.core_count}
                      valueStyle={{ color: "#cf1322" }}
                    />
                  </Card>
                </Col>
                <Col span={6}>
                  <Card size="small">
                    <Statistic
                      title="应付式引用"
                      value={quality.perfunctory_count}
                      valueStyle={{ color: "#8c8c8c" }}
                    />
                  </Card>
                </Col>
              </Row>
              <Table
                columns={[
                  { title: "所属文献", dataIndex: "docTitle", key: "docTitle", ellipsis: true },
                  { title: "序号", dataIndex: "index", key: "index", width: 70 },
                  { title: "参考文献标题", dataIndex: "title", key: "title", ellipsis: true },
                  {
                    title: "分数",
                    dataIndex: "score",
                    key: "score",
                    width: 90,
                    render: (v: number) => v?.toFixed(3),
                  },
                  {
                    title: "档位",
                    dataIndex: "label",
                    key: "label",
                    width: 110,
                    render: (v: string) => (
                      <Tag color={LABEL_META[v]?.color || "default"}>
                        {LABEL_META[v]?.text || v}
                      </Tag>
                    ),
                  },
                  {
                    title: "可解释信号",
                    key: "signals",
                    width: 300,
                    render: (_: any, r: CitationQualityRef) => (
                      <Text type="secondary" style={{ fontSize: 12 }}>
                        {signalText(r)}
                      </Text>
                    ),
                  },
                ]}
                dataSource={qualityRows}
                rowKey="key"
                size="small"
                pagination={{ pageSize: 10 }}
              />
            </>
          )}
        </>
      ),
    },
    {
      key: "future-work",
      label: (
        <span>
          <RocketOutlined /> 前沿探索
        </span>
      ),
      children: (
        <>
          <Space wrap style={{ marginBottom: 12 }}>
            <Input
              placeholder="领域关键词（标题/摘要/关键词）"
              value={domain}
              onChange={(e) => setDomain(e.target.value)}
              style={{ width: 260 }}
              allowClear
            />
            <InputNumber
              placeholder="起始年"
              value={minYear ?? undefined}
              onChange={(v) => setMinYear(v ?? null)}
              style={{ width: 110 }}
            />
            <InputNumber
              placeholder="截止年"
              value={maxYear ?? undefined}
              onChange={(v) => setMaxYear(v ?? null)}
              style={{ width: 110 }}
            />
            <Button
              type="primary"
              icon={<FilterOutlined />}
              onClick={runFutureWork}
              loading={fwLoading}
            >
              扫描前沿方向
            </Button>
          </Space>
          {!futureWork && (
            <Empty description="扫描语料库 Future Work，排除已被后续论文解决的旧 idea" />
          )}
          {futureWork && (
            <>
              <Space wrap style={{ marginBottom: 12 }}>
                <Tag color="green">待探索：{futureWork.candidate_count}</Tag>
                <Tag color="default">已被解决：{futureWork.excluded_count}</Tag>
                <Tag color="blue">idea 总数：{futureWork.idea_count}</Tag>
                {futureWork.filtered?.applied_document_count != null && (
                  <Tag>命中文献：{futureWork.filtered.applied_document_count}</Tag>
                )}
              </Space>
              <Space wrap style={{ marginBottom: 16 }}>
                {futureWork.time_buckets.map((t) => (
                  <Tag key={t.year} color="cyan">
                    {t.year}：{t.count} 篇
                  </Tag>
                ))}
              </Space>
              <Card
                size="small"
                title="待探索方向（未被后续论文解决）"
                style={{ marginBottom: 16, borderRadius: 8 }}
              >
                <Table
                  columns={fwIdeaColumns}
                  dataSource={futureWork.candidates}
                  rowKey={(r) => `${r.document_id}-${r.idea?.slice(0, 16)}`}
                  size="small"
                  pagination={{ pageSize: 10 }}
                  locale={{
                    emptyText: (
                      <Empty
                        description="无语料或无可探索方向"
                        image={Empty.PRESENTED_IMAGE_SIMPLE}
                      />
                    ),
                  }}
                />
              </Card>
              <Card size="small" title="已被后续论文解决（排除组）" style={{ borderRadius: 8 }}>
                <Table
                  columns={fwIdeaColumns}
                  dataSource={futureWork.excluded}
                  rowKey={(r) => `${r.document_id}-${r.idea?.slice(0, 16)}`}
                  size="small"
                  pagination={{ pageSize: 10 }}
                  locale={{
                    emptyText: (
                      <Empty description="暂无已解决 idea" image={Empty.PRESENTED_IMAGE_SIMPLE} />
                    ),
                  }}
                />
              </Card>
            </>
          )}
        </>
      ),
    },
  ];

  return (
    <div style={{ padding: 4 }}>
      <div style={{ marginBottom: 20 }}>
        <Title level={4} style={{ margin: 0, display: "flex", alignItems: "center", gap: 8 }}>
          <RocketOutlined style={{ color: "#722ed1" }} />
          研究洞察（需求对标补强）
        </Title>
        <Text type="secondary">
          跨文献结构化演进对比（步骤 19）· 引用含金量筛选（步骤 20）· Future Work 前沿探索（步骤
          22）
        </Text>
      </div>

      <Card size="small" title="文献选择" style={{ marginBottom: 16, borderRadius: 12 }}>
        <Select
          mode="multiple"
          showSearch
          placeholder="选择一篇或多篇文献"
          options={docOptions}
          value={selected}
          onChange={setSelected}
          style={{ width: "100%" }}
          optionFilterProp="label"
          maxTagCount="responsive"
        />
        <Text type="secondary" style={{ fontSize: 12 }}>
          共 {docs.length} 篇可选；对比矩阵建议选 2 篇以上。
        </Text>
      </Card>

      <Tabs items={tabItems} defaultActiveKey="matrix" />
    </div>
  );
}
