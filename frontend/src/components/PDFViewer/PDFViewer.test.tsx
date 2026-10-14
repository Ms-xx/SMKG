import { describe, it, expect, vi } from "vitest";
import { useEffect } from "react";
import { render, screen, fireEvent } from "@testing-library/react";
import PDFViewer from "./PDFViewer";

// 使用轻量 mock 渲染 react-pdf，聚焦「文件页之间跳转」行为，不涉及文本/代码/内容高亮
vi.mock("react-pdf", () => {
  const Document = ({ onLoadSuccess, children }: any) => {
    useEffect(() => {
      onLoadSuccess?.({ numPages: 3 });
    }, [onLoadSuccess]);
    return <div>{children}</div>;
  };
  const Page = ({ pageNumber, onLoadSuccess }: any) => {
    useEffect(() => {
      onLoadSuccess?.();
    }, []);
    return <div data-testid="pdf-current-page">{pageNumber}</div>;
  };
  return {
    Document,
    Page,
    pdfjs: { version: "0.0.0", GlobalWorkerOptions: {} },
  };
});

describe("PDFViewer（文件页跳转，无内容高亮）", () => {
  it("渲染工具栏、上一页/下一页按钮与当前页", () => {
    render(<PDFViewer fileUrl="http://example.com/x.pdf" />);
    expect(screen.getByText("上一页")).toBeInTheDocument();
    expect(screen.getByText("下一页")).toBeInTheDocument();
    // Document onLoadSuccess 置 numPages=3，当前页初始为 1
    expect(screen.getByText("1 / 3")).toBeInTheDocument();
  });

  it("下一页切换页码，上一页在第一页时禁用", () => {
    render(<PDFViewer fileUrl="http://example.com/x.pdf" />);
    const prev = screen.getByRole("button", { name: "上一页" });
    expect(prev).toBeDisabled();
    fireEvent.click(screen.getByRole("button", { name: "下一页" }));
    expect(screen.getByTestId("pdf-current-page").textContent).toBe("2");
    expect(prev).not.toBeDisabled();
  });

  it("targetPage 变化时自动跳转到对应页（文件页之间跳转）", () => {
    const { rerender } = render(<PDFViewer fileUrl="http://example.com/x.pdf" />);
    rerender(<PDFViewer fileUrl="http://example.com/x.pdf" targetPage={3} />);
    expect(screen.getByTestId("pdf-current-page").textContent).toBe("3");
  });

  it("targetPage 非法或与当前页相同时不跳转", () => {
    const { rerender } = render(<PDFViewer fileUrl="http://example.com/x.pdf" targetPage={0} />);
    expect(screen.getByTestId("pdf-current-page").textContent).toBe("1");
    rerender(<PDFViewer fileUrl="http://example.com/x.pdf" targetPage={1} />);
    expect(screen.getByTestId("pdf-current-page").textContent).toBe("1");
  });

  it("页面加载完成后回调 onPageChange 同步当前页", () => {
    const onPageChange = vi.fn();
    render(<PDFViewer fileUrl="http://example.com/x.pdf" onPageChange={onPageChange} />);
    expect(onPageChange).toHaveBeenCalledWith(1);
  });

  it("不再渲染任何内容高亮矩形/标记", () => {
    const { container } = render(<PDFViewer fileUrl="http://example.com/x.pdf" targetPage={1} />);
    expect(container.querySelector("[data-annotation-highlight]")).toBeNull();
  });
});
