import { useState } from "react";
import { Document, Page, pdfjs } from "react-pdf";
import { Spin, Button, Space } from "antd";
import { ZoomInOutlined, ZoomOutOutlined } from "@ant-design/icons";
import "react-pdf/dist/esm/Page/AnnotationLayer.css";
import "react-pdf/dist/esm/Page/TextLayer.css";

pdfjs.GlobalWorkerOptions.workerSrc = `//unpkg.com/pdfjs-dist@${pdfjs.version}/build/pdf.worker.min.js`;

interface PDFViewerProps {
  fileUrl: string;
  onPageChange?: (page: number) => void;
  onElementClick?: (bbox: number[]) => void;
}

export default function PDFViewer({ fileUrl, onPageChange }: PDFViewerProps) {
  const [numPages, setNumPages] = useState<number | null>(null);
  const [pageNumber, setPageNumber] = useState(1);
  const [scale, setScale] = useState(1.5);

  const onDocumentLoadSuccess = ({ numPages }: { numPages: number }) => setNumPages(numPages);

  return (
    <div className="pdf-viewer">
      <div className="pdf-toolbar">
        <Space>
          <Button
            onClick={() => setPageNumber((p) => Math.max(p - 1, 1))}
            disabled={pageNumber <= 1}
          >
            上一页
          </Button>
          <span>
            {pageNumber} / {numPages || "?"}
          </span>
          <Button
            onClick={() => setPageNumber((p) => Math.min(p + 1, numPages || 1))}
            disabled={pageNumber >= (numPages || 1)}
          >
            下一页
          </Button>
          <Button
            icon={<ZoomOutOutlined />}
            onClick={() => setScale((s) => Math.max(s - 0.1, 0.5))}
          />
          <Button icon={<ZoomInOutlined />} onClick={() => setScale((s) => Math.min(s + 0.1, 3))} />
        </Space>
      </div>
      <div className="pdf-content" style={{ overflow: "auto", height: "calc(100vh - 200px)" }}>
        <Document
          file={fileUrl}
          onLoadSuccess={onDocumentLoadSuccess}
          loading={<Spin size="large" />}
        >
          <Page
            pageNumber={pageNumber}
            scale={scale}
            onLoadSuccess={() => onPageChange?.(pageNumber)}
          />
        </Document>
      </div>
    </div>
  );
}
