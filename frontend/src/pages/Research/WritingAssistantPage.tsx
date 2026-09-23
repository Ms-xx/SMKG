import { useState } from "react";
import { Card, Button, Input, Typography, Segmented, Space, Tag, message, List, Empty } from "antd";
import {
  EditOutlined,
  ApartmentOutlined,
  LineChartOutlined,
  CopyOutlined,
  TranslationOutlined,
  ThunderboltOutlined,
} from "@ant-design/icons";
import { writingAssistantApi } from "@api/modules";
import type { OutlineResult } from "@/types";

const { Title, Text, Paragraph } = Typography;

const defaultCsv = "Method,Accuracy\nTransformer,93.5\nRNN,88.2\nCNN,90.4\nGNN,91.7";

const defaultNodes = ["Data", "Preprocess", "Model", "Evaluate"];
const defaultEdges = [
  [0, 1],
  [1, 2],
  [2, 3],
  [0, 2],
];

export default function WritingAssistantPage() {
  const [idea, setIdea] = useState("基于图神经网络的科学文献知识图谱构建");
  const [refsText, setRefsText] = useState(
    '[{"index":1,"title":"Attention Is All You Need","year":"2017"},' +
      '{"index":2,"title":"Semi-Supervised Classification with Graph Convolutional Networks","year":"2017"}]',
  );
  const [outline, setOutline] = useState<OutlineResult | null>(null);
  const [outlineLoading, setOutlineLoading] = useState(false);

  const [diagramType, setDiagramType] = useState<string | number>("mermaid");
  const [script, setScript] = useState("");
  const [diagramLoading, setDiagramLoading] = useState(false);

  const [csvText, setCsvText] = useState(defaultCsv);
  const [chartType, setChartType] = useState<string | number>("bar");
  const [svg, setSvg] = useState("");
  const [chartLoading, setChartLoading] = useState(false);

  const runOutline = async () => {
    if (!idea.trim()) {
      message.warning("请输入研究主题");
      return;
    }
    let refs: Record<string, any>[] = [];
    if (refsText.trim()) {
      try {
        refs = JSON.parse(refsText);
      } catch {
        message.error("参考文献需为 JSON 数组");
        return;
      }
    }
    setOutlineLoading(true);
    try {
      setOutline(await writingAssistantApi.outline({ idea, references: refs }));
    } finally {
      setOutlineLoading(false);
    }
  };

  const runDiagram = async () => {
    setDiagramLoading(true);
    try {
      const res = await writingAssistantApi.diagram({
        diagram_type: diagramType as string,
        spec: { title: "System Architecture", nodes: defaultNodes, edges: defaultEdges },
      });
      setScript(res.script);
    } finally {
      setDiagramLoading(false);
    }
  };

  const runChart = async () => {
    if (!csvText.trim()) {
      message.warning("请输入 CSV 数据");
      return;
    }
    setChartLoading(true);
    try {
      const res = await writingAssistantApi.csvChart({
        csv_text: csvText,
        chart_type: chartType as string,
      });
      setSvg(res.svg || "");
      if (res.error) message.warning(res.error);
    } finally {
      setChartLoading(false);
    }
  };

  const copyScript = async () => {
    if (!script) return;
    await navigator.clipboard.writeText(script);
    message.success("已复制脚本");
  };

  const [translateText, setTranslateText] = useState(
    "Graph neural networks enable materials property prediction.",
  );
  const [translateTarget, setTranslateTarget] = useState<string | number>("zh");
  const [translated, setTranslated] = useState<{
    backend: string;
    text: string;
    note?: string;
  } | null>(null);
  const [translateLoading, setTranslateLoading] = useState(false);

  const [llmPrompt, setLlmPrompt] = useState("写一段关于能源材料研究的中文学术引言。");
  const [llmRes, setLlmRes] = useState<{ backend: string; content: string; note?: string } | null>(
    null,
  );
  const [llmLoading, setLlmLoading] = useState(false);

  const runTranslate = async () => {
    if (!translateText.trim()) {
      message.warning("请输入待翻译内容");
      return;
    }
    setTranslateLoading(true);
    try {
      const res = await writingAssistantApi.translate({
        text: translateText,
        target: translateTarget as string,
      });
      setTranslated(res);
      if (res.note) message.warning(res.note);
    } finally {
      setTranslateLoading(false);
    }
  };

  const runLlm = async () => {
    if (!llmPrompt.trim()) {
      message.warning("请输入写作提示词");
      return;
    }
    setLlmLoading(true);
    try {
      const res = await writingAssistantApi.llmGenerate({ prompt: llmPrompt });
      setLlmRes(res);
      if (res.note) message.warning(res.note);
    } finally {
      setLlmLoading(false);
    }
  };

  return (
    <div style={{ padding: 24, background: "#f0f2f5", minHeight: "100vh" }}>
      <div style={{ marginBottom: 24 }}>
        <Title level={4} style={{ margin: 0, display: "flex", alignItems: "center", gap: 8 }}>
          <EditOutlined style={{ color: "#13c2c2" }} />
          写作辅助与可视化 Copilot
        </Title>
        <Text type="secondary">论文框架生成（无幻觉）、图表脚本、CSV 零依赖 SVG 可视化</Text>
      </div>

      <Card size="small" title="论文框架生成" style={{ marginBottom: 16, borderRadius: 12 }}>
        <Input
          value={idea}
          onChange={(e) => setIdea(e.target.value)}
          placeholder="研究主题 / 论文 idea"
          style={{ marginBottom: 12 }}
        />
        <Input.TextArea
          rows={3}
          value={refsText}
          onChange={(e) => setRefsText(e.target.value)}
          placeholder="参考文献 JSON 数组（真实条目，仅回显不编造）"
        />
        <Button
          type="primary"
          onClick={runOutline}
          loading={outlineLoading}
          style={{ marginTop: 12 }}
        >
          生成框架
        </Button>
        {outline && (
          <div style={{ marginTop: 16 }}>
            <Tag color="cyan">后端：{outline.backend}</Tag>
            <Tag>参考文献 {outline.reference_count} 条</Tag>
            <List
              style={{ marginTop: 12 }}
              dataSource={outline.sections}
              renderItem={(s) => (
                <List.Item>
                  <List.Item.Meta
                    title={<Text strong>{s.title}</Text>}
                    description={<Text type="secondary">{s.content}</Text>}
                  />
                </List.Item>
              )}
            />
            <Paragraph type="secondary" style={{ fontSize: 12, marginTop: 8 }}>
              {outline.note}
            </Paragraph>
          </div>
        )}
      </Card>

      <Card size="small" title="架构图脚本" style={{ marginBottom: 16, borderRadius: 12 }}>
        <Space wrap>
          <Segmented
            value={diagramType}
            onChange={setDiagramType}
            options={[
              { label: "Mermaid", value: "mermaid" },
              { label: "Graphviz", value: "graphviz" },
              { label: "TikZ", value: "tikz" },
              { label: "Matplotlib", value: "matplotlib" },
            ]}
          />
          <Button icon={<ApartmentOutlined />} onClick={runDiagram} loading={diagramLoading}>
            生成脚本
          </Button>
          {script && (
            <Button icon={<CopyOutlined />} onClick={copyScript}>
              复制
            </Button>
          )}
        </Space>
        {script && (
          <pre
            style={{
              marginTop: 12,
              padding: 12,
              background: "#fafafa",
              border: "1px solid #f0f0f0",
              borderRadius: 8,
              fontSize: 12,
              overflow: "auto",
            }}
          >
            {script}
          </pre>
        )}
      </Card>

      <Card size="small" title="CSV 可视化" style={{ borderRadius: 12 }}>
        <Input.TextArea rows={4} value={csvText} onChange={(e) => setCsvText(e.target.value)} />
        <Space wrap style={{ marginTop: 12 }}>
          <Segmented
            value={chartType}
            onChange={setChartType}
            options={[
              { label: "柱状", value: "bar" },
              { label: "折线", value: "line" },
              { label: "雷达", value: "radar" },
              { label: "表格", value: "table" },
            ]}
          />
          <Button icon={<LineChartOutlined />} onClick={runChart} loading={chartLoading}>
            生成图表
          </Button>
        </Space>
        {svg ? (
          <div
            style={{ marginTop: 16, background: "#fff", borderRadius: 8, overflow: "auto" }}
            dangerouslySetInnerHTML={{ __html: svg }}
          />
        ) : (
          <Empty
            style={{ marginTop: 16 }}
            description="生成后将在此预览 SVG 图表"
            image={Empty.PRESENTED_IMAGE_SIMPLE}
          />
        )}
      </Card>

      <Card size="small" title="中英翻译 + LLM 生成" style={{ borderRadius: 12 }}>
        <Space wrap style={{ marginBottom: 12 }}>
          <Segmented
            value={translateTarget}
            onChange={setTranslateTarget}
            options={[
              { label: "英 → 中", value: "zh" },
              { label: "中 → 英", value: "en" },
            ]}
          />
        </Space>
        <Input.TextArea
          rows={2}
          value={translateText}
          onChange={(e) => setTranslateText(e.target.value)}
          placeholder="待翻译文本"
        />
        <Button
          icon={<TranslationOutlined />}
          onClick={runTranslate}
          loading={translateLoading}
          style={{ marginTop: 12 }}
        >
          翻译
        </Button>
        {translated && (
          <Typography.Paragraph
            style={{
              marginTop: 12,
              padding: 12,
              background: "#fafafa",
              border: "1px solid #f0f0f0",
              borderRadius: 8,
            }}
          >
            <Tag color="cyan">后端：{translated.backend}</Tag>
            <div>{translated.text}</div>
            {translated.note && <Text type="secondary">{translated.note}</Text>}
          </Typography.Paragraph>
        )}

        <Input.TextArea
          rows={2}
          value={llmPrompt}
          onChange={(e) => setLlmPrompt(e.target.value)}
          placeholder="写作提示词"
          style={{ marginTop: 16 }}
        />
        <Button
          icon={<ThunderboltOutlined />}
          type="primary"
          onClick={runLlm}
          loading={llmLoading}
          style={{ marginTop: 12 }}
        >
          LLM 生成
        </Button>
        {llmRes && (
          <Typography.Paragraph
            style={{
              marginTop: 12,
              padding: 12,
              background: "#fafafa",
              border: "1px solid #f0f0f0",
              borderRadius: 8,
              whiteSpace: "pre-wrap",
            }}
          >
            <Tag color="purple">后端：{llmRes.backend}</Tag>
            <div>{llmRes.content}</div>
            {llmRes.note && <Text type="secondary">{llmRes.note}</Text>}
          </Typography.Paragraph>
        )}
      </Card>
    </div>
  );
}
