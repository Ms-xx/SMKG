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

  it("点击页面区域命中元素时回调", () => {
    const onElementSelect = vi.fn();
    render(
      <DualPaneView
        documentId="d1"
        fileUrl="http://example.com/x.pdf"
        elements={elements}
        selectedElement={null}
        onElementSelect={onElementSelect}
        onAnnotationChange={vi.fn()}
      />,
    );
    pdfProps.onElementClick([50, 50]);
    expect(onElementSelect).toHaveBeenCalledWith(elements[0]);
  });

  it("点击空白区域不回调", () => {
    const onElementSelect = vi.fn();
    render(
      <DualPaneView
        documentId="d1"
        fileUrl="http://example.com/x.pdf"
        elements={elements}
        selectedElement={null}
        onElementSelect={onElementSelect}
        onAnnotationChange={vi.fn()}
      />,
    );
    pdfProps.onElementClick([999, 999]);
    expect(onElementSelect).not.toHaveBeenCalled();
  });
});
