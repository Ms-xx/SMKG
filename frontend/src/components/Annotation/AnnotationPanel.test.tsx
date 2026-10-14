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

  it("快速连续点击不同解析元素都触发回调（无状态残留）", () => {
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
    fireEvent.click(screen.getByText("表格"));
    fireEvent.click(screen.getByText("正文"));
    expect(onElementSelect).toHaveBeenCalledTimes(3);
    expect(onElementSelect.mock.calls[0][0]).toBe(elements[0]);
    expect(onElementSelect.mock.calls[1][0]).toBe(elements[1]);
    expect(onElementSelect.mock.calls[2][0]).toBe(elements[3]);
  });

  it("高亮当前选中元素（背景变色）", () => {
    const { container } = render(
      <AnnotationPanel
        elements={elements}
        selectedElement={elements[1]}
        onElementSelect={vi.fn()}
        onAnnotationChange={vi.fn()}
      />,
    );
    const items = container.querySelectorAll<HTMLElement>(".ant-list-item");
    expect(items[1].style.background).toBe("rgb(230, 247, 255)");
    expect(items[0].style.background).toBe("transparent");
  });
});
