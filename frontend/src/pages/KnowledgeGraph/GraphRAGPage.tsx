import { useEffect, useRef, useState } from "react";
import {
  Alert,
  Badge,
  Button,
  Card,
  Col,
  Divider,
  Input,
  Row,
  Space,
  Spin,
  Statistic,
  Tag,
  Tooltip,
  Typography,
  message,
} from "antd";
import {
  AimOutlined,
  ApiOutlined,
  ClearOutlined,
  FileTextOutlined,
  LoadingOutlined,
  NodeIndexOutlined,
  RobotOutlined,
  ThunderboltOutlined,
  UserOutlined,
} from "@ant-design/icons";
import { useNavigate } from "react-router-dom";
import { graphApi } from "@api/modules";
import dayjs from "dayjs";

const { Text } = Typography;
const { TextArea } = Input;

/** 示例问题类型（用于界面标注，帮助用户理解问答能力边界）。 */
type QueryType = "引用关系" | "结构关系" | "节点关系";

const QUERY_TYPE_COLOR: Record<QueryType, string> = {
  引用关系: "green",
  结构关系: "blue",
  节点关系: "purple",
};

/**
 * 示例问题：全部落在**知识图谱**上可回答（不是关系库字段查询），且已逐条实测命中图谱上下文。
 *
 * 依据图谱实况（均已用真实链路验证）：
 * - `(:Document)-[:CITES]->(:Document)`：15 条引用边，均自《Attention Is All You Need》
 *   指向 15 篇被引论文 → 支撑「引用了哪些论文」（实测命中 15 条边）；
 * - `(:Document)-[:CONTAINS]->(:Chunk)`：论文与其正文分段的包含关系 → 支撑结构类问题；
 * - 任意节点可用一跳关系连通（如 Layer Normalization 的 CITES 入边）→ 支撑「与哪些节点存在关系」。
 */
const EXAMPLE_QUESTIONS: { type: QueryType; text: string }[] = [
  { type: "引用关系", text: "《Attention Is All You Need》引用了图谱中的哪些论文？" },
  { type: "结构关系", text: "图谱中论文与正文分段（Chunk）是如何关联的？" },
  { type: "节点关系", text: "Layer Normalization 在图谱中与哪些节点存在关系？" },
];

/** 空态引导：示例仅 3 条，全部展示。 */
const STARTER_QUESTIONS = EXAMPLE_QUESTIONS;

interface ChatMessage {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
  keywords?: string[];
  context?: any;
  sources?: any[];
  timestamp: string;
}

interface LLMStatus {
  llm_provider: string;
  base_url: string;
  current_model?: string;
  status?: string;
  loaded_model?: any;
  error?: string;
}

