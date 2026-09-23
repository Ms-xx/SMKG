import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import DocumentDetailPage from "./DocumentDetailPage";
import { useDocumentStore } from "@store/documentStore";
import { documentApi, citationLinkApi, writingAssistantApi } from "@api/modules";

vi.mock("@api/modules", async (importOriginal) => {
  const actual = (await importOriginal()) as Record<string, unknown>;
  const spread = (o: unknown) => ({ ...(o as object) });
  return {
    ...actual,
    documentApi: { ...spread(actual.documentApi), getFullText: vi.fn() },
    citationLinkApi: { ...spread(actual.citationLinkApi), map: vi.fn() },
    writingAssistantApi: {
      ...spread(actual.writingAssistantApi),
      translate: vi.fn(),
    },
  };
});

const doc = {
  id: "d1",
  title: "测试论文",
  status: "parsed",
  doi: "10.1/x",
  journal: "Nature",
  authors: ["张三"],
  affiliations: ["中国科学院材料研究所"],
  publication_date: "2026-01-01",
  page_count: 10,
  file_size: 2097152,
  keywords: ["组合", "材料"],
  abstract: "摘要内容",
  references: [
    {
      index: 1,
      authors: "张三, 李四",
      title: "钙钛矿太阳能电池研究进展",
      journal: "材料科学学报",
      year: "2023",
      volume: "45",
      issue: "3",
      pages: "123-130",
      doi: "10.1000/xyz",
      type: "journal",
      raw: "张三,李四. 钙钛矿太阳能电池研究进展[J]. 材料科学学报, 2023, 45(3): 123-130.",
    },
  ],
  created_at: "2026-01-01T00:00:00",
  updated_at: "2026-01-02T00:00:00",
} as any;

const renderPage = () =>
  render(
    <MemoryRouter initialEntries={["/documents/d1"]}>
      <Routes>
        <Route path="/documents/:id" element={<DocumentDetailPage />} />
      </Routes>
    </MemoryRouter>,
  );

