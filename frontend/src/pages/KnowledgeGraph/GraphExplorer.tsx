import { useState, useEffect, useRef, useCallback } from "react";
import {
  Card,
  Input,
  Select,
  Space,
  Button,
  Row,
  Col,
  Tag,
  Drawer,
  Empty,
  Spin,
  message,
  Popconfirm,
  Typography,
} from "antd";
import {
  SearchOutlined,
  ReloadOutlined,
  NodeIndexOutlined,
  DatabaseOutlined,
  DeleteOutlined,
  BarChartOutlined,
  ClusterOutlined,
} from "@ant-design/icons";
import ForceGraph from "@components/Graph/ForceGraph";
import { graphApi } from "@api/modules";
import { useAuthStore } from "@store/authStore";
import { useNavigate } from "react-router-dom";
import type { GraphEntity, GraphRelation } from "@/types";

const { Title, Text } = Typography;

const nodeTypeOptions = [
  { value: "Material", label: "材料", color: "#1890ff" },
  { value: "Property", label: "性能", color: "#52c41a" },
  { value: "Method", label: "方法", color: "#faad14" },
  { value: "Document", label: "文档", color: "#13c2c2" },
  { value: "Result", label: "结果", color: "#eb2f96" },
  { value: "Parameter", label: "参数", color: "#722ed1" },
];

const relationTypeOptions = [
  { value: "ACHIEVES", label: "实现" },
  { value: "HAS_CHALLENGE", label: "面临挑战" },
  { value: "EXHIBITS", label: "展现" },
  { value: "PRODUCES", label: "产生" },
  { value: "TRANSPORTS_HOLE", label: "传输空穴" },
  { value: "TRANSPORTS_ELECTRON", label: "传输电子" },
  { value: "REQUIRES", label: "需要" },
];

