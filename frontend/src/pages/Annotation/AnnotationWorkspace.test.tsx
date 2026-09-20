import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import { message } from "antd";
import AnnotationWorkspace from "./AnnotationWorkspace";
import { annotationApi, commentApi, userApi } from "@api/modules";

vi.mock("@api/modules", () => ({
  annotationApi: {
    getByDocument: vi.fn(),
    create: vi.fn(),
    submit: vi.fn(),
    update: vi.fn(),
    firstReview: vi.fn(),
    finalReview: vi.fn(),
    getVersions: vi.fn(),
  },
  commentApi: { create: vi.fn(), list: vi.fn(), remove: vi.fn() },
  userApi: { mentionable: vi.fn() },
}));

vi.mock("./components/DualPaneView", () => ({
  default: () => <div data-testid="dual-pane" />,
}));

const renderWorkspace = () =>
  render(
    <MemoryRouter initialEntries={["/d1"]}>
      <Routes>
        <Route path="/:documentId" element={<AnnotationWorkspace />} />
      </Routes>
    </MemoryRouter>,
  );

const makeAnnotation = (overrides: Record<string, any> = {}) =>
  ({
    id: "a1",
    document_id: "d1",
    element_id: null,
    annotation_type: "ner",
    content: { text: "钛酸钡", entity_type: "Material" },
    confidence: 0.9,
    status: "approved",
    annotated_by: "u1",
    created_at: "2026-01-01T00:00:00",
    updated_at: "2026-01-01T00:00:00",
    ...overrides,
  }) as any;

describe("AnnotationWorkspace", () => {
  beforeEach(() => {
    vi.mocked(annotationApi.getByDocument).mockReset().mockResolvedValue({ data: [] });
    vi.mocked(annotationApi.create)
      .mockReset()
      .mockResolvedValue({ data: { id: "real1" } });
    vi.mocked(annotationApi.submit).mockReset().mockResolvedValue({});
    vi.mocked(commentApi.list)
      .mockReset()
      .mockResolvedValue({ items: [], total: 0, page: 1, page_size: 20 });
    vi.mocked(userApi.mentionable).mockReset().mockResolvedValue([]);
  });

  afterEach(() => {
    message.destroy();
  });

  it("加载中显示 Spin", () => {
    vi.mocked(annotationApi.getByDocument).mockReturnValue(new Promise(() => {}));
    renderWorkspace();
    expect(document.querySelector(".ant-spin")).toBeTruthy();
    expect(screen.queryByText("保存")).toBeNull();
  });

  it("加载完成后渲染标题按钮与四个标签页", async () => {
    renderWorkspace();
    expect(await screen.findByText("保存")).toBeInTheDocument();
    expect(screen.getByText("提交审核")).toBeInTheDocument();
    expect(screen.getByText("实体标注")).toBeInTheDocument();
    expect(screen.getByText("关系标注")).toBeInTheDocument();
    expect(screen.getByText("评论讨论")).toBeInTheDocument();
    expect(screen.getByText("历史记录")).toBeInTheDocument();
    expect(screen.getByTestId("dual-pane")).toBeInTheDocument();
  });

  it("getByDocument 返回数组时也能正常渲染", async () => {
    vi.mocked(annotationApi.getByDocument).mockResolvedValue([makeAnnotation()]);
    renderWorkspace();
    expect(await screen.findByText("保存")).toBeInTheDocument();
  });

  it("getByDocument 失败时回退为空标注列表", async () => {
    vi.mocked(annotationApi.getByDocument).mockRejectedValue(new Error("404"));
    renderWorkspace();
    expect(await screen.findByText("保存")).toBeInTheDocument();
    expect(screen.queryByText(/不存在/)).toBeNull();
  });

  it("没有新标注时点击保存提示无需保存", async () => {
    vi.mocked(annotationApi.getByDocument).mockResolvedValue({ data: [makeAnnotation()] });
    renderWorkspace();
    fireEvent.click(await screen.findByText("保存"));
    expect(await screen.findByText("没有新的标注需要保存")).toBeInTheDocument();
  });

  it("保存临时标注并替换真实ID", async () => {
    vi.mocked(annotationApi.getByDocument).mockResolvedValue({
      data: [makeAnnotation({ id: "temp_1", status: "draft" })],
    });
    renderWorkspace();
    fireEvent.click(await screen.findByText("保存"));
    await waitFor(() =>
      expect(vi.mocked(annotationApi.create)).toHaveBeenCalledWith({
        document_id: "d1",
        element_id: null,
        annotation_type: "ner",
        content: { text: "钛酸钡", entity_type: "Material" },
        confidence: 0.9,
      }),
    );
    expect(await screen.findByText("已保存 1 条标注")).toBeInTheDocument();
  });

  it("存在未保存标注时提交提示先保存", async () => {
    vi.mocked(annotationApi.getByDocument).mockResolvedValue({
      data: [makeAnnotation({ id: "temp_1", status: "draft" })],
    });
    renderWorkspace();
    fireEvent.click(await screen.findByText("提交审核"));
    expect(await screen.findByText("请先保存新标注再提交")).toBeInTheDocument();
  });

  it("没有待提交标注时提示", async () => {
    vi.mocked(annotationApi.getByDocument).mockResolvedValue({ data: [makeAnnotation()] });
    renderWorkspace();
    fireEvent.click(await screen.findByText("提交审核"));
    expect(await screen.findByText("没有待提交的标注")).toBeInTheDocument();
  });
});
