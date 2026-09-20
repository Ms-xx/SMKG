import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import DocumentListPage from "./DocumentListPage";
import { useDocumentStore } from "@store/documentStore";

const docs = [
  { id: "d1", title: "论文A", status: "parsed", page_count: 10, created_at: "2026-01-01T00:00:00" },
  {
    id: "d2",
    title: "论文B",
    status: "uploaded",
    page_count: 3,
    created_at: "2026-01-02T00:00:00",
  },
] as any;

describe("DocumentListPage", () => {
  beforeEach(() => {
    useDocumentStore.setState({
      documents: docs,
      total: 2,
      loading: false,
      filters: {},
      fetchDocuments: vi.fn(),
      deleteDocument: vi.fn(),
      triggerParse: vi.fn(),
      uploadDocument: vi.fn(),
      setFilters: vi.fn(),
    });
  });

  it("渲染文档列表与状态标签", () => {
    render(
      <MemoryRouter>
        <DocumentListPage />
      </MemoryRouter>,
    );
    expect(screen.getByText("论文A")).toBeInTheDocument();
    expect(screen.getByText("论文B")).toBeInTheDocument();
    expect(screen.getByText("已解析")).toBeInTheDocument();
    expect(screen.getByText("已上传")).toBeInTheDocument();
  });
});
