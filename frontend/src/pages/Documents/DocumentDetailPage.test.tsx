import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import DocumentDetailPage from "./DocumentDetailPage";
import { useDocumentStore } from "@store/documentStore";

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
    expect(
      screen.getByText(/\[1\] 钙钛矿太阳能电池研究进展/),
    ).toBeInTheDocument();
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
});
