import { useState, useEffect, useRef } from "react";
import {
  Card,
  Input,
  Button,
  Space,
  Typography,
  Spin,
  Tag,
  Badge,
  Row,
  Col,
  Statistic,
  Alert,
  Divider,
  Tooltip,
  message,
} from "antd";
import {
  RobotOutlined,
  UserOutlined,
  NodeIndexOutlined,
  ThunderboltOutlined,
  ApiOutlined,
  AimOutlined,
  ClearOutlined,
  LoadingOutlined,
} from "@ant-design/icons";
import { graphApi } from "@api/modules";
import dayjs from "dayjs";

const { Text } = Typography;
const { TextArea } = Input;

interface ChatMessage {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
  keywords?: string[];
  context?: any;
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
            <div style={{ textAlign: "center", marginTop: 80, color: "#999" }}>
              <RobotOutlined style={{ fontSize: 48, display: "block", marginBottom: 16 }} />
              <Text type="secondary">输入问题开始 GraphRAG 问答</Text>
              <div style={{ marginTop: 8 }}>
                {[
                  "钙钛矿有哪些性能特点？",
                  "列举图谱中的材料类实体",
                  "高效率太阳能电池的制备方法有哪些？",
                ].map((q) => (
                  <Tag
                    key={q}
                    style={{ marginBottom: 4, cursor: "pointer" }}
                    onClick={() => setQuestion(q)}
                  >
                    {q}
                  </Tag>
                ))}
              </div>
            </div>
          )}
          {messages.map((msg) => (
            <div
              key={msg.id}
              style={{
                marginBottom: 12,
                display: "flex",
                justifyContent: msg.role === "user" ? "flex-end" : "flex-start",
              }}
            >
              <div
                style={{
                  maxWidth: "75%",
                  display: "flex",
                  gap: 8,
                  flexDirection: msg.role === "user" ? "row-reverse" : "row",
                  alignItems: "flex-start",
                }}
              >
                <div
                  style={{
                    width: 28,
                    height: 28,
                    borderRadius: "50%",
                    background: msg.role === "user" ? "#1890ff" : "#52c41a",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    color: "#fff",
                    fontSize: 14,
                    flexShrink: 0,
                  }}
                >
                  {msg.role === "user" ? <UserOutlined /> : <RobotOutlined />}
                </div>
                <div>
                  <div
                    style={{
                      background: msg.role === "user" ? "#1890ff" : "#f5f5f5",
                      color: msg.role === "user" ? "#fff" : "#000",
                      borderRadius: 8,
                      padding: "8px 12px",
                      whiteSpace: "pre-wrap",
                    }}
                  >
                    {msg.content}
                  </div>
                  {(msg.keywords?.length ?? 0) > 0 && msg.role === "assistant" && (
                    <div style={{ marginTop: 4 }}>
                      {(msg.keywords ?? []).map((kw) => (
                        <Tag key={kw} color="purple" style={{ fontSize: 11 }}>
                          <AimOutlined /> {kw}
                        </Tag>
                      ))}
                    </div>
                  )}
                  <Text type="secondary" style={{ fontSize: 11, marginTop: 2, display: "block" }}>
                    {dayjs(msg.timestamp).format("HH:mm:ss")}
                  </Text>
                </div>
              </div>
            </div>
          ))}
          {loading && (
            <div style={{ display: "flex", alignItems: "center", gap: 8, color: "#999" }}>
              <Spin size="small" />
              <Text type="secondary">GraphRAG 思考中...</Text>
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
            placeholder="输入问题，按 Enter 或点击发送... (Shift+Enter 换行)"
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

      {/* 示例问题提示 */}
      <Divider style={{ margin: "16px 0" }} />
      <Text type="secondary">示例问题: </Text>
      {[
        "图谱中有哪些材料类实体？",
        "列出所有HAS_PROPERTY关系",
        "与高效太阳能电池相关的实体有哪些？",
      ].map((q) => (
        <Tag
          key={q}
          style={{ marginLeft: 4, cursor: "pointer" }}
          onClick={() => (ragEnabled ? setQuestion(q) : message.warning("服务未连接"))}
        >
          {q}
        </Tag>
      ))}
    </div>
  );
}
