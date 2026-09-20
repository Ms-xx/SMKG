import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import EntityExtractor from "./EntityExtractor";

const nerAnnotation = (overrides: Record<string, any> = {}) =>
  ({
    id: "n1",
    document_id: "d1",
    element_id: null,
    annotation_type: "ner",
    content: { text: "钛酸钡", entity_type: "Material" },
    confidence: 0.9,
    status: "draft",
    created_at: "2026-01-01T00:00:00",
    updated_at: "2026-01-01T00:00:00",
    ...overrides,
  }) as any;

describe("EntityExtractor", () => {
  it("空列表显示空态与筛选标签", () => {
    render(<EntityExtractor annotations={[]} onChange={vi.fn()} documentId="d1" />);
    expect(screen.getByText("暂无实体标注，请在上方添加")).toBeInTheDocument();
    expect(screen.getByText("全部 (0)")).toBeInTheDocument();
    expect(screen.getByText("材料类 (0)")).toBeInTheDocument();
  });

  it("渲染实体列表字段", () => {
    render(
      <EntityExtractor
        annotations={[
          nerAnnotation({
            id: "n1",
            content: { text: "钛酸钡", entity_type: "Material" },
            confidence: 0.9,
            status: "draft",
          }),
          nerAnnotation({
            id: "n2",
            content: { text: "导电性", entity_type: "Property" },
            confidence: 0.8,
            status: "approved",
          }),
        ]}
        onChange={vi.fn()}
        documentId="d1"
      />,
    );
    expect(screen.getByText("钛酸钡")).toBeInTheDocument();
    expect(screen.getByText("导电性")).toBeInTheDocument();
    expect(screen.getByText("材料类")).toBeInTheDocument();
    expect(screen.getByText("性能类")).toBeInTheDocument();
    expect(screen.getByText("90%")).toBeInTheDocument();
    expect(screen.getByText("80%")).toBeInTheDocument();
    expect(screen.getByText("草稿")).toBeInTheDocument();
    expect(screen.getByText("通过")).toBeInTheDocument();
  });

  it("点击类型筛选标签进行过滤", () => {
    render(
      <EntityExtractor
        annotations={[
          nerAnnotation({ id: "n1", content: { text: "钛酸钡", entity_type: "Material" } }),
          nerAnnotation({ id: "n2", content: { text: "导电性", entity_type: "Property" } }),
        ]}
        onChange={vi.fn()}
        documentId="d1"
      />,
    );
    fireEvent.click(screen.getByText("材料类 (1)"));
    expect(screen.queryByText("导电性")).toBeNull();
    expect(screen.getByText("钛酸钡")).toBeInTheDocument();
  });

  it("未选择类型时点击添加不回调", () => {
    const onChange = vi.fn();
    render(<EntityExtractor annotations={[]} onChange={onChange} documentId="d1" />);
    fireEvent.change(screen.getByPlaceholderText("实体文本"), { target: { value: "氧化铝" } });
    fireEvent.click(screen.getByText("添加"));
    expect(onChange).not.toHaveBeenCalled();
  });

  it("添加新实体回调携带新标注", async () => {
    const onChange = vi.fn();
    render(<EntityExtractor annotations={[]} onChange={onChange} documentId="d1" />);
    fireEvent.change(screen.getByPlaceholderText("实体文本"), { target: { value: "氧化铝" } });
    fireEvent.mouseDown(screen.getByRole("combobox"));
    fireEvent.click(await screen.findByText("材料类"));
    fireEvent.click(screen.getByText("添加"));
    await waitFor(() => expect(onChange).toHaveBeenCalledTimes(1));
    const added = onChange.mock.calls[0][0];
    expect(added).toHaveLength(1);
    expect(added[0].content.text).toBe("氧化铝");
    expect(added[0].content.entity_type).toBe("Material");
  });
});
