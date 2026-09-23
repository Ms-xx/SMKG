import { describe, it, expect, beforeAll, beforeEach, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";

const apiHolder = vi.hoisted(() => ({
  search: vi.fn(),
  downloadAndIngest: vi.fn(),
  message: { success: vi.fn(), warning: vi.fn(), error: vi.fn() },
}));

// antd 的 message 使用 ref 渲染，jsdom 下难以直接断言；
// 参照项目既有约定 mock antd 的 message，其余 antd 组件保持原样。
vi.mock("antd", async (importOriginal) => {
  const actual: any = await importOriginal();
  return { ...actual, message: apiHolder.message };
});

vi.mock("@api/modules", () => ({
  paperRetrievalApi: {
    search: apiHolder.search,
    downloadAndIngest: apiHolder.downloadAndIngest,
  },
}));

import PaperRetrievalPage from "./PaperRetrievalPage";

const mockResult = {
  arxiv_id: "2401.00123",
  title: "Graph Neural Networks for Materials",
  authors: ["Alice", "Bob"],
  source: "arxiv",
  published: "2024-01-02",
  summary: "A paper about GNN for materials.",
};

describe("PaperRetrievalPage", () => {
  beforeAll(() => {
    // jsdom 未实现 Element.scrollIntoView
    Object.defineProperty(Element.prototype, "scrollIntoView", {
      writable: true,
      value: () => {},
    });
  });

  beforeEach(() => {
    vi.clearAllMocks();
    apiHolder.search.mockResolvedValue({ results: [mockResult] });
    apiHolder.downloadAndIngest.mockResolvedValue({
      ingested: true,
      document_id: "doc-abcdef",
      parsing: { status: "parsed" },
    });
  });

  it("渲染行内「下载入库」按钮", async () => {
    render(
      <MemoryRouter>
        <PaperRetrievalPage />
      </MemoryRouter>,
    );
    await userEvent.click(screen.getByRole("button", { name: /检\s*索/ }));

    expect(await screen.findByRole("button", { name: /下载入库/ })).toBeInTheDocument();
  });

  it("触发下载入库后调用 downloadAndIngest 并以 message.success 提示", async () => {
    render(
      <MemoryRouter>
        <PaperRetrievalPage />
      </MemoryRouter>,
    );
    await userEvent.click(screen.getByRole("button", { name: /检\s*索/ }));
    await userEvent.click(await screen.findByRole("button", { name: /下载入库/ }));

    await vi.waitFor(() => expect(apiHolder.downloadAndIngest).toHaveBeenCalledTimes(1));
    expect(apiHolder.downloadAndIngest).toHaveBeenCalledWith({
      result: {
        source: "arxiv",
        arxiv_id: "2401.00123",
        pubmed_id: undefined,
        title: "Graph Neural Networks for Materials",
      },
    });
    expect(apiHolder.message.success).toHaveBeenCalled();
  });
});