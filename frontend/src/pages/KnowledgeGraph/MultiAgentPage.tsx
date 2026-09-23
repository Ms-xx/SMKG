import { useEffect, useState } from "react";
import {
  Card,
  Input,
  Button,
  Space,
  Typography,
  Radio,
  Checkbox,
  Tag,
  Alert,
  Spin,
  Divider,
  Collapse,
  Empty,
  Row,
  Col,
  message,
} from "antd";
import {
  ApartmentOutlined,
  ThunderboltOutlined,
  AimOutlined,
  ReconciliationOutlined,
  PartitionOutlined,
} from "@ant-design/icons";
import { multiAgentApi } from "@api/modules";
import type { AgentDescriptor, MultiAgentRunResult } from "@/types";

const { Text, Paragraph } = Typography;
const { TextArea } = Input;

export default function MultiAgentPage() {
  const [agents, setAgents] = useState<AgentDescriptor[]>([]);
  const [modes, setModes] = useState<string[]>(["merge", "vote", "arbitrate"]);
  const [selectedAgents, setSelectedAgents] = useState<string[]>([]);
  const [query, setQuery] = useState("");
  const [context, setContext] = useState("");
  const [mode, setMode] = useState("merge");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<MultiAgentRunResult | null>(null);

  useEffect(() => {
    multiAgentApi
      .agents()
      .then((res: any) => {
        const data = res.data || res;
        setAgents(data.agents || []);
        setSelectedAgents((data.agents || []).map((a: AgentDescriptor) => a.name));
        if (data.modes) setModes(data.modes);
      })
      .catch(() => {
        /* ignore */
      });
  }, []);

  const handleRun = async () => {
    if (!query.trim()) {
      message.warning("请输入任务/问题");
      return;
    }
    if (selectedAgents.length === 0) {
      message.warning("请至少选择一个智能体");
      return;
    }
    setLoading(true);
    setResult(null);
    try {
      const res: any = await multiAgentApi.run({
        query: query.trim(),
        context: context.trim() || undefined,
        agents: selectedAgents,
        mode,
      });
      setResult((res.data || res) as MultiAgentRunResult);
    } catch (e: any) {
      message.error(e?.response?.data?.detail || e?.message || "编排失败");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <div>
          <h2 style={{ margin: 0 }}>多 Agent 协作</h2>
          <Text type="secondary">协调器编排多智能体（解析 / 抽取 / 问答 / 综述）并解决冲突</Text>
        </div>
        <Tag color="geekblue" icon={<ApartmentOutlined />}>
          科研助手 · LLM 多智能体编排
        </Tag>
      </div>

      <Divider style={{ margin: "16px 0" }} />

      <Row gutter={16}>
        <Col span={9}>
          <Card
            size="small"
            title={
              <span>
                <PartitionOutlined /> 智能体与策略
              </span>
            }
            style={{ marginBottom: 16 }}
          >
            <Text strong>参与智能体</Text>
            <div style={{ margin: "8px 0 16px" }}>
              <Checkbox.Group
                options={agents.map((a) => ({
                  label: `${a.name} · ${a.description}`,
                  value: a.name,
                }))}
                value={selectedAgents}
                onChange={(vals: any[]) => setSelectedAgents(vals)}
                style={{ display: "flex", flexDirection: "column", gap: 4 }}
              />
            </div>
            <Text strong>冲突解决模式</Text>
            <div style={{ marginTop: 8 }}>
              <Radio.Group value={mode} onChange={(e) => setMode(e.target.value)}>
                <Space direction="vertical">
                  {modes.map((m) => (
                    <Radio key={m} value={m}>
                      {m === "merge"
                        ? "合并（去重并集）"
                        : m === "vote"
                          ? "投票（多数决）"
                          : "仲裁（最高置信度）"}
                    </Radio>
                  ))}
                </Space>
              </Radio.Group>
            </div>
          </Card>

          <Card
            size="small"
            title={
              <span>
                <ThunderboltOutlined /> 输入
              </span>
            }
          >
            <Text type="secondary">任务 / 问题</Text>
            <TextArea
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="如：钙钛矿有哪些性能特点？"
              autoSize={{ minRows: 2, maxRows: 4 }}
              style={{ marginTop: 4 }}
            />
            <Text type="secondary" style={{ display: "block", marginTop: 12 }}>
              上下文（可选，文献段落；解析/抽取/综述优先使用）
            </Text>
            <TextArea
              value={context}
              onChange={(e) => setContext(e.target.value)}
              placeholder="如：钙钛矿太阳能电池采用高效率的制备方法…"
              autoSize={{ minRows: 2, maxRows: 5 }}
              style={{ marginTop: 4 }}
            />
            <Button
              type="primary"
              icon={<ThunderboltOutlined />}
              onClick={handleRun}
              loading={loading}
              block
              style={{ marginTop: 12 }}
            >
              运行编排
            </Button>
          </Card>
        </Col>

        <Col span={15}>
          {!result && !loading && (
            <Card>
              <Empty description="运行后在此查看多智能体协同结果与冲突解决详情" />
            </Card>
          )}
          {loading && (
            <Card>
              <div style={{ textAlign: "center", padding: 32 }}>
                <Spin size="large" />
                <div style={{ marginTop: 8 }}>
                  <Text type="secondary">协调器正分派任务给多个智能体…</Text>
                </div>
              </div>
            </Card>
          )}
          {result && !loading && (
            <>
              <Card
                size="small"
                title={
                  <span>
                    <ReconciliationOutlined /> 最终结论（{result.resolution.mode}）
                  </span>
                }
                extra={<Tag color="blue">{result.session_id}</Tag>}
                style={{ marginBottom: 16 }}
              >
                {result.resolution.final_text && (
                  <Paragraph>{result.resolution.final_text}</Paragraph>
                )}
                {result.resolution.final_items && result.resolution.final_items.length > 0 && (
                  <div style={{ marginTop: 8 }}>
                    <Text strong>合并实体：</Text>
                    {result.resolution.final_items.map((it, i) => (
                      <Tag key={i} color="green" style={{ marginTop: 4 }}>
                        {it.text} : {it.type}
                      </Tag>
                    ))}
                  </div>
                )}
                {result.resolution.unresolved.length > 0 && (
                  <Alert
                    type="warning"
                    showIcon
                    style={{ marginTop: 8 }}
                    message="存在未解决冲突"
                    description={result.resolution.unresolved.map((u) => u.description).join("；")}
                  />
                )}
              </Card>

              {result.conflicts.length > 0 && (
                <Card
                  size="small"
                  title={
                    <span>
                      <AimOutlined /> 冲突明细（{result.conflicts.length}）
                    </span>
                  }
                  style={{ marginBottom: 16 }}
                >
                  {result.conflicts.map((c, i) => (
                    <Alert
                      key={i}
                      type={c.type === "answer" ? "info" : "warning"}
                      showIcon
                      style={{ marginBottom: 8 }}
                      message={
                        c.type === "answer"
                          ? `${c.agents?.join(", ")} 给出不同答案`
                          : `实体「${c.text}」类型冲突：${c.types?.join(" / ")}`
                      }
                      description={c.description}
                    />
                  ))}
                </Card>
              )}

              <Card size="small" title="各智能体独立产出">
                <Collapse
                  items={result.agent_results.map((a) => ({
                    key: a.agent,
                    label: (
                      <Space>
                        <span>{a.agent}</span>
                        <Tag color="purple">{a.backend}</Tag>
                        <Text type="secondary" style={{ fontSize: 12 }}>
                          {a.description} · 置信度 {(a.confidence * 100).toFixed(0)}%
                        </Text>
                      </Space>
                    ),
                    children: (
                      <div>
                        <Paragraph>{a.content}</Paragraph>
                        {a.items && a.items.length > 0 && (
                          <div>
                            {a.items.map((it, i) => (
                              <Tag key={i} color="cyan" style={{ marginBottom: 4 }}>
                                {it.text} : {it.type}
                              </Tag>
                            ))}
                          </div>
                        )}
                      </div>
                    ),
                  }))}
                />
              </Card>
            </>
          )}
        </Col>
      </Row>
    </div>
  );
}
