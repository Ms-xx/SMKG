import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import LatexFormula from "./LatexFormula";

describe("LatexFormula", () => {
  const originalClipboard = navigator.clipboard;

  beforeEach(() => {
    Object.defineProperty(navigator, "clipboard", {
      value: { writeText: vi.fn().mockResolvedValue(undefined) },
      configurable: true,
      writable: true,
    });
  });

  afterEach(() => {
    Object.defineProperty(navigator, "clipboard", {
      value: originalClipboard,
      configurable: true,
      writable: true,
    });
  });

  it("用 KaTeX 渲染 LaTeX 并剥离定界符", () => {
    const { container } = render(<LatexFormula latex="$$E=mc^{2}$$" display normalized />);
    expect(container.querySelector(".katex")).toBeTruthy();
    // 定界符不应作为文本泄漏到页面
    expect(container.textContent).not.toContain("$$");
  });

  it("行内与行间公式输出不同版式", () => {
    const { container, unmount } = render(<LatexFormula latex="a_i" display={false} normalized />);
    expect(screen.getByTestId("latex-formula").getAttribute("data-display")).toBe("false");
    expect(container.querySelector(".katex-display")).toBeNull();
    unmount();

    const display = render(<LatexFormula latex="a_i" display normalized />);
    expect(display.container.querySelector(".katex-display")).toBeTruthy();
    expect(display.container.querySelector(".latex-formula.is-display")).toBeTruthy();
  });

  it("渲染公式编号", () => {
    render(<LatexFormula latex="E=mc^{2}" display number="3" normalized />);
    expect(screen.getByText("(3)")).toBeInTheDocument();
  });

  it("复制内容为带统一定界符的 LaTeX", async () => {
    render(<LatexFormula latex="E=mc^{2}" display number={null} normalized />);
    fireEvent.click(screen.getByLabelText("复制 LaTeX 公式"));
    await waitFor(() => {
      expect(navigator.clipboard.writeText).toHaveBeenCalledWith("$$E=mc^{2}$$");
    });
  });

  it("行内公式复制为单定界符", async () => {
    render(<LatexFormula latex="a_i" display={false} normalized />);
    fireEvent.click(screen.getByLabelText("复制 LaTeX 公式"));
    await waitFor(() => {
      expect(navigator.clipboard.writeText).toHaveBeenCalledWith("$a_i$");
    });
  });

  it("无法渲染时降级为等宽原文，不白屏", () => {
    const { container } = render(<LatexFormula latex="\\frac{1}{" display normalized />);
    expect(container.querySelector(".katex")).toBeNull();
    expect(container.querySelector(".latex-formula-fallback")).toBeTruthy();
    expect(screen.getByTestId("latex-formula")).toBeInTheDocument();
  });

  it("后端标注未转 LaTeX 时同样降级展示", () => {
    const { container } = render(
      <LatexFormula latex="What school did burne hogarth establish?" normalized={false} />,
    );
    expect(container.querySelector(".katex")).toBeNull();
    expect(container.querySelector(".latex-formula-fallback")).toBeTruthy();
    expect(screen.getByText(/What school did burne hogarth establish\?/)).toBeInTheDocument();
  });

  it("空公式保持既有占位文案", () => {
    render(<LatexFormula latex="" normalized />);
    expect(screen.getByText("[无文本内容]")).toBeInTheDocument();
  });

  it("copyable=false 时不渲染复制按钮", () => {
    render(<LatexFormula latex="x=1" normalized copyable={false} />);
    expect(screen.queryByLabelText("复制 LaTeX 公式")).toBeNull();
  });
});
