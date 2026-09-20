import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import ForceGraph from "./ForceGraph";

const holder = vi.hoisted(() => ({ props: null as any }));

vi.mock("react-force-graph-2d", () => ({
  default: (props: any) => {
    holder.props = props;
    return (
      <div
        data-testid="force-graph"
        data-nodes={props?.graphData?.nodes?.length}
        data-links={props?.graphData?.links?.length}
      />
    );
  },
}));

const entities = [
  { id: "e1", labels: ["Material"], properties: { name: "氧化铝" } },
  { id: "e2", labels: ["Unknown"], properties: {} },
];
const relations = [
  { id: "r1", type: "HAS_PROPERTY", startNode: "e1", endNode: "e2", properties: {} },
];

describe("ForceGraph", () => {
  it("渲染力导向图并生成节点/边数据", () => {
    render(<ForceGraph entities={entities} relations={relations} />);
    const el = screen.getByTestId("force-graph");
    expect(el).toBeInTheDocument();
    expect(el.getAttribute("data-nodes")).toBe("2");
    expect(el.getAttribute("data-links")).toBe("1");
  });

  it("loading 时显示加载指示器", () => {
    render(<ForceGraph entities={entities} relations={relations} loading />);
    expect(document.querySelector(".ant-spin")).toBeTruthy();
  });

  it("点击节点触发回调", () => {
    const onNodeClick = vi.fn();
    render(<ForceGraph entities={entities} relations={relations} onNodeClick={onNodeClick} />);
    holder.props.onNodeClick({ id: "e2" });
    expect(onNodeClick).toHaveBeenCalledWith(entities[1]);
  });

  it("未提供回调时点击不报错", () => {
    render(<ForceGraph entities={entities} relations={relations} />);
    expect(() => holder.props.onNodeClick({ id: "e1" })).not.toThrow();
  });

  it("绘制节点背景与指针区域", () => {
    render(<ForceGraph entities={entities} relations={relations} />);
    const ctx: any = {
      measureText: () => ({ width: 20 }),
      roundRect: vi.fn(),
      beginPath: vi.fn(),
      fill: vi.fn(),
      fillText: vi.fn(),
      arc: vi.fn(),
    };
    const node = { label: "氧化铝", color: "#1890ff", x: 10, y: 20 };
    holder.props.nodeCanvasObject(node, ctx, 2);
    expect(ctx.fill).toHaveBeenCalled();
    expect(ctx.fillText).toHaveBeenCalledWith("氧化铝", 10, 20);

    holder.props.nodePointerAreaPaint(node, "#fff", ctx);
    expect(ctx.arc).toHaveBeenCalled();
  });
});
