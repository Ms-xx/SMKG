import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen, act, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import GraphExplorer from "./GraphExplorer";
import { useAuthStore } from "@store/authStore";

// 捕获 mock 组件的 props，便于断言传入的数据与点击回调
const forceGraphHolder = vi.hoisted(() => ({ props: null as any }));

vi.mock("@components/Graph/ForceGraph", () => ({
  default: (props: any) => {
    forceGraphHolder.props = props;
    return (
      <div
        data-testid="force-graph-mock"
        data-loading={String(!!props.loading)}
        data-entities={String(props.entities?.length ?? 0)}
      />
    );
  },
}));

const apiHolder = vi.hoisted(() => ({
  graphApi: {
    ragGraphStats: vi.fn(),
    ragSearchNodes: vi.fn(),
    ragNodesByLabel: vi.fn(),
    ragGraphSearch: vi.fn(),
    ragClearGraph: vi.fn(),
    getNodeTypes: vi.fn(),
    createNodeType: vi.fn(),
    deleteNodeType: vi.fn(),
    getTrends: vi.fn(),
    getAnomalies: vi.fn(),
  },
}));

vi.mock("@api/modules", () => ({
  graphApi: apiHolder.graphApi,
}));

// mock echarts 渲染，避免真实 canvas 依赖
vi.mock("echarts-for-react", () => ({
  default: (_props: any) => <div data-testid="trend-chart" />,
}));

describe("GraphExplorer", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    forceGraphHolder.props = null;
    localStorage.clear();
    useAuthStore.setState({
      isAuthenticated: true,
      user: null,
      permissions: [],
      token: "test-token",
    });

    apiHolder.graphApi.ragGraphStats.mockResolvedValue({
      data: { total_nodes: 42, total_relations: 7, node_labels: { Material: 3 } },
    });
    apiHolder.graphApi.ragNodesByLabel.mockResolvedValue({ data: { nodes: [] } });
    apiHolder.graphApi.ragGraphSearch.mockResolvedValue({ data: { relations: [] } });
    apiHolder.graphApi.ragSearchNodes.mockResolvedValue({ data: { nodes: [] } });
    apiHolder.graphApi.ragClearGraph.mockResolvedValue({ data: {} });
    apiHolder.graphApi.getNodeTypes.mockResolvedValue({
      data: { items: [{ label: "Material", name: "材料", color: "#1890ff", is_default: true }] },
    });
    apiHolder.graphApi.createNodeType.mockResolvedValue({ data: {} });
    apiHolder.graphApi.deleteNodeType.mockResolvedValue({ data: {} });
    apiHolder.graphApi.getTrends.mockResolvedValue({ data: { timeline: [], top_entities: [] } });
    apiHolder.graphApi.getAnomalies.mockResolvedValue({
      data: {
        anomalies: [],
        isolated: { count: 0, nodes: [] },
        high_connectivity: { count: 0, nodes: [] },
        low_connectivity: { count: 0, nodes: [] },
      },
    });
  });

  it("渲染页面标题与统计卡片", async () => {
    render(
      <MemoryRouter>
        <GraphExplorer />
      </MemoryRouter>,
    );

    expect(screen.getByText("知识图谱探索")).toBeInTheDocument();
    expect(
      screen.getByText("交互式可视化知识图谱，支持节点搜索、筛选和详情查看"),
    ).toBeInTheDocument();
    expect(screen.getByText("实体总数")).toBeInTheDocument();
    expect(screen.getByText("关系总数")).toBeInTheDocument();
    expect(screen.getByText("节点分布：")).toBeInTheDocument();
    // 统计接口返回后显示实体总数
    expect(await screen.findByText("42")).toBeInTheDocument();
  });

  it("加载实体后将数据传入 ForceGraph", async () => {
    apiHolder.graphApi.ragNodesByLabel.mockResolvedValue({
      data: { nodes: [{ id: "e1", label: "Material", properties: { id: "e1" } }] },
    });

    render(
      <MemoryRouter>
        <GraphExplorer />
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(forceGraphHolder.props?.entities?.length ?? 0).toBe(1);
    });
  });

  it("搜索节点调用 ragSearchNodes", async () => {
    render(
      <MemoryRouter>
        <GraphExplorer />
      </MemoryRouter>,
    );

    await screen.findByText("实体总数");
    const input = screen.getByPlaceholderText("搜索实体关键词...");
    await userEvent.type(input, "钙钛矿{enter}");

    expect(apiHolder.graphApi.ragSearchNodes).toHaveBeenCalledWith("钙钛矿", 50);
  });

  it("点击节点打开实体详情抽屉", async () => {
    apiHolder.graphApi.ragNodesByLabel.mockResolvedValue({
      data: { nodes: [{ id: "e1", label: "Material", properties: { id: "e1", name: "节点A" } }] },
    });

    render(
      <MemoryRouter>
        <GraphExplorer />
      </MemoryRouter>,
    );

    await screen.findByTestId("force-graph-mock");
    act(() => {
      forceGraphHolder.props.onNodeClick({
        id: "e1",
        labels: ["Material"],
        properties: { name: "氧化铝", formula: "CH3NH3PbI3" },
      });
    });

    expect(await screen.findByText("实体详情")).toBeInTheDocument();
    expect(screen.getByText("氧化铝")).toBeInTheDocument();
    expect(screen.getByText("CH3NH3PbI3")).toBeInTheDocument();
  });

  it("添加自定义节点类型调用 createNodeType", async () => {
    render(
      <MemoryRouter>
        <GraphExplorer />
      </MemoryRouter>,
    );

    await screen.findByText("实体总数");
    await userEvent.type(screen.getByPlaceholderText("label（英文）"), "Catalyst");
    await userEvent.type(screen.getByPlaceholderText("中文名（可选）"), "催化剂");
    await userEvent.click(screen.getByRole("button", { name: /添加/ }));

    expect(apiHolder.graphApi.createNodeType).toHaveBeenCalledWith({
      label: "Catalyst",
      name: "催化剂",
      color: "#1890ff",
    });
  });

  it("加载趋势分析与异常检测并高亮异常节点", async () => {
    apiHolder.graphApi.getAnomalies.mockResolvedValue({
      data: {
        anomalies: [{ kind: "isolated", node_id: "e1", node_label: "节点A" }],
        isolated: { count: 1, nodes: [{ id: "e1" }] },
        high_connectivity: { count: 0, nodes: [] },
        low_connectivity: { count: 0, nodes: [] },
      },
    });

    render(
      <MemoryRouter>
        <GraphExplorer />
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(apiHolder.graphApi.getTrends).toHaveBeenCalled();
      expect(apiHolder.graphApi.getAnomalies).toHaveBeenCalled();
      // 异常节点 id 集合经 onAnomalyHighlight 回传给 ForceGraph
      expect(forceGraphHolder.props?.highlightNodes?.has("e1")).toBe(true);
    });
    // 异常检测面板渲染出异常标签
    expect(screen.getByText("节点A")).toBeInTheDocument();
  });
});
