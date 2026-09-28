import ForceGraph2D from "react-force-graph-2d";
import { Button, Spin } from "antd";
import { AimOutlined } from "@ant-design/icons";
import type { GraphEntity, GraphRelation } from "@/types";
import { useRef, useMemo, memo } from "react";

const nodeColors: Record<string, string> = {
  Material: "#1890ff",
  Property: "#52c41a",
  Method: "#faad14",
  Parameter: "#722ed1",
  Document: "#13c2c2",
  Result: "#eb2f96",
  Chunk: "#8c8c8c",
};

// 节点显示文案：优先可读的标题/名称，其次“节点类型 + 内容预览”，最后才回退到类型标签，
// 避免把 UUID 之类技术 id 直接当节点文字展示
function readableNodeLabel(e: GraphEntity): string {
  if (e.properties.title && String(e.properties.title).length) return String(e.properties.title);
  if (e.properties.name && String(e.properties.name).length) return String(e.properties.name);
  if (typeof e.properties.content === "string" && e.properties.content.length) {
    const preview = e.properties.content.replace(/\s+/g, " ").slice(0, 12);
    return e.labels[0] ? `${e.labels[0]}·${preview}` : preview;
  }
  return e.labels[0] || e.id;
}

interface ForceGraphProps {
  entities: GraphEntity[];
  relations: GraphRelation[];
  onNodeClick?: (entity: GraphEntity) => void;
  loading?: boolean;
  // 异常节点高亮集合：命中节点以红色圆点/红色描边渲染
  highlightNodes?: Set<string>;
}

function ForceGraph({
  entities,
  relations,
  onNodeClick,
  loading,
  highlightNodes,
}: ForceGraphProps) {
  const graphRef = useRef<any>();

  // 节点较多时默认以“点”呈现，放大到足够比例才显示文字，避免标签拥挤重叠
  const tooMany = entities.length > 40;
  // 到达此缩放倍数后显示节点文字
  const labelZoom = tooMany ? 1.6 : 0;

  const handleFit = () => {
    graphRef.current?.zoomToFit(400, 60);
  };

  // 使用 useMemo 避免每次渲染重新创建 graphData
  const graphData = useMemo(
    () => ({
      nodes: entities.map((e) => ({
        id: e.id,
        label: readableNodeLabel(e),
        color: nodeColors[e.labels[0]] || "#999",
        highlighted: highlightNodes ? highlightNodes.has(e.id) : false,
        ...e.properties,
      })),
      links: relations.map((r) => ({
        source: r.startNode,
        target: r.endNode,
        label: r.type,
      })),
    }),
    [entities, relations, highlightNodes],
  );

  // 缓存 onNodeClick 回调
  const handleNodeClick = useMemo(() => {
    return (node: any) => onNodeClick?.(entities.find((e) => e.id === node.id)!);
  }, [onNodeClick, entities]);

  return (
    <div
      style={{
        position: "relative",
        width: "100%",
        height: "100%",
        borderRadius: 8,
        overflow: "hidden",
      }}
    >
      {loading && (
        <div
          style={{
            position: "absolute",
            inset: 0,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            zIndex: 10,
            background: "rgba(255,255,255,0.95)",
            backdropFilter: "blur(4px)",
          }}
        >
          <Spin size="large" />
        </div>
      )}
      <Button
        size="small"
        icon={<AimOutlined />}
        onClick={handleFit}
        style={{
          position: "absolute",
          top: 8,
          right: 8,
          zIndex: 5,
          boxShadow: "0 1px 4px rgba(0,0,0,0.15)",
        }}
        title="一键回到初始大小"
      >
        重置视图
      </Button>
      <ForceGraph2D
        ref={graphRef}
        graphData={graphData}
        nodeLabel="label"
        nodeColor="color"
        nodeRelSize={5}
        linkWidth={1.5}
        linkDirectionalParticles={2}
        linkDirectionalParticleWidth={2}
        linkDirectionalParticleSpeed={0.004}
        d3AlphaDecay={0.05}
        d3VelocityDecay={0.4}
        warmupTicks={60}
        cooldownTicks={60}
        onNodeClick={handleNodeClick}
        backgroundColor="#fafafa"
        nodeCanvasObject={(node: any, ctx: any, globalScale: number) => {
          // 放大到足够倍数(或节点数不多)才绘制文字标签；否则只画一个实心圆点
          const showText = !tooMany || globalScale >= labelZoom;
          ctx.lineWidth = 1;
          if (!showText) {
            ctx.beginPath();
            if (node.highlighted) {
              // 异常节点：红色实心圆 + 红色描边外圈
              ctx.fillStyle = "#ff4d4f";
              ctx.arc(node.x, node.y, 6, 0, 2 * Math.PI, false);
              ctx.fill();
              ctx.strokeStyle = "#ff4d4f";
              ctx.lineWidth = 2 / globalScale;
              ctx.beginPath();
              ctx.arc(node.x, node.y, 10, 0, 2 * Math.PI, false);
              ctx.stroke();
            } else {
              ctx.fillStyle = node.color || "#1890ff";
              ctx.arc(node.x, node.y, 4, 0, 2 * Math.PI, false);
              ctx.fill();
            }
            return;
          }
          // 截断较长文字，使标签更紧凑
          const raw = String(node.label || "");
          const label = raw.length > 14 ? `${raw.slice(0, 14)}…` : raw;
          const fontSize = 12 / globalScale;
          ctx.font = `${fontSize}px Sans-Serif`;
          const textWidth = ctx.measureText(label).width;
          const bckgDimensions = [textWidth, fontSize].map((n) => n + fontSize);

          // 异常节点用红色高亮（填充 + 描边），普通节点用自身类型色
          const fillColor = node.highlighted ? "#ff4d4f" : node.color || "#1890ff";

          // 节点圆角矩形背景
          ctx.fillStyle = fillColor;
          ctx.beginPath();
          ctx.roundRect(
            node.x - bckgDimensions[0] / 2 - 4,
            node.y - bckgDimensions[1] / 2,
            bckgDimensions[0] + 8,
            bckgDimensions[1],
            6,
          );
          ctx.fill();

          if (node.highlighted) {
            ctx.strokeStyle = "#ff4d4f";
            ctx.lineWidth = 2 / globalScale;
            ctx.stroke();
          }

          // 节点文字
          ctx.textAlign = "center";
          ctx.textBaseline = "middle";
          ctx.fillStyle = "#fff";
          ctx.fillText(label, node.x, node.y);
        }}
        nodePointerAreaPaint={(node: any, color: string, ctx: any) => {
          ctx.fillStyle = color;
          ctx.beginPath();
          ctx.arc(node.x, node.y, 8, 0, 2 * Math.PI, false);
          ctx.fill();
        }}
      />
    </div>
  );
}

// 使用 memo 避免不必要的重渲染
export default memo(ForceGraph);
