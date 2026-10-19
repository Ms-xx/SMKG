import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import ResearchInsightsPage from "./ResearchInsightsPage";

const holders = vi.hoisted(() => ({
  documentApi: { getList: vi.fn() },
  sourceAnchorApi: { compareMatrix: vi.fn() },
  citationQualityApi: { score: vi.fn() },
  citationGraphApi: { futureWork: vi.fn() },
}));

vi.mock("@api/modules", () => ({
  documentApi: holders.documentApi,
  sourceAnchorApi: holders.sourceAnchorApi,
  citationQualityApi: holders.citationQualityApi,
  citationGraphApi: holders.citationGraphApi,
}));

const renderPage = (url = "/research-insights") =>
  render(
    <MemoryRouter initialEntries={[url]}>
      <ResearchInsightsPage />
    </MemoryRouter>,
  );

describe("ResearchInsightsPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    holders.documentApi.getList.mockResolvedValue({
      items: [],
      total: 0,
      page: 1,
      page_size: 200,
    });
  });

  it("渲染标题、三个页签与文献选择", async () => {
    renderPage();

    expect(screen.getByText("研究洞察（需求对标补强）")).toBeInTheDocument();
    expect(screen.getByText(/步骤 19/)).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: /跨文献对比矩阵/ })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: /引用含金量/ })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: /前沿探索/ })).toBeInTheDocument();
    expect(screen.getByText("文献选择")).toBeInTheDocument();
    expect(await screen.findByText(/共 0 篇可选/)).toBeInTheDocument();
  });

  it("未选择文献时按钮禁用并展示空态", () => {
    renderPage();

    expect(screen.getByText("选择至少 1 篇文献后构建对比矩阵")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /构建对比矩阵/ })).toBeDisabled();
  });

  it("预选文献后构建对比矩阵，渲染覆盖率/洞察/单元与无锚点标记", async () => {
    holders.sourceAnchorApi.compareMatrix.mockResolvedValue({
      backend: "auto",
      dimension_count: 6,
      document_count: 2,
      dimensions: ["architecture", "parameter_count"],
      document_columns: [
        { index: 0, document_id: "d1", title: "论文A" },
        { index: 1, document_id: "d2", title: "论文B" },
      ],
      rows: [
        {
          dimension: "architecture",
          cells: [
            {
              document_id: "d1",
              title: "论文A",
              value: "encoder-decoder",
              anchored: true,
              anchors: [
                { document_id: "d1", page: 3, chunk: null, snippet: "we use an encoder-decoder" },
              ],
            },
            {
              document_id: "d2",
              title: "论文B",
              value: null,
              anchored: false,
              anchors: [],
              note: "无锚点，不出结论（原文未定位到该维度的可核查证据）。",
            },
          ],
        },
      ],
      anchor_coverage: { total_cells: 12, anchored_cells: 7, coverage_pct: 58.33 },
      insight: {
        backend: "rule",
        matrix_backend: "auto",
        insight: "规则洞察：矩阵覆盖 2 篇文献 × 6 个维度。",
        note: "",
      },
    });

    renderPage("/research-insights?docs=d1,d2");
    await userEvent.click(screen.getByRole("button", { name: /构建对比矩阵/ }));

    expect(await screen.findByText("锚点覆盖率：58.33%")).toBeInTheDocument();
    expect(screen.getByText("规则洞察：矩阵覆盖 2 篇文献 × 6 个维度。")).toBeInTheDocument();
    expect(screen.getByText("encoder-decoder")).toBeInTheDocument();
    expect(screen.getAllByText("无锚点").length).toBeGreaterThan(0);
    expect(holders.sourceAnchorApi.compareMatrix).toHaveBeenCalledWith({
      documents: [{ document_id: "d1" }, { document_id: "d2" }],
    });
  });

  it("切换引用含金量页签并评估，渲染统计与档位/信号", async () => {
    holders.citationQualityApi.score.mockResolvedValue({
      backend: "builtin",
      document_count: 1,
      total_refs: 2,
      perfunctory_count: 1,
      core_count: 1,
      documents: [
        {
          document_id: "d1",
          title: "论文A",
          total: 2,
          core_count: 1,
          supporting_count: 0,
          perfunctory_count: 1,
          thresholds: { perfunctory_threshold: 0.4, supporting_threshold: 0.7 },
          refs: [
            {
              index: 1,
              title: "Attention Is All You Need",
              score: 0.85,
              label: "core",
              position: "abstract",
              occurrences: 4,
              signals: [
                { signal: "position", level: 0.9, detail: "abstract" },
                { signal: "occurrences", level: 4, detail: "正文出现 4 次" },
                { signal: "conclusion", hit: true },
                { signal: "cites_edge", hit: true },
              ],
            },
            {
              index: 2,
              title: "A related work listing",
              score: 0.25,
              label: "perfunctory",
              position: "related_work",
              occurrences: 1,
              signals: [
                { signal: "position", level: 0.25, detail: "related_work" },
                { signal: "occurrences", level: 1, detail: "正文出现 1 次" },
                { signal: "conclusion", hit: false },
                { signal: "cites_edge", hit: false },
              ],
            },
          ],
        },
      ],
    });

    renderPage("/research-insights?docs=d1");
    await userEvent.click(screen.getByRole("tab", { name: /引用含金量/ }));
    await userEvent.click(screen.getByRole("button", { name: /评估引用含金量/ }));

    expect(await screen.findByText("参考文献总数")).toBeInTheDocument();
    expect(screen.getAllByText("核心支撑").length).toBeGreaterThan(0);
    expect(screen.getAllByText("应付式").length).toBeGreaterThan(0);
    expect(screen.getByText("Attention Is All You Need")).toBeInTheDocument();
    expect(screen.getByText(/位置:abstract/)).toBeInTheDocument();
    expect(holders.citationQualityApi.score).toHaveBeenCalledWith(["d1"]);
  });

  it("切换前沿探索页签并扫描，渲染时间桶/待探索/已被解决", async () => {
    holders.citationGraphApi.futureWork.mockResolvedValue({
      backend: "builtin",
      idea_count: 2,
      excluded_count: 1,
      candidate_count: 1,
      time_buckets: [{ year: 2017, count: 2 }],
      excluded: [
        {
          document_id: "d2",
          title: "论文B",
          year: 2019,
          keyword: "future work",
          idea: "探索更高效的位置编码",
          snippet: "...",
          resolved: true,
          confidence: 0.95,
          resolved_by: ["d3"],
          evidence: [{ document_id: "d3", title: "论文C", year: 2021 }],
          reason: "被后续论文解决（命中关键词+解决表述）",
        },
      ],
      candidates: [
        {
          document_id: "d1",
          title: "论文A",
          year: 2017,
          keyword: "future work",
          idea: "将模型扩展到多模态输入",
          snippet: "...",
          resolved: false,
          confidence: 0.5,
          resolved_by: [],
          evidence: [],
          reason: "未发现后续论文解决该 idea",
        },
      ],
      filtered: { domain: null, min_year: null, max_year: null, applied_document_count: 2 },
    });

    renderPage();
    await userEvent.click(screen.getByRole("tab", { name: /前沿探索/ }));
    await userEvent.click(screen.getByRole("button", { name: /扫描前沿方向/ }));

    expect(await screen.findByText("待探索：1")).toBeInTheDocument();
    expect(screen.getByText("已被解决：1")).toBeInTheDocument();
    expect(screen.getByText("2017：2 篇")).toBeInTheDocument();
    expect(screen.getByText("将模型扩展到多模态输入")).toBeInTheDocument();
    expect(screen.getByText("探索更高效的位置编码")).toBeInTheDocument();
    expect(holders.citationGraphApi.futureWork).toHaveBeenCalledWith({
      domain: undefined,
      min_year: undefined,
      max_year: undefined,
    });
  });
});
