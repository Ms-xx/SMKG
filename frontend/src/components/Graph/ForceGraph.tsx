import ForceGraph2D from "react-force-graph-2d";
import { Spin } from "antd";
import type { GraphEntity, GraphRelation } from "@/types";
import { useRef, useMemo, memo } from "react";

const nodeColors: Record<string, string> = {
  Material: "#1890ff",
  Property: "#52c41a",
  Method: "#faad14",
  Parameter: "#722ed1",
  Document: "#13c2c2",
  Result: "#eb2f96",
};

interface ForceGraphProps {
  entities: GraphEntity[];
  relations: GraphRelation[];
  onNodeClick?: (entity: GraphEntity) => void;
  loading?: boolean;
}

function ForceGraph({ entities, relations, onNodeClick, loading }: ForceGraphProps) {
  const graphRef = useRef<any>();

  // 使用 useMemo 避免每次渲染重新创建 graphData
  const graphData = useMemo(
    () => ({
      nodes: entities.map((e) => ({
        id: e.id,
        label: e.properties.name || e.id,
        color: nodeColors[e.labels[0]] || "#999",
        ...e.properties,
      })),
      links: relations.map((r) => ({
        source: r.startNode,
        target: r.endNode,
        label: r.type,
      })),
    }),
    [entities, relations],
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
      <ForceGraph2D
        ref={graphRef}
        graphData={graphData}
        nodeLabel="label"
        nodeColor="color"
        nodeRelSize={6}
        linkWidth={2}
        linkDirectionalParticles={2}
        linkDirectionalParticleWidth={3}
        linkDirectionalParticleSpeed={0.005}
        onNodeClick={handleNodeClick}
        backgroundColor="#fafafa"
        nodeCanvasObject={(node: any, ctx: any, globalScale: number) => {
          const label = node.label;
          const fontSize = 12 / globalScale;
          ctx.font = `${fontSize}px Sans-Serif`;
          const textWidth = ctx.measureText(label).width;
          const bckgDimensions = [textWidth, fontSize].map((n) => n + fontSize);

          // 节点圆角矩形背景
          ctx.fillStyle = node.color || "#1890ff";
          ctx.beginPath();
          ctx.roundRect(
            node.x - bckgDimensions[0] / 2 - 4,
            node.y - bckgDimensions[1] / 2,
            bckgDimensions[0] + 8,
            bckgDimensions[1],
            6,
          );
          ctx.fill();

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