export default function GraphExplorer() {
  const [entities, setEntities] = useState<GraphEntity[]>([]);
  const [relations, setRelations] = useState<GraphRelation[]>([]);
  const [searchQuery, setSearchQuery] = useState("");
  const [_entityTypeFilter, setEntityTypeFilter] = useState<string | undefined>(undefined);
  const [loading, setLoading] = useState(false);
  const [stats, setStats] = useState<any>(null);
  const [selectedNode, setSelectedNode] = useState<GraphEntity | null>(null);
  const [_nodeDetails, setNodeDetails] = useState<any>(null);
  const [seeding, setSeeding] = useState(false);
  const [initReady, setInitReady] = useState(false);

  const { isAuthenticated } = useAuthStore();
  const navigate = useNavigate();
  const graphRef = useRef<any>();

  // 检查认证状态
  useEffect(() => {
    const checkAuth = () => {
      const token = localStorage.getItem("access_token");
      if (isAuthenticated === undefined) return;
      if (!isAuthenticated && !token) {
        navigate("/login");
        return;
      }
      setInitReady(true);
    };
    checkAuth();
  }, [isAuthenticated, navigate]);

  // 获取图谱统计
  const fetchStats = async () => {
    try {
      const res: any = await graphApi.ragGraphStats();
      setStats(res.data || res);
    } catch {
      // ignore
    }
  };

  // 搜索节点
  const handleSearch = async () => {
    setLoading(true);
    try {
      if (searchQuery) {
        const res: any = await graphApi.ragSearchNodes(searchQuery, 50);
        const data = res.data || res;
        const nodes = data.nodes || [];
        setEntities(
          nodes.map((n: any) => ({
            id: n.properties?.id || n.id,
            labels: [n.label],
            properties: n.properties || {},
          })),
        );
        setRelations([]);
      } else {
        await loadAllNodes();
      }
    } catch {
      message.error("搜索失败");
    } finally {
      setLoading(false);
    }
  };

  // 按类型加载节点
  const loadNodesByType = async (type: string) => {
    setLoading(true);
    try {
      const res: any = await graphApi.ragNodesByLabel(type, 100);
      const data = res.data || res;
      const nodes = data.nodes || [];
      setEntities(
        nodes.map((n: any) => ({
          id: n.properties?.id || n.id,
          labels: [n.label],
          properties: n.properties || {},
        })),
      );
      setRelations([]);
    } catch {
      message.error("加载失败");
    } finally {
      setLoading(false);
    }
  };

  // 加载所有节点
  const loadAllNodes = async () => {
    setLoading(true);
    try {
      const allEntities: GraphEntity[] = [];
      for (const typeOpt of nodeTypeOptions) {
        try {
          const res: any = await graphApi.ragNodesByLabel(typeOpt.value, 30);
          const data = res.data || res;
          const nodes = data.nodes || [];
          nodes.forEach((n: any) => {
            allEntities.push({
              id: n.properties?.id || n.id,
              labels: [n.label],
              properties: n.properties || {},
            });
          });
        } catch {
          // ignore
        }
      }
      setEntities(allEntities);
      await loadRelations();
    } catch {
      message.error("加载图谱失败");
    } finally {
      setLoading(false);
    }
  };

  // 加载关系
  const loadRelations = async () => {
    const allRels: GraphRelation[] = [];
    for (const relOpt of relationTypeOptions.slice(0, 3)) {
      try {
        const res: any = await graphApi.ragGraphSearch(relOpt.value, 20);
        const data = res.data || res;
        const rels = data.relations || [];
        rels.forEach((r: any) => {
          allRels.push({
            id: `${r.source?.id || r.source_id}-${r.relation || r.type}-${r.target?.id || r.target_id}`,
            type: r.relation || r.type || r.relation_type,
            startNode: r.source?.id || r.source_id,
            endNode: r.target?.id || r.target_id,
            properties: r.properties || {},
          });
        });
      } catch {
        // ignore
      }
    }
    setRelations(allRels);
  };

  // 初始化示例数据
  const handleSeedData = async () => {
    setSeeding(true);
    try {
      const res: any = await graphApi.ragSeedDemoData();
      const data = res.data || res;
      message.success(data.message || "示例数据初始化成功");
      await loadAllNodes();
      await fetchStats();
    } catch (e: any) {
      message.error(e?.response?.data?.detail || "初始化失败");
    } finally {
      setSeeding(false);
    }
  };

  // 清空图谱
  const handleClearGraph = async () => {
    try {
      await graphApi.ragClearGraph();
      message.success("图谱已清空");
      setEntities([]);
      setRelations([]);
      await fetchStats();
    } catch {
      message.error("清空失败");
    }
  };

  // 初始加载
  useEffect(() => {
    if (!initReady) return;
    fetchStats();
    loadAllNodes();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [initReady]);

  // 节点点击
  const handleNodeClick = useCallback((entity: GraphEntity) => {
    setSelectedNode(entity);
    setNodeDetails({ node: entity });
  }, []);

  // 聚焦节点
  const focusNode = () => {
    if (graphRef.current && selectedNode) {
      const node = graphRef.current.graphData().nodes.find((n: any) => n.id === selectedNode.id);
      if (node) {
        graphRef.current.centerAt(node.x, node.y, 800);
        graphRef.current.zoom(2.5, 800);
      }
    }
  };

  if (isAuthenticated === undefined) {
    return (
      <div
        style={{ display: "flex", justifyContent: "center", alignItems: "center", height: "100vh" }}
      >
        <Spin size="large" tip="加载中..." />
      </div>
    );
  }

  return (
    <div style={{ padding: 24, background: "#f0f2f5", minHeight: "100vh" }}>
      {/* 页面标题 */}
      <div
        style={{
          marginBottom: 24,
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
        }}
      >
        <div>
          <Title level={4} style={{ margin: 0, display: "flex", alignItems: "center", gap: 8 }}>
            <ClusterOutlined style={{ color: "#1890ff" }} />
            知识图谱探索
          </Title>
          <Text type="secondary" style={{ marginTop: 4, display: "block" }}>
            交互式可视化知识图谱，支持节点搜索、筛选和详情查看
          </Text>
        </div>
      </div>

      {/* 统计概览卡片 */}
      <Row gutter={16} style={{ marginBottom: 24 }}>
        <Col span={6}>
          <Card
            size="small"
            style={{
              background: "linear-gradient(135deg, #1890ff 0%, #096dd9 100%)",
              border: "none",
              borderRadius: 12,
            }}
            styles={{ body: { padding: "16px 20px" } }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
              <div
                style={{
                  width: 48,
                  height: 48,
                  borderRadius: 12,
                  background: "rgba(255,255,255,0.2)",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                }}
              >
                <NodeIndexOutlined style={{ fontSize: 24, color: "#fff" }} />
              </div>
              <div>
                <Text style={{ color: "rgba(255,255,255,0.8)", fontSize: 12 }}>实体总数</Text>
                <div style={{ color: "#fff", fontSize: 24, fontWeight: "bold" }}>
                  {stats?.total_nodes || 0}
                </div>
              </div>
            </div>
          </Card>
        </Col>
        <Col span={6}>
          <Card
            size="small"
            style={{
              background: "linear-gradient(135deg, #52c41a 0%, #389e0d 100%)",
              border: "none",
              borderRadius: 12,
            }}
            styles={{ body: { padding: "16px 20px" } }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
              <div
                style={{
                  width: 48,
                  height: 48,
                  borderRadius: 12,
                  background: "rgba(255,255,255,0.2)",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                }}
              >
                <BarChartOutlined style={{ fontSize: 24, color: "#fff" }} />
              </div>
              <div>
                <Text style={{ color: "rgba(255,255,255,0.8)", fontSize: 12 }}>关系总数</Text>
                <div style={{ color: "#fff", fontSize: 24, fontWeight: "bold" }}>
                  {stats?.total_relations || 0}
                </div>
              </div>
            </div>
          </Card>
        </Col>
        <Col span={12}>
          <Card
            size="small"
            style={{ borderRadius: 12, border: "1px solid #e8e8e8" }}
            styles={{ body: { padding: "12px 16px" } }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
              <Text type="secondary" style={{ fontSize: 12 }}>
                节点分布：
              </Text>
              {nodeTypeOptions.map((t) => (
                <Tag
                  key={t.value}
                  color={t.color}
                  style={{
                    margin: 0,
                    borderRadius: 12,
                    padding: "2px 10px",
                    fontSize: 12,
                  }}
                >
                  {t.label} {stats?.node_labels?.[t.value] || 0}
                </Tag>
              ))}
            </div>
          </Card>
        </Col>
      </Row>

      {/* 操作栏 */}
      <Card
        size="small"
        style={{ marginBottom: 16, borderRadius: 12 }}
        styles={{ body: { padding: "12px 16px" } }}
      >
        <Space wrap size={12}>
          <Input.Search
            placeholder="搜索实体关键词..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            onSearch={handleSearch}
            style={{ width: 260 }}
            allowClear
            prefix={<SearchOutlined style={{ color: "#bfbfbf" }} />}
          />
          <Select
            placeholder="筛选节点类型"
            style={{ width: 140 }}
            allowClear
            options={nodeTypeOptions}
            onChange={(v) => {
              setEntityTypeFilter(v);
              if (v) loadNodesByType(v);
              else loadAllNodes();
            }}
          />
          <Button
            icon={<ReloadOutlined />}
            onClick={() => {
              loadAllNodes();
              fetchStats();
            }}
          >
            刷新
          </Button>
          <Button
            icon={<DatabaseOutlined />}
            onClick={handleSeedData}
            loading={seeding}
            style={{ background: "#1890ff", borderColor: "#1890ff", color: "#fff" }}
          >
            初始化示例数据
          </Button>
          <Popconfirm
            title="确定要清空图谱吗？"
            description="此操作不可恢复，将删除所有实体和关系"
            onConfirm={handleClearGraph}
            okText="确定清空"
            cancelText="取消"
            okButtonProps={{ danger: true }}
          >
            <Button icon={<DeleteOutlined />} danger>
              清空图谱
            </Button>
          </Popconfirm>
        </Space>
      </Card>

      {/* 图谱展示区域 */}
      <Card
        style={{
          borderRadius: 12,
          border: "1px solid #e8e8e8",
          boxShadow: "0 2px 12px rgba(0,0,0,0.08)",
        }}
        styles={{ body: { padding: 0, height: "calc(100vh - 420px)", minHeight: 400 } }}
      >
        {entities.length === 0 && !loading ? (
          <Empty description="暂无图谱数据" style={{ paddingTop: 120 }}>
            <Space>
              <Button type="primary" onClick={loadAllNodes}>
                加载图谱
              </Button>
              <Button icon={<DatabaseOutlined />} onClick={handleSeedData} loading={seeding}>
                初始化示例
              </Button>
            </Space>
          </Empty>
        ) : (
          <ForceGraph
            entities={entities}
            relations={relations}
            onNodeClick={handleNodeClick}
            loading={loading}
          />
        )}
      </Card>

      {/* 图例 */}
      <Card
        size="small"
        style={{ marginTop: 16, borderRadius: 12, background: "#fff" }}
        styles={{ body: { padding: "12px 16px" } }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 24, flexWrap: "wrap" }}>
          <Text strong type="secondary" style={{ fontSize: 12 }}>
            节点类型：
          </Text>
          {nodeTypeOptions.map((t) => (
            <Space key={t.value} size={6}>
              <span
                style={{
                  width: 14,
                  height: 14,
                  borderRadius: "50%",
                  background: t.color,
                  display: "inline-block",
                  boxShadow: `0 2px 4px ${t.color}40`,
                }}
              />
              <Text style={{ fontSize: 13 }}>{t.label}</Text>
            </Space>
          ))}
          <Text type="secondary" style={{ fontSize: 12, marginLeft: 16 }}>
            点击节点查看详情 | 拖拽移动节点 | 滚轮缩放
          </Text>
        </div>
      </Card>

      {/* 节点详情抽屉 */}
      <Drawer
        title={
          <Space>
            <ClusterOutlined
              style={{
                color: selectedNode
                  ? nodeTypeOptions.find((t) => t.value === selectedNode.labels[0])?.color
                  : "#1890ff",
              }}
            />
            <span>实体详情</span>
          </Space>
        }
        open={!!selectedNode}
        onClose={() => {
          setSelectedNode(null);
          setNodeDetails(null);
        }}
        width={420}
        styles={{ body: { padding: 0 } }}
      >
        {selectedNode && (
          <div>
            {/* 节点头部 */}
            <div
              style={{
                padding: 24,
                background: "linear-gradient(135deg, #f0f5ff 0%, #e6f7ff 100%)",
                borderBottom: "1px solid #e8e8e8",
              }}
            >
              <div
                style={{
                  width: 56,
                  height: 56,
                  borderRadius: 16,
                  background:
                    nodeTypeOptions.find((t) => t.value === selectedNode.labels[0])?.color ||
                    "#1890ff",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  marginBottom: 16,
                  boxShadow: `0 4px 12px ${nodeTypeOptions.find((t) => t.value === selectedNode.labels[0])?.color}40`,
                }}
              >
                <NodeIndexOutlined style={{ fontSize: 28, color: "#fff" }} />
              </div>
              <Title level={4} style={{ margin: 0, marginBottom: 8 }}>
                {selectedNode.properties?.name || selectedNode.id}
              </Title>
              <Space size={8}>
                <Tag
                  color={nodeTypeOptions.find((t) => t.value === selectedNode.labels[0])?.color}
                  style={{ borderRadius: 12 }}
                >
                  {selectedNode.labels[0]}
                </Tag>
                {selectedNode.properties?.formula && (
                  <Tag style={{ borderRadius: 12 }}>{selectedNode.properties.formula}</Tag>
                )}
              </Space>
            </div>

            {/* 节点属性 */}
            <div style={{ padding: 20 }}>
              <Text
                strong
                style={{ fontSize: 14, color: "#262626", display: "block", marginBottom: 12 }}
              >
                属性信息
              </Text>
              <div style={{ display: "grid", gap: 12 }}>
                <div
                  style={{
                    display: "flex",
                    padding: "10px 12px",
                    background: "#fafafa",
                    borderRadius: 8,
                  }}
                >
                  <Text type="secondary" style={{ width: 80 }}>
                    ID
                  </Text>
                  <Text copyable style={{ fontFamily: "monospace", fontSize: 13 }}>
                    {selectedNode.id}
                  </Text>
                </div>
                {selectedNode.properties &&
                  Object.entries(selectedNode.properties).map(([k, v]) => {
                    if (k === "id" || k === "name" || k === "formula") return null;
                    return (
                      <div
                        key={k}
                        style={{
                          display: "flex",
                          padding: "10px 12px",
                          background: "#fafafa",
                          borderRadius: 8,
                        }}
                      >
                        <Text type="secondary" style={{ width: 80 }}>
                          {k}
                        </Text>
                        <Text style={{ flex: 1, fontSize: 13 }}>{String(v)}</Text>
                      </div>
                    );
                  })}
              </div>

              <Button
                type="primary"
                icon={<NodeIndexOutlined />}
                onClick={focusNode}
                block
                style={{ marginTop: 20, height: 44, borderRadius: 10 }}
              >
                在图谱中定位
              </Button>
            </div>
          </div>
        )}
      </Drawer>
    </div>
  );
}
