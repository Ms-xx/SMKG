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
  publication_date: "2026-01-01",
  page_count: 10,
  file_size: 2097152,
  keywords: ["组合", "材料"],
  abstract: "摘要内容",
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
    expect(screen.getByText("2.00 MB")).toBeInTheDocument();
    expect(screen.getByText("进入标注工作台")).toBeInTheDocument();
  });
});