export default function GraphRAGPage() {
  const [question, setQuestion] = useState("");
  const [loading, setLoading] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [llmStatus, setLlmStatus] = useState<LLMStatus | null>(null);
  const [graphStats, setGraphStats] = useState<any>(null);
  const [statusLoading, setStatusLoading] = useState(false);
  const [ragEnabled, setRagEnabled] = useState(false);
  const [showContext, setShowContext] = useState(false);
  const [lastContext, setLastContext] = useState<any>(null);
  const chatEndRef = useRef<HTMLDivElement>(null);
  const navigate = useNavigate();

  useEffect(() => {
    checkServices();
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const checkServices = async () => {
    setStatusLoading(true);
    try {
      const [healthRes, statsRes] = await Promise.all([
        graphApi.ragHealth(),
        graphApi.ragGraphStats(),
      ]);
      const health = healthRes.data || healthRes;
      const stats = statsRes.data || statsRes;
      setRagEnabled(health.status === "connected");
      setGraphStats(stats);
    } catch {
      setRagEnabled(false);
    } finally {
      setStatusLoading(false);
    }
  };

  const fetchLlmStatus = async () => {
    try {
      const res: any = await graphApi.ragStatus();
      setLlmStatus(res.data || res);
    } catch {
      /* ignore */
    }
  };

  useEffect(() => {
    if (ragEnabled) fetchLlmStatus();
  }, [ragEnabled]);

  const handleQuery = async () => {
    if (!question.trim()) return;
    if (!ragEnabled) {
      message.warning("GraphRAGTest 服务未连接，请确保服务已启动");
      return;
    }

    const userMsg: ChatMessage = {
      id: `user_${Date.now()}`,
      role: "user",
      content: question.trim(),
      timestamp: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, userMsg]);
    setQuestion("");
    setLoading(true);
    setShowContext(false);
    setLastContext(null);

    try {
      const res: any = await graphApi.ragQuery(question.trim(), true);
      const data = res.data || res;

      if (data.error) {
        // 处理错误对象，确保显示为字符串
        const errorStr =
          typeof data.error === "object" ? JSON.stringify(data.error) : String(data.error);
        const errMsg: ChatMessage = {
          id: `err_${Date.now()}`,
          role: "assistant",
          content: `错误: ${errorStr}`,
          timestamp: new Date().toISOString(),
        };
        setMessages((prev) => [...prev, errMsg]);
      } else {
        if (data.context) setLastContext(data.context);
        const assistantMsg: ChatMessage = {
          id: `asst_${Date.now()}`,
          role: "assistant",
          content: data.answer || "（未返回有效答案）",
          keywords: data.keywords,
          context: data.context,
          sources: data.sources,
          timestamp: new Date().toISOString(),
        };
        setMessages((prev) => [...prev, assistantMsg]);
      }
    } catch (e: any) {
      // 提取错误信息，确保显示为字符串
      let errorMessage = "未知错误";
      if (e?.response?.data?.detail) {
        errorMessage =
          typeof e.response.data.detail === "object"
            ? JSON.stringify(e.response.data.detail)
            : String(e.response.data.detail);
      } else if (e?.response?.data?.error) {
        errorMessage =
          typeof e.response.data.error === "object"
            ? JSON.stringify(e.response.data.error)
            : String(e.response.data.error);
      } else if (e?.message) {
        errorMessage = e.message;
      }

      const errMsg: ChatMessage = {
        id: `err_${Date.now()}`,
        role: "assistant",
        content: `请求失败: ${errorMessage}`,
        timestamp: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, errMsg]);
    } finally {
      setLoading(false);
    }
  };

  const clearChat = () => setMessages([]);

  const latestMsg = messages[messages.length - 1];

  return (
    <div>
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          marginBottom: 16,
        }}
      >
        <div>
          <h2 style={{ margin: 0 }}>GraphRAG 智能问答</h2>
          <Text type="secondary">基于知识图谱 + Qwen LLM 的智能问答系统</Text>
        </div>
        <Space>
          <Badge
            status={ragEnabled ? "success" : "error"}
            text={ragEnabled ? "GraphRAG 已连接" : "未连接"}
          />
          <Button
            icon={<ApiOutlined />}
            onClick={checkServices}
            size="small"
            loading={statusLoading}
          >
            刷新状态
          </Button>
          {ragEnabled && (
            <Button icon={<ThunderboltOutlined />} onClick={fetchLlmStatus} size="small">
              LLM: {llmStatus?.current_model || "未加载"}
            </Button>
          )}
        </Space>
      </div>

      <Row gutter={16} style={{ marginBottom: 16 }}>
        {/* 图谱统计 */}
        <Col span={12}>
          <Card
            size="small"
            title={
              <span>
                <NodeIndexOutlined /> 图谱统计
              </span>
            }
            extra={
              <Button size="small" onClick={checkServices}>
                刷新
              </Button>
            }
          >
            {graphStats && !graphStats.error ? (
              <Row gutter={12}>
                <Col span={8}>
                  <Statistic
                    title="节点总数"
                    value={graphStats.total_nodes || 0}
                    valueStyle={{ fontSize: 20 }}
                  />
                </Col>
                <Col span={8}>
                  <Statistic
                    title="关系总数"
                    value={graphStats.total_relations || 0}
                    valueStyle={{ fontSize: 20 }}
                  />
                </Col>
                <Col span={8}>
                  <Statistic
                    title="节点类型"
                    value={Object.keys(graphStats.node_labels || {}).length}
                    valueStyle={{ fontSize: 20 }}
                  />
                </Col>
              </Row>
            ) : (
              <Text type="secondary">图谱为空或服务未连接</Text>
            )}
            {graphStats && graphStats.node_labels && (
              <div style={{ marginTop: 8 }}>
                {Object.entries(graphStats.node_labels as Record<string, number>).map(
                  ([label, cnt]) => (
                    <Tag key={label} color="blue" style={{ marginBottom: 4 }}>
                      {label}: {cnt}
                    </Tag>
                  ),
                )}
              </div>
            )}
          </Card>
        </Col>

        {/* LLM 状态 */}
        <Col span={12}>
          <Card
            size="small"
            title={
              <span>
                <RobotOutlined /> LLM 状态
              </span>
            }
            extra={
              <Button size="small" icon={<LoadingOutlined />} onClick={fetchLlmStatus}>
                刷新
              </Button>
            }
          >
            {llmStatus ? (
              <>
                <Row gutter={12}>
                  <Col span={12}>
                    <Statistic title="Provider" value="LM Studio" valueStyle={{ fontSize: 16 }} />
                  </Col>
                  <Col span={12}>
                    <Statistic
                      title="当前模型"
                      value={llmStatus.current_model || llmStatus.loaded_model?.id || "未加载"}
                      valueStyle={{ fontSize: 16 }}
                    />
                  </Col>
                </Row>
                <div style={{ marginTop: 8 }}>
                  <Text type="secondary">地址: {llmStatus.base_url}</Text>
                </div>
                {llmStatus.error && (
                  <Alert message={llmStatus.error} type="warning" style={{ marginTop: 8 }} />
                )}
              </>
            ) : (
              <Spin size="small" />
            )}
          </Card>
        </Col>
      </Row>

      {!ragEnabled && (
        <Alert
          type="warning"
          showIcon
          message="GraphRAGTest 服务未连接"
          description="请确保 GraphRAGTest 服务已启动 (python app.py，默认端口 8001)，且 Neo4j 和 LM Studio 已就绪。"
          style={{ marginBottom: 16 }}
          action={
            <Button size="small" onClick={checkServices}>
              重试
            </Button>
          }
        />
      )}

      {/* 聊天区域 */}
      <Card
        style={{ height: 480, display: "flex", flexDirection: "column" }}
        title={
          <span>
            <RobotOutlined /> 问答对话
          </span>
        }
        extra={
          <Space>
            {(latestMsg?.keywords?.length ?? 0) > 0 && (
              <Tooltip title="显示检索上下文">
                <Button size="small" onClick={() => setShowContext(!showContext)}>
                  {showContext ? "隐藏" : "显示"}上下文
                </Button>
              </Tooltip>
            )}
            <Button size="small" icon={<ClearOutlined />} onClick={clearChat}>
              清空
            </Button>
          </Space>
        }
      >
        {/* 消息列表 */}
        <div style={{ flex: 1, overflowY: "auto", marginBottom: 12 }}>
          {messages.length === 0 && (
            <div style={{ textAlign: "center", marginTop: 48, color: "#999" }}>
              <div
                style={{
                  width: 64,
                  height: 64,
                  margin: "0 auto 16px",
                  borderRadius: "50%",
                  background: "linear-gradient(135deg,#4f46e5,#06b6d4)",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  boxShadow: "0 12px 28px -10px rgba(79,70,229,0.5)",
                }}
              >
                <RobotOutlined style={{ fontSize: 28, color: "#fff" }} />
              </div>
              <div style={{ fontSize: 16, fontWeight: 600, color: "#0f172a" }}>
                开始一次知识图谱问答
              </div>
              <Text type="secondary" style={{ fontSize: 13 }}>
                基于文献图谱实体关系与 LLM 推理，答案可溯源到原文页码
              </Text>
              <div
                style={{
                  marginTop: 16,
                  display: "flex",
                  flexWrap: "wrap",
                  gap: 8,
                  justifyContent: "center",
                }}
              >
                {STARTER_QUESTIONS.map(({ type, text: q }) => (
                  <div
                    key={q}
                    onClick={() => setQuestion(q)}
                    title={`${type}：点击填入输入框`}
                    style={{
                      padding: "6px 14px",
                      borderRadius: 999,
                      background: "#eef2ff",
                      color: "#4f46e5",
                      fontSize: 13,
                      cursor: "pointer",
                      border: "1px solid #e0e7ff",
                      transition: "all .2s",
                    }}
                  >
                    {q}
                  </div>
                ))}
              </div>
              <Text type="secondary" style={{ fontSize: 12, marginTop: 10, display: "block" }}>
                支持 {STARTER_QUESTIONS.map((q) => q.type).join(" / ")}
              </Text>
            </div>
          )}
          {messages.map((msg) => (
            <div
              key={msg.id}
              style={{
                marginBottom: 16,
                display: "flex",
                justifyContent: msg.role === "user" ? "flex-end" : "flex-start",
              }}
            >
              <div
                style={{
                  maxWidth: "78%",
                  display: "flex",
                  gap: 10,
                  flexDirection: msg.role === "user" ? "row-reverse" : "row",
                  alignItems: "flex-start",
                }}
              >
                <div
                  style={{
                    width: 34,
                    height: 34,
                    borderRadius: "50%",
                    background:
                      msg.role === "user"
                        ? "linear-gradient(135deg,#64748b,#475569)"
                        : "linear-gradient(135deg,#4f46e5,#06b6d4)",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    color: "#fff",
                    fontSize: 15,
                    flexShrink: 0,
                    boxShadow: "0 4px 10px -4px rgba(79,70,229,0.4)",
                  }}
                >
                  {msg.role === "user" ? <UserOutlined /> : <RobotOutlined />}
                </div>
                <div
                  style={{
                    display: "flex",
                    flexDirection: "column",
                    alignItems: msg.role === "user" ? "flex-end" : "flex-start",
                  }}
                >
                  <div
                    style={{
                      background:
                        msg.role === "user" ? "linear-gradient(135deg,#4f46e5,#6366f1)" : "#f8fafc",
                      color: msg.role === "user" ? "#fff" : "#0f172a",
                      border: msg.role === "user" ? "none" : "1px solid #e6e8f0",
                      borderRadius:
                        msg.role === "user" ? "16px 16px 4px 16px" : "16px 16px 16px 4px",
                      padding: "10px 14px",
                      whiteSpace: "pre-wrap",
                      lineHeight: 1.6,
                      fontSize: 14,
                      boxShadow:
                        msg.role === "user"
                          ? "0 6px 16px -6px rgba(79,70,229,0.5)"
                          : "0 1px 2px rgba(15,23,42,0.04)",
                    }}
                  >
                    {msg.content}
                  </div>
                  {(msg.keywords?.length ?? 0) > 0 && msg.role === "assistant" && (
                    <div style={{ marginTop: 6 }}>
                      {(msg.keywords ?? []).map((kw) => (
                        <Tag
                          key={kw}
                          style={{
                            fontSize: 11,
                            marginBottom: 4,
                            background: "#eef2ff",
                            color: "#4f46e5",
                            border: "1px solid #e0e7ff",
                          }}
                        >
                          <AimOutlined /> {kw}
                        </Tag>
                      ))}
                    </div>
                  )}
                  {(msg.sources?.length ?? 0) > 0 && msg.role === "assistant" && (
                    <div
                      style={{
                        marginTop: 8,
                        background: "#f8fafc",
                        border: "1px solid #e6e8f0",
                        borderLeft: "3px solid #4f46e5",
                        borderRadius: 8,
                        padding: "8px 10px",
                        fontSize: 11,
                        maxWidth: 480,
                      }}
                    >
                      <Text strong style={{ fontSize: 11, color: "#4f46e5" }}>
                        溯源来源 ({msg.sources!.length})
                      </Text>
                      {(msg.sources ?? []).slice(0, 5).map((s: any, i: number) => (
                        <div key={i} style={{ marginTop: 4, color: "#475569" }}>
                          <Tag
                            color="geekblue"
                            style={{ fontSize: 10, marginRight: 4, cursor: "pointer" }}
                            onClick={() =>
                              s.document_id &&
                              navigate(
                                `/documents/${s.document_id}${
                                  typeof s.page_number === "number" ? `?page=${s.page_number}` : ""
                                }`,
                              )
                            }
                          >
                            {s.document_id || "?"}
                          </Tag>
                          {typeof s.page_number === "number" && (
                            <Tag color="default" style={{ fontSize: 10, marginRight: 4 }}>
                              <FileTextOutlined /> 第 {s.page_number} 页
                            </Tag>
                          )}
                          {s.snippet?.slice(0, 60) || ""}
                          {typeof s.score === "number" && (
                            <Text type="secondary" style={{ fontSize: 10 }}>
                              {" "}
                              (score {s.score.toFixed(2)})
                            </Text>
                          )}
                        </div>
                      ))}
                    </div>
                  )}
                  <Text type="secondary" style={{ fontSize: 11, marginTop: 4 }}>
                    {dayjs(msg.timestamp).format("HH:mm")}
                  </Text>
                </div>
              </div>
            </div>
          ))}
          {loading && (
            <div style={{ display: "flex", alignItems: "flex-start", gap: 10 }}>
              <div
                style={{
                  width: 34,
                  height: 34,
                  borderRadius: "50%",
                  background: "linear-gradient(135deg,#4f46e5,#06b6d4)",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  color: "#fff",
                  flexShrink: 0,
                }}
              >
                <RobotOutlined />
              </div>
              <div
                style={{
                  background: "#f8fafc",
                  border: "1px solid #e6e8f0",
                  borderRadius: "16px 16px 16px 4px",
                  padding: "12px 16px",
                  display: "flex",
                  alignItems: "center",
                  gap: 6,
                }}
              >
                <span className="rag-typing-dot" />
                <span className="rag-typing-dot" style={{ animationDelay: "0.15s" }} />
                <span className="rag-typing-dot" style={{ animationDelay: "0.3s" }} />
              </div>
            </div>
          )}
          <div ref={chatEndRef} />
        </div>

        {/* 上下文面板 */}
        {showContext && lastContext && (
          <div
            style={{
              background: "#f0f5ff",
              border: "1px solid #adc6ff",
              borderRadius: 6,
              padding: 8,
              marginBottom: 8,
              maxHeight: 120,
              overflowY: "auto",
              fontSize: 12,
            }}
          >
            <Text strong style={{ fontSize: 12 }}>
              检索到的图谱上下文:
            </Text>
            {lastContext.nodes?.length > 0 && (
              <div style={{ marginTop: 4 }}>
                <Text type="secondary">实体: </Text>
                {lastContext.nodes.slice(0, 5).map((n: any) => (
                  <Tag key={n.properties?.id} color="blue" style={{ fontSize: 11 }}>
                    {n.label}: {n.properties?.id || n.properties?.name}
                  </Tag>
                ))}
              </div>
            )}
            {lastContext.relations?.length > 0 && (
              <div style={{ marginTop: 4 }}>
                <Text type="secondary">关系: </Text>
                {lastContext.relations.slice(0, 5).map((r: any, i: number) => (
                  <Tag key={i} color="green" style={{ fontSize: 11 }}>
                    {`${r.source?.name || r.source?.id} --[${r.relation}]--> ${r.target?.name || r.target?.id}`}
                  </Tag>
                ))}
              </div>
            )}
          </div>
        )}

        {/* 输入框 */}
        <div style={{ display: "flex", gap: 8 }}>
          <TextArea
            placeholder="就图谱中的论文与关系提问（引用 / 结构 / 属性均可），按 Enter 发送"
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            onPressEnter={(e) => {
              if (!e.shiftKey) {
                e.preventDefault();
                handleQuery();
              }
            }}
            autoSize={{ minRows: 1, maxRows: 3 }}
            style={{ flex: 1 }}
            disabled={loading || !ragEnabled}
          />
          <Button
            type="primary"
            onClick={handleQuery}
            loading={loading}
            disabled={!question.trim() || !ragEnabled}
          >
            发送
          </Button>
        </div>
      </Card>

      {/* 示例问题提示：按查询类型分组，贴合库内语料 */}
      <Divider style={{ margin: "16px 0" }} />
      <Text type="secondary">
        示例问题（均可在图谱中回答：引用关系 / 结构关系 / 节点关系，点击即可填入输入框）:
      </Text>
      <div style={{ marginTop: 8 }}>
        {EXAMPLE_QUESTIONS.map(({ type, text: q }) => (
          <Tooltip key={q} title={`${type} · 答案附原文出处锚点`}>
            <Tag
              color={QUERY_TYPE_COLOR[type]}
              data-testid="graphrag-example-tag"
              style={{ marginBottom: 6, cursor: "pointer" }}
              onClick={() => (ragEnabled ? setQuestion(q) : message.warning("服务未连接"))}
            >
              {type}｜{q}
            </Tag>
          </Tooltip>
        ))}
      </div>
    </div>
  );
}
