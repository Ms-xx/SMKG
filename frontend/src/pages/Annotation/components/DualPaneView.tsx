import { Splitter } from "antd";
import PDFViewer from "@components/PDFViewer/PDFViewer";
import AnnotationPanel from "@components/Annotation/AnnotationPanel";

interface DualPaneViewProps {
  documentId: string;
  fileUrl: string;
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
        <PDFViewer
          fileUrl={fileUrl}
          onElementClick={(bbox) => {
            const el = elements.find((e: any) => {
              const [x0, y0, x1, y1] = e.bbox;
              return bbox[0] >= x0 && bbox[1] >= y0 && bbox[0] <= x1 && bbox[1] <= y1;
            });
            if (el) onElementSelect(el);
          }}
        />
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
