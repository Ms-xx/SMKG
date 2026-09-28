import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import DeduplicationPage from "./DeduplicationPage";

const detectMock = vi.fn();

vi.mock("@api/modules", () => ({
  dedupApi: {
    detect: (...args: unknown[]) => detectMock(...args),
    affiliations: vi.fn().mockResolvedValue({ affiliations: [] }),
  },
}));

const V1_ID = "doc-v1";
const V7_ID = "doc-v7";

const detectResult = {
  backend: "simhash",
  threshold: 0.85,
  total_documents: 2,
  duplicate_pairs: [{ a_id: V1_ID, b_id: V7_ID, similarity: 0.9062 }],
  cluster_count: 1,
  clusters: [
    {
      size: 2,
      document_ids: [V1_ID, V7_ID],
      documents: [
        { id: V1_ID, title: "attention_1706.03762v1.pdf", version: "v1" },
        { id: V7_ID, title: "attention_1706.03762v7.pdf", version: "v7" },
      ],
      suggestion: {
        keep: V7_ID,
        reason: "同源版本中保留最新版本（arXiv 版本号最高）",
      },
    },
  ],
};

const renderPage = () =>
  render(
    <MemoryRouter>
      <DeduplicationPage />
    </MemoryRouter>,
  );

describe("DeduplicationPage 版本管理", () => {
  beforeEach(() => {
    detectMock.mockReset();
    detectMock.mockResolvedValue(detectResult);
  });

  it("渲染页面标题与检测入口", () => {
    renderPage();
    expect(screen.getByText("语义去重与版本管理")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /检测重复/ })).toBeInTheDocument();
  });

  it("检测后展示 v1/v7 版本标签与保留最新建议", async () => {
    renderPage();
    fireEvent.click(screen.getByRole("button", { name: /检测重复/ }));

    await waitFor(() => expect(screen.getByText("检测结果")).toBeInTheDocument());

    // 版本号标签
    expect(screen.getByText("v1")).toBeInTheDocument();
    expect(screen.getByText("v7")).toBeInTheDocument();
    // 最新版本被标记为建议保留，旧版本标记可归档
    expect(screen.getAllByTestId("keep-tag").length).toBe(1);
    expect(screen.getAllByTestId("old-tag").length).toBe(1);
    expect(screen.getByText(/同源版本中保留最新版本/)).toBeInTheDocument();
  });

  it("存在最新版本建议时给出整体提示", async () => {
    renderPage();
    fireEvent.click(screen.getByRole("button", { name: /检测重复/ }));

    await waitFor(() =>
      expect(
        screen.getByText(/检测到 1 组同源版本，建议保留每组中版本号最高的文档/),
      ).toBeInTheDocument(),
    );
  });

  it("无重复时展示空态", async () => {
    detectMock.mockResolvedValue({
      ...detectResult,
      cluster_count: 0,
      clusters: [],
      duplicate_pairs: [],
    });
    renderPage();
    fireEvent.click(screen.getByRole("button", { name: /检测重复/ }));

    await waitFor(() => expect(screen.getByText("未发现语义重复的文档")).toBeInTheDocument());
  });
});
