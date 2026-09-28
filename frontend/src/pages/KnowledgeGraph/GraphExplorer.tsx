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
  DeleteOutlined,
  BarChartOutlined,
  ClusterOutlined,
  PlusOutlined,
} from "@ant-design/icons";
import ForceGraph from "@components/Graph/ForceGraph";
import GraphInsights from "@components/GraphInsights";
import { graphApi } from "@api/modules";
import { useAuthStore } from "@store/authStore";
import { useNavigate } from "react-router-dom";
import type { GraphEntity, GraphRelation } from "@/types";

const { Title, Text } = Typography;

// 预设色板（新自定义类型未指定颜色时按序取用）
const presetColors = [
  "#1890ff",
  "#52c41a",
  "#faad14",
  "#13c2c2",
  "#eb2f96",
  "#722ed1",
  "#f5222d",
  "#ff7a45",
  "#a0d911",
  "#08979c",
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
  const [initReady, setInitReady] = useState(false);
  const [nodeTypeOptions, setNodeTypeOptions] = useState<any[]>([]);
  const [newTypeLabel, setNewTypeLabel] = useState("");
  const [newTypeName, setNewTypeName] = useState("");
  const [newTypeColor, setNewTypeColor] = useState(presetColors[0]);
  const [highlightNodes, setHighlightNodes] = useState<Set<string>>(new Set());

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

  // 获取节点类型列表（默认在前，自定义在后）
  const fetchNodeTypes = async () => {
    try {
      const res: any = await graphApi.getNodeTypes();
      setNodeTypeOptions(res?.data?.items ?? []);
    } catch {
      setNodeTypeOptions([]);
    }
  };

  // 添加自定义节点类型
  const handleAddNodeType = async () => {
    if (!newTypeLabel.trim()) {
      message.warning("请输入节点类型的英文 label");
      return;
    }
    try {
      await graphApi.createNodeType({
        label: newTypeLabel.trim(),
        name: newTypeName.trim(),
        color: newTypeColor,
      });
      message.success("节点类型已添加");
      setNewTypeLabel("");
      setNewTypeName("");
      setNewTypeColor(presetColors[0]);
      await fetchNodeTypes();
    } catch {
      message.error("添加节点类型失败");
    }
  };

  // 删除自定义节点类型（默认类型不可删）
  const handleDeleteNodeType = async (label: string) => {
    try {
      await graphApi.deleteNodeType(label);
      message.success("节点类型已删除");
      await fetchNodeTypes();
    } catch {
      message.error("删除节点类型失败");
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

  // 加载所有节点（按图内实际标签加载，而非配置的类型列表，保证任意领域/自定义类型都能显示）
  const loadAllNodes = async () => {
    setLoading(true);
    try {
      let st = stats;
      if (!st?.node_labels) {
        const sres: any = await graphApi.ragGraphStats();
        st = sres.data || sres;
      }
      const labels = Object.keys(st?.node_labels || {});
      const allEntities: GraphEntity[] = [];
      for (const label of labels) {
        try {
          const res: any = await graphApi.ragNodesByLabel(label, 200);
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
      await loadRelations(st);
    } catch {
      message.error("加载图谱失败");
    } finally {
      setLoading(false);
    }
  };

  // 加载关系（按图内实际关系类型加载）
  const loadRelations = async (st?: any) => {
    let s = st;
    if (!s?.relation_types) {
      const sres: any = await graphApi.ragGraphStats();
      s = sres.data || sres;
    }
    const allRels: GraphRelation[] = [];
    const types = Object.keys(s?.relation_types || {});
    for (const relType of types) {
      try {
        const res: any = await graphApi.ragGraphSearch(relType, 200);
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
    fetchNodeTypes();
    fetchStats();
    loadAllNodes();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [initReady]);

  // 节点类型列表就绪后加载各类型节点（避免初始空列表导致无数据）
  useEffect(() => {
    if (!initReady || nodeTypeOptions.length === 0) return;
    loadAllNodes();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [nodeTypeOptions, initReady]);

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
              {(() => {
                // 按图内实际节点类型分布渲染（剔除 0 计数的配置类型），用配置的颜色/名称，未知类型用回退配色
                const fallback = [
                  "#1890ff",
                  "#52c41a",
                  "#faad14",
                  "#722ed1",
                  "#13c2c2",
                  "#eb2f96",
                  "#8c8c8c",
                ];
                const entries = Object.entries(stats?.node_labels || {})
                  .map(([label, count], i) => {
                    const conf = nodeTypeOptions.find((t) => t.label === label);
                    return {
                      label,
                      count: count as number,
                      name: conf?.name || label,
                      color: conf?.color || fallback[i % fallback.length],
                    };
                  })
                  .sort((a, b) => b.count - a.count);
                if (!entries.length) {
                  return (
                    <Text type="secondary" style={{ fontSize: 12 }}>
                      暂无数据
                    </Text>
                  );
                }
                const max = entries[0].count || 1;
                return entries.map((d) => (
                  <div
                    key={d.label}
                    style={{
                      display: "inline-flex",
                      alignItems: "center",
                      gap: 4,
                      borderRadius: 12,
                      border: `1px solid ${d.color}55`,
                      padding: "2px 10px",
                      fontSize: 12,
                    }}
                  >
                    <span
                      style={{
                        width: 8,
                        height: 8,
                        borderRadius: "50%",
                        background: d.color,
                        display: "inline-block",
                      }}
                    />
                    <span>{d.name}</span>
                    <span style={{ fontWeight: 600, color: d.color, marginLeft: 4 }}>
                      {d.count}
                    </span>
                    <span style={{ color: "#bfbfbf", fontSize: 11, minWidth: 34 }}>
                      {Math.round((d.count / max) * 100)}%
                    </span>
                  </div>
                ));
              })()}
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
            options={nodeTypeOptions.map((t) => ({
              value: t.label,
              label: t.name || t.label,
              color: t.color,
            }))}
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
            </Space>
          </Empty>
        ) : (
          <ForceGraph
            entities={entities}
            relations={relations}
            onNodeClick={handleNodeClick}
            loading={loading}
            highlightNodes={highlightNodes}
          />
        )}
      </Card>

      {/* 知识图谱高级能力：趋势分析 + 异常检测 */}
      <GraphInsights onAnomalyHighlight={setHighlightNodes} />

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
            <Space key={t.label} size={6}>
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
              <Text style={{ fontSize: 13 }}>{t.name || t.label}</Text>
              {t.is_default === false && (
                <Button
                  type="text"
                  size="small"
                  icon={<DeleteOutlined />}
                  onClick={() => handleDeleteNodeType(t.label)}
                  style={{ fontSize: 12, color: "#ff4d4f" }}
                />
              )}
            </Space>
          ))}
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 8,
              flexWrap: "wrap",
              marginTop: 12,
              paddingTop: 12,
              borderTop: "1px dashed #e8e8e8",
              width: "100%",
            }}
          >
            <Text type="secondary" style={{ fontSize: 12 }}>
              添加自定义节点类型：
            </Text>
            <Input
              placeholder="label（英文）"
              value={newTypeLabel}
              onChange={(e) => setNewTypeLabel(e.target.value)}
              style={{ width: 140 }}
            />
            <Input
              placeholder="中文名（可选）"
              value={newTypeName}
              onChange={(e) => setNewTypeName(e.target.value)}
              style={{ width: 140 }}
            />
            <Space size={4}>
              {presetColors.map((c) => (
                <span
                  key={c}
                  onClick={() => setNewTypeColor(c)}
                  style={{
                    width: 18,
                    height: 18,
                    borderRadius: "50%",
                    background: c,
                    cursor: "pointer",
                    display: "inline-block",
                    border: newTypeColor === c ? "2px solid #333" : "2px solid transparent",
                    boxShadow: "0 1px 3px rgba(0,0,0,0.2)",
                  }}
                />
              ))}
            </Space>
            <Button type="primary" size="small" icon={<PlusOutlined />} onClick={handleAddNodeType}>
              添加
            </Button>
          </div>
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
                  ? nodeTypeOptions.find((t) => t.label === selectedNode.labels[0])?.color
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
                    nodeTypeOptions.find((t) => t.label === selectedNode.labels[0])?.color ||
                    "#1890ff",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  marginBottom: 16,
                  boxShadow: `0 4px 12px ${nodeTypeOptions.find((t) => t.label === selectedNode.labels[0])?.color}40`,
                }}
              >
                <NodeIndexOutlined style={{ fontSize: 28, color: "#fff" }} />
              </div>
              <Title level={4} style={{ margin: 0, marginBottom: 8 }}>
                {selectedNode.properties?.name || selectedNode.id}
              </Title>
              <Space size={8}>
                <Tag
                  color={nodeTypeOptions.find((t) => t.label === selectedNode.labels[0])?.color}
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