describe("DocumentDetailPage", () => {
  beforeEach(() => {
    useDocumentStore.setState({
      currentDocument: null,
      fetchDocument: vi.fn(),
      triggerParse: vi.fn(),
    });
    // 默认：无正文、无引用映射、翻译回显占位（不干扰既有用例）
    vi.mocked(documentApi.getFullText).mockResolvedValue({
      document_id: "d1",
      page_count: 0,
      pages: [],
    });
    vi.mocked(citationLinkApi.map).mockResolvedValue({
      backend: "rule",
      total_citations: 0,
      references_count: 0,
      citations: [],
      by_reference: {},
    });
    vi.mocked(writingAssistantApi.translate).mockResolvedValue({
      backend: "llm",
      text: "译文占位",
      target: "zh",
    });
  });

  it("无当前文档时显示加载态", () => {
    renderPage();
    expect(screen.queryByText("测试论文")).toBeNull();
    expect(screen.queryByText("文档详情")).toBeNull();
  });

  it("展示文档详情与字段", () => {
    useDocumentStore.setState({ currentDocument: doc });
    renderPage();
    expect(screen.getByText("测试论文")).toBeInTheDocument();
    expect(screen.getByText("已解析")).toBeInTheDocument();
    expect(screen.getByText("Nature")).toBeInTheDocument();
    expect(screen.getByText("张三")).toBeInTheDocument();
    expect(screen.getByText("中国科学院材料研究所")).toBeInTheDocument();
    expect(screen.getByText("2.00 MB")).toBeInTheDocument();
    expect(screen.getByText("进入标注工作台")).toBeInTheDocument();
  });

  it("展示参考文献列表（含作者/期刊/年份/DOI）", () => {
    useDocumentStore.setState({ currentDocument: doc });
    renderPage();
    expect(screen.getByText("参考文献（1）")).toBeInTheDocument();
    expect(screen.getByText(/\[1\] 钙钛矿太阳能电池研究进展/)).toBeInTheDocument();
    expect(
      screen.getByText("张三, 李四 · 材料科学学报 · 2023 · 45(3) · 123-130 · 10.1000/xyz"),
    ).toBeInTheDocument();
  });

  it("正文引用标注 [n] 与参考文献双向跳转", () => {
    useDocumentStore.setState({
      currentDocument: {
        ...doc,
        abstract: "钙钛矿材料具有高转化效率[1]，且稳定性良好[1,2]。",
      },
    });
    renderPage();
    // 摘要中的 [1] 变为可点击链接并带 cite 锚点，指向 ref-1
    expect(document.getElementById("cite-1")?.getAttribute("href")).toBe("#ref-1");
    // 未在参考文献中的编号 [2] 保持纯文本，不生成链接
    expect(document.getElementById("cite-2")).toBeNull();
    // 参考文献项带 ref 锚点与「回到正文」
    expect(document.getElementById("ref-1")).not.toBeNull();
    expect(screen.getByText("回到正文")).toBeInTheDocument();
  });

  it("正文全文渲染并支持 [n] 引用↔参考文献双向跳转（5.1）", async () => {
    vi.mocked(documentApi.getFullText).mockResolvedValue({
      document_id: "d1",
      page_count: 1,
      pages: [{ page_number: 1, text: "引言正文[1]与后续研究。" }],
    });
    vi.mocked(citationLinkApi.map).mockResolvedValue({
      backend: "rule",
      total_citations: 1,
      references_count: 1,
      citations: [
        {
          ref_index: 1,
          start: 4,
          end: 7,
          kind: "numeric",
          raw: "[1]",
          snippet: "",
          page_index: 0,
          page_number: 1,
        },
      ],
      by_reference: {
        "1": [
          {
            ref_index: 1,
            start: 4,
            end: 7,
            kind: "numeric",
            raw: "[1]",
            snippet: "",
            page_index: 0,
            page_number: 1,
          },
        ],
      },
    });
    useDocumentStore.setState({ currentDocument: { ...doc, status: "parsed" } });
    renderPage();

    // 正文全文展示
    expect(await screen.findByText(/引言正文/)).toBeInTheDocument();
    // 正文 [1] 生成可点击锚点，指向参考文献 ref-1
    const anchor = document.getElementById("body-cite-1-4");
    expect(anchor).not.toBeNull();
    expect(anchor?.querySelector("a")?.getAttribute("href")).toBe("#ref-1");
    // 参考文献「回到正文引用」命中正文引用位置
    expect(await screen.findByText("回到正文引用")).toBeInTheDocument();
  });

  it("整篇翻译触发 translate 并展示对照译文（5.3）", async () => {
    vi.mocked(documentApi.getFullText).mockResolvedValue({
      document_id: "d1",
      page_count: 1,
      pages: [{ page_number: 1, text: "Graph neural networks predict properties." }],
    });
    vi.mocked(writingAssistantApi.translate).mockResolvedValue({
      backend: "llm",
      text: "图神经网络可预测材料性质。",
      target: "zh",
    });
    useDocumentStore.setState({ currentDocument: { ...doc, status: "parsed" } });
    renderPage();

    const btn = await screen.findByRole("button", { name: /整篇翻译/ });
    fireEvent.click(btn);

    expect(await screen.findByText("图神经网络可预测材料性质。")).toBeInTheDocument();
    expect(writingAssistantApi.translate).toHaveBeenCalledWith({
      text: "Graph neural networks predict properties.",
      target: "zh",
    });
  });

  it("切换中英对照自动逐页翻译（5.2）", async () => {
    vi.mocked(documentApi.getFullText).mockResolvedValue({
      document_id: "d1",
      page_count: 1,
      pages: [{ page_number: 1, text: "Attention is all you need." }],
    });
    vi.mocked(writingAssistantApi.translate).mockResolvedValue({
      backend: "llm",
      text: "注意力机制是核心。",
      target: "zh",
    });
    useDocumentStore.setState({ currentDocument: { ...doc, status: "parsed" } });
    renderPage();

    fireEvent.click(await screen.findByText("中英对照"));

    expect(await screen.findByText("注意力机制是核心。")).toBeInTheDocument();
    expect(writingAssistantApi.translate).toHaveBeenCalled();
  });
});
