import { useState, useEffect } from "react";
import { Document, Page, pdfjs } from "react-pdf";
import { Spin, Button, Space } from "antd";
import { ZoomInOutlined, ZoomOutOutlined } from "@ant-design/icons";
import "react-pdf/dist/esm/Page/AnnotationLayer.css";
import "react-pdf/dist/esm/Page/TextLayer.css";

pdfjs.GlobalWorkerOptions.workerSrc = `//unpkg.com/pdfjs-dist@${pdfjs.version}/build/pdf.worker.min.js`;

interface PDFViewerProps {
  fileUrl: string | Blob;
  onPageChange?: (page: number) => void;
  // 文件页之间跳转的目标页（如右侧选中解析元素所在页）。仅用于页面切换定位，不做任何内容高亮。
  targetPage?: number;
}

export default function PDFViewer({ fileUrl, onPageChange, targetPage }: PDFViewerProps) {
  const [numPages, setNumPages] = useState<number | null>(null);
  const [pageNumber, setPageNumber] = useState(1);
  const [scale, setScale] = useState(1.5);

  const onDocumentLoadSuccess = ({ numPages: n }: { numPages: number }) => setNumPages(n);

  // 文件页之间跳转：targetPage 变化时自动切换到对应页（仅跳页，不绘制高亮）
  useEffect(() => {
    if (typeof targetPage === "number" && targetPage >= 1 && targetPage !== pageNumber) {
      setPageNumber(targetPage);
    }
  }, [targetPage, pageNumber]);

  const handlePageLoad = () => {
    onPageChange?.(pageNumber);
  };

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
          onItemClick={({ pageNumber: p }) => {
            if (typeof p === "number" && p >= 1) setPageNumber(p);
          }}
          loading={<Spin size="large" />}
        >
          <div className="pdf-page-wrap" style={{ position: "relative", display: "inline-block" }}>
            <Page pageNumber={pageNumber} scale={scale} onLoadSuccess={handlePageLoad} />
          </div>
        </Document>
      </div>
    </div>
  );
}
