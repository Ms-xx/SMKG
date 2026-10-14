import { Splitter } from "antd";
import PDFViewer from "@components/PDFViewer/PDFViewer";
import AnnotationPanel from "@components/Annotation/AnnotationPanel";

interface DualPaneViewProps {
  documentId: string;
  fileUrl: string | Blob;
  elements: any[];
  selectedElement: any | null;
  onElementSelect: (element: any) => void;
  onAnnotationChange: (annotation: any) => void;
}

export default function DualPaneView({
  fileUrl,
  elements,
  selectedElement,
  onElementSelect,
  onAnnotationChange,
}: DualPaneViewProps) {
  return (
    <Splitter style={{ height: "calc(100vh - 120px)" }}>
      <Splitter.Panel collapsible>
        {/* 仅把选中元素所在页作为文件页跳转目标传给 PDF 视图（不触发任何内容高亮） */}
        <PDFViewer fileUrl={fileUrl} targetPage={selectedElement?.page} />
      </Splitter.Panel>
      <Splitter.Panel>
        <AnnotationPanel
          elements={elements}
          selectedElement={selectedElement}
          onElementSelect={onElementSelect}
          onAnnotationChange={onAnnotationChange}
        />
      </Splitter.Panel>
    </Splitter>
  );
}
