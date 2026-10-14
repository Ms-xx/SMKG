import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import DualPaneView from "./DualPaneView";

let pdfProps: any = {};

vi.mock("@components/PDFViewer/PDFViewer", () => ({
  default: (props: any) => {
    pdfProps = props;
    return <div data-testid="pdf-viewer" />;
  },
}));
vi.mock("@components/Annotation/AnnotationPanel", () => ({
  default: () => <div data-testid="annotation-panel" />,
}));

describe("DualPaneView", () => {
  const elements = [
    { id: "e1", bbox: [0, 0, 100, 100] },
    { id: "e2", bbox: [100, 100, 200, 200] },
  ];

  it("渲染 PDF 视图与标注面板", () => {
    render(
      <DualPaneView
        documentId="d1"
        fileUrl="http://example.com/x.pdf"
        elements={elements}
        selectedElement={null}
        onElementSelect={vi.fn()}
        onAnnotationChange={vi.fn()}
      />,
    );
    expect(screen.getByTestId("pdf-viewer")).toBeInTheDocument();
    expect(screen.getByTestId("annotation-panel")).toBeInTheDocument();
  });

  it("将选中元素所在页作为文件页跳转目标透传给 PDF 视图", () => {
    const selected = { id: "e1", page: 3, bbox: [0, 0, 100, 100] };
    render(
      <DualPaneView
        documentId="d1"
        fileUrl="http://example.com/x.pdf"
        elements={elements}
        selectedElement={selected}
        onElementSelect={vi.fn()}
        onAnnotationChange={vi.fn()}
      />,
    );
    expect(pdfProps.targetPage).toBe(3);
  });

  it("无选中时不传跳页目标，且不请求内容高亮", () => {
    render(
      <DualPaneView
        documentId="d1"
        fileUrl="http://example.com/x.pdf"
        elements={elements}
        selectedElement={null}
        onElementSelect={vi.fn()}
        onAnnotationChange={vi.fn()}
      />,
    );
    expect(pdfProps.targetPage).toBeUndefined();
    expect("highlightEl" in pdfProps).toBe(false);
    expect("onElementClick" in pdfProps).toBe(false);
  });
});
