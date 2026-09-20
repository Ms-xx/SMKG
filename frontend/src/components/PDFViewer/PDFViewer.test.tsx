import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent, act } from "@testing-library/react";
import PDFViewer from "./PDFViewer";

let docProps: any = {};
let pageProps: any = {};

vi.mock("react-pdf", () => ({
  Document: (props: any) => {
    docProps = props;
    return <div data-testid="pdf-document">{props.children}</div>;
  },
  Page: (props: any) => {
    pageProps = props;
    return <div data-testid="pdf-page">page {props.pageNumber}</div>;
  },
  pdfjs: { version: "3.11.174", GlobalWorkerOptions: {} },
}));

describe("PDFViewer", () => {
  it("渲染工具栏和初始页码", () => {
    const onPageChange = vi.fn();
    render(<PDFViewer fileUrl="http://example.com/x.pdf" onPageChange={onPageChange} />);
    expect(screen.getByText("1 / ?")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "上一页" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "下一页" })).toBeDisabled();
  });

  it("加载成功后更新页数并可翻页", () => {
    const onPageChange = vi.fn();
    render(<PDFViewer fileUrl="http://example.com/x.pdf" onPageChange={onPageChange} />);
    act(() => docProps.onLoadSuccess({ numPages: 5 }));
    expect(screen.getByText("1 / 5")).toBeInTheDocument();

    fireEvent.click(screen.getByText("下一页"));
    expect(screen.getByText("2 / 5")).toBeInTheDocument();

    act(() => pageProps.onLoadSuccess());
    expect(onPageChange).toHaveBeenCalledWith(2);

    fireEvent.click(screen.getByText("上一页"));
    expect(screen.getByText("1 / 5")).toBeInTheDocument();
  });
});
