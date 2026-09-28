import { useEffect, useState } from "react";
import { Card, Col, Row, Space, Spin, Tag, Empty, message } from "antd";
import { LineChartOutlined, WarningOutlined } from "@ant-design/icons";
import ReactECharts from "echarts-for-react";
import { graphApi } from "@api/modules";

const anomalyTypeColor: Record<string, string> = {
  isolated: "#faad14",
  high_connectivity: "#ff4d4f",
  low_connectivity: "#52c41a",
};

interface GraphInsightsProps {
  onAnomalyHighlight?: (nodeIds: Set<string>) => void;
}

/**
 * 知识图谱高级能力面板：趋势分析（折线图）+ 异常检测（统计与列表、图谱高亮）。
 * 数据来自 /knowledge-graph/trends 与 /knowledge-graph/anomalies。
 */
export default function GraphInsights({ onAnomalyHighlight }: GraphInsightsProps) {
  const [trends, setTrends] = useState<any>(null);
  const [anomalies, setAnomalies] = useState<any>(null);
  const [loading, setLoading] = useState(false);

  const loadTrends = async () => {
    try {
      const res: any = await graphApi.getTrends();
      setTrends(res.data || res);
    } catch {
      message.warning("趋势分析暂不可用");
    }
  };

  const loadAnomalies = async () => {
    setLoading(true);
    try {
      const res: any = await graphApi.getAnomalies();
      const data = res.data || res;
      setAnomalies(data);
      // 汇总全部异常节点 id 用于图谱高亮
      const ids = new Set<string>();
      (data?.anomalies ?? []).forEach((a: any) => {
        if (a.node_id) ids.add(a.node_id);
      });
      onAnomalyHighlight?.(ids);
    } catch {
      message.warning("异常检测暂不可用");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadTrends();
    loadAnomalies();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // 折线图：x=时间桶，每条 series 为一个热点实体类型的节点计数
  const chartOption = (() => {
    const timeline = trends?.timeline ?? [];
    const periods = timeline.map((t: any) => t.period);
    const labels = (trends?.top_entities ?? []).slice(0, 6).map((e: any) => e.label);
    return {
      tooltip: { trigger: "axis" },
      legend: { type: "scroll", bottom: 0 },
      grid: { left: 16, right: 16, top: 32, bottom: 40, containLabel: true },
      xAxis: { type: "category", data: periods },
      yAxis: { type: "value", minInterval: 1 },
      series: labels.map((label: string) => ({
        name: label,
        type: "line",
        smooth: true,
        data: timeline.map((t: any) => t.entity_counts?.[label] ?? 0),
      })),
    };
  })();

  const anomalyGroups = [
    { key: "isolated", title: "孤立节点" },
    { key: "high_connectivity", title: "超连通" },
    { key: "low_connectivity", title: "低连通" },
  ];

  return (
    <Row gutter={16} style={{ marginTop: 16 }}>
      <Col span={14}>
        <Card
          size="small"
          title={
            <Space>
              <LineChartOutlined style={{ color: "#1890ff" }} />
              趋势分析（按实体类型按时间演进）
            </Space>
          }
        >
          {trends && timelineHasData(trends) ? (
            <ReactECharts option={chartOption} style={{ height: 300 }} notMerge />
          ) : (
            <Empty description="暂无趋势数据" style={{ padding: 40 }}>
              <Tag>已分析实体 {trends?.coverage?.total_nodes ?? 0} 个</Tag>
            </Empty>
          )}
          {trends?.top_entities?.length > 0 && (
            <Space size={[8, 8]} wrap style={{ marginTop: 8 }}>
              <Tag color="blue">
                热点实体 TOP：
                {trends.top_entities
                  .slice(0, 3)
                  .map((e: any) => `${e.label}(${e.count})`)
                  .join("、")}
              </Tag>
            </Space>
          )}
        </Card>
      </Col>
      <Col span={10}>
        <Card
          size="small"
          title={
            <Space>
              <WarningOutlined style={{ color: "#ff4d4f" }} />
              异常检测
            </Space>
          }
          extra={
            <Tag color={anomalies ? (anomalies.anomalies?.length ? "red" : "green") : "default"}>
              {anomalies?.anomalies?.length ?? 0} 条
            </Tag>
          }
        >
          {loading && <Spin size="small" />}
          <Row gutter={8}>
            {anomalyGroups.map((g) => {
              const group = anomalies?.[g.key] ?? { count: 0, nodes: [] };
              return (
                <Col span={8} key={g.key}>
                  <div
                    style={{
                      textAlign: "center",
                      padding: "8px 4px",
                      borderRadius: 8,
                      background: `${anomalyTypeColor[g.key]}22`,
                    }}
                  >
                    <div style={{ fontSize: 20, fontWeight: 600, color: anomalyTypeColor[g.key] }}>
                      {group.count ?? 0}
                    </div>
                    <div style={{ fontSize: 12, color: "#595959" }}>{g.title}</div>
                  </div>
                </Col>
              );
            })}
          </Row>
          <div style={{ marginTop: 12, maxHeight: 120, overflow: "auto" }}>
            {anomalies?.anomalies?.length ? (
              anomalies.anomalies.slice(0, 8).map((a: any, i: number) => (
                <Tag key={i} color={anomalyTypeColor[a.kind]} style={{ marginBottom: 4 }}>
                  {a.node_label || a.node_id || a.kind}
                </Tag>
              ))
            ) : (
              <div style={{ color: "#8c8c8c", fontSize: 12 }}>未发现异常节点</div>
            )}
          </div>
        </Card>
      </Col>
    </Row>
  );
}

function timelineHasData(trends: any): boolean {
  return (trends?.timeline ?? []).some((t: any) => Object.keys(t?.entity_counts ?? {}).length);
}
