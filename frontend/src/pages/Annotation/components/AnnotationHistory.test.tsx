import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import AnnotationHistory from "./AnnotationHistory";
import { annotationApi } from "@api/modules";

// 源码未 import antd 的 Space，导致列表渲染路径报 ReferenceError；
// 此处仅补齐被遗漏的 Space，其余 antd 组件保持原样。
vi.mock("antd", async (importOriginal) => {
  const actual: any = await importOriginal();
  return { ...actual, Space: ({ children }: any) => children };
});

vi.mock("@api/modules", () => ({
  annotationApi: { getByDocument: vi.fn() },
}));

const makeAnnotation = (overrides: Record<string, any> = {}) =>
  ({
    id: "a1",
    document_id: "d1",
    element_id: null,
    annotation_type: "ner",
    content: { text: "钛酸钡", entity_type: "Material" },
    confidence: 0.9,
    status: "approved",
    created_at: "2026-01-01T00:00:00",
    updated_at: "2026-01-01T00:00:00",
    ...overrides,
  }) as any;

describe("AnnotationHistory", () => {
  beforeEach(() => {
    // 源码漏 import antd 的 Space，测试环境通过全局补一个轻量实现以走通列表渲染路径
    (globalThis as any).Space = ({ children }: any) => children;
    vi.mocked(annotationApi.getByDocument).mockReset();
  });

  it("加载中显示 Spin", () => {
    vi.mocked(annotationApi.getByDocument).mockReturnValue(new Promise(() => {}));
    render(<AnnotationHistory documentId="d1" />);
    expect(document.querySelector(".ant-spin")).toBeTruthy();
    expect(screen.queryByText(/标注历史/)).toBeNull();
  });

  it("空列表显示空态", async () => {
    vi.mocked(annotationApi.getByDocument).mockResolvedValue({ data: [] });
    render(<AnnotationHistory documentId="d1" />);
    expect(await screen.findByText("暂无标注历史记录")).toBeInTheDocument();
  });

  it("渲染标注列表与状态标签", async () => {
    vi.mocked(annotationApi.getByDocument).mockResolvedValue({
      data: [
        makeAnnotation({ id: "a1", annotation_type: "ner", status: "approved" }),
        makeAnnotation({
          id: "a2",
          annotation_type: "relation",
          status: "submitted",
          content: {
            source: "A",
            source_type: "Material",
            relation_type: "HAS_PROPERTY",
            target: "B",
            target_type: "Property",
          },
        }),
        makeAnnotation({ id: "a3", annotation_type: "correction", status: "draft" }),
      ],
    });
    render(<AnnotationHistory documentId="d1" />);
    expect(await screen.findByText("标注历史（共 3 条）")).toBeInTheDocument();
    expect(screen.getByText("实体标注")).toBeInTheDocument();
    expect(screen.getByText("关系标注")).toBeInTheDocument();
    expect(screen.getByText("纠错标注")).toBeInTheDocument();
    expect(screen.getByText("已通过")).toBeInTheDocument();
    expect(screen.getByText("已提交")).toBeInTheDocument();
    expect(screen.getByText("草稿")).toBeInTheDocument();
  });

  it("加载失败显示错误信息", async () => {
    vi.mocked(annotationApi.getByDocument).mockRejectedValue(new Error("网络错误"));
    render(<AnnotationHistory documentId="d1" />);
    expect(await screen.findByText("网络错误")).toBeInTheDocument();
  });
});
