import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import RelationEditor from "./RelationEditor";

const nerAnnotation = (id: string, text: string, entity_type: string) =>
  ({
    id,
    document_id: "d1",
    element_id: null,
    annotation_type: "ner",
    content: { text, entity_type },
    confidence: 0.9,
    status: "draft",
    created_at: "2026-01-01T00:00:00",
    updated_at: "2026-01-01T00:00:00",
  }) as any;

const relationAnnotation = (overrides: Record<string, any> = {}) =>
  ({
    id: "r1",
    document_id: "d1",
    element_id: null,
    annotation_type: "relation",
    content: {
      source: "钙钛矿",
      source_type: "Material",
      relation_type: "HAS_PROPERTY",
      target: "高效率",
      target_type: "Property",
      context: "钙钛矿具有高效率",
    },
    confidence: 0.7,
    status: "draft",
    created_at: "2026-01-01T00:00:00",
    updated_at: "2026-01-01T00:00:00",
    ...overrides,
  }) as any;

describe("RelationEditor", () => {
  it("空列表显示空态且添加按钮禁用", () => {
    render(<RelationEditor annotations={[]} onChange={vi.fn()} />);
    expect(
      screen.getByText("暂无关系标注，请先在实体标注Tab中添加实体后创建关系"),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /添加/ })).toBeDisabled();
  });

  it("渲染关系列表", () => {
    render(
      <RelationEditor
        annotations={[
          nerAnnotation("n1", "钙钛矿", "Material"),
          nerAnnotation("n2", "高效率", "Property"),
          relationAnnotation(),
        ]}
        onChange={vi.fn()}
      />,
    );
    expect(screen.getByText("具有性能")).toBeInTheDocument();
    expect(screen.getByText("钙钛矿具有高效率")).toBeInTheDocument();
    expect(screen.getAllByText("钙钛矿").length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText("高效率")).toBeInTheDocument();
    expect(screen.getByText("70%")).toBeInTheDocument();
  });

  it("点击关系类型筛选标签进行过滤", () => {
    render(
      <RelationEditor
        annotations={[
          nerAnnotation("n1", "钙钛矿", "Material"),
          nerAnnotation("n2", "高效率", "Property"),
          nerAnnotation("n3", "稳定性", "Property"),
          relationAnnotation(),
          relationAnnotation({
            id: "r2",
            content: {
              source: "钙钛矿",
              source_type: "Material",
              relation_type: "IMPROVES",
              target: "稳定性",
              target_type: "Property",
              context: "钙钛矿改善稳定性",
            },
          }),
        ]}
        onChange={vi.fn()}
      />,
    );
    expect(screen.getByText("改善")).toBeInTheDocument();
    fireEvent.click(screen.getByText("具有性能 (1)"));
    expect(screen.queryByText("改善")).toBeNull();
    expect(screen.getByText("钙钛矿具有高效率")).toBeInTheDocument();
  });

  it("未选择源/关系/目标时添加按钮保持禁用", () => {
    render(
      <RelationEditor
        annotations={[
          nerAnnotation("n1", "钙钛矿", "Material"),
          nerAnnotation("n2", "高效率", "Property"),
        ]}
        onChange={vi.fn()}
      />,
    );
    expect(screen.getByRole("button", { name: /添加/ })).toBeDisabled();
  });
});
