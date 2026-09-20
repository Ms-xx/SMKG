import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import AnnotationPanel from "./AnnotationPanel";

describe("AnnotationPanel", () => {
  const elements = [
    { id: "e1", element_type: "heading", content: "标题一" },
    { id: "e2", element_type: "table", content: "表格" },
    { id: "e3", element_type: "formula", content: "" },
    { id: "e4", element_type: "paragraph", content: "正文" },
  ];

  it("渲染元素列表并展示类型标签", () => {
    render(
      <AnnotationPanel
        elements={elements}
        selectedElement={null}
        onElementSelect={vi.fn()}
        onAnnotationChange={vi.fn()}
      />,
    );
    expect(screen.getByText("解析元素")).toBeInTheDocument();
    expect(screen.getByText("标题一")).toBeInTheDocument();
    expect(screen.getByText("[无文本内容]")).toBeInTheDocument();
    for (const t of ["heading", "table", "formula", "paragraph"]) {
      expect(screen.getByText(t)).toBeInTheDocument();
    }
  });

  it("点击元素触发回调", () => {
    const onElementSelect = vi.fn();
    render(
      <AnnotationPanel
        elements={elements}
        selectedElement={null}
        onElementSelect={onElementSelect}
        onAnnotationChange={vi.fn()}
      />,
    );
    fireEvent.click(screen.getByText("标题一"));
    expect(onElementSelect).toHaveBeenCalledWith(elements[0]);
  });
});
