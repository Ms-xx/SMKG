import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import LandingPage from "./LandingPage";

const navigateMock = vi.fn();

vi.mock("react-router-dom", async () => {
  const actual = await vi.importActual<typeof import("react-router-dom")>("react-router-dom");
  return { ...actual, useNavigate: () => navigateMock };
});

vi.mock("@store/authStore", () => ({
  useAuthStore: (selector: (s: { isAuthenticated: boolean }) => boolean) =>
    selector({ isAuthenticated: false }),
}));

const renderPage = () =>
  render(
    <MemoryRouter>
      <LandingPage />
    </MemoryRouter>,
  );

describe("LandingPage", () => {
  it("渲染项目标题与说明", () => {
    renderPage();
    // 标题文案在页脚也会出现，这里按 h1 角色定位以消除歧义
    const heading = screen.getByRole("heading", { level: 1 });
    expect(heading.textContent).toContain("多模态科学文献智能解析");
    expect(heading.textContent).toContain("与知识图谱构建平台");
    expect(screen.getByText(/结构化知识/)).toBeInTheDocument();
  });

  it("展示五大核心能力与六大模块", () => {
    renderPage();
    expect(screen.getByText("五大核心能力")).toBeInTheDocument();
    expect(screen.getByText("功能模块概览")).toBeInTheDocument();
    expect(screen.getByText("模块一 · PDF 管理与细粒度解析")).toBeInTheDocument();
    expect(screen.getByText("模块六 · 写作辅助与可视化")).toBeInTheDocument();
  });

  it("展示适用场景与技术栈", () => {
    renderPage();
    expect(screen.getByText("适用场景")).toBeInTheDocument();
    expect(screen.getByText("技术栈")).toBeInTheDocument();
    expect(screen.getByText("GraphRAGTest(:8001)")).toBeInTheDocument();
  });

  it("点击主视觉按钮跳转登录页", () => {
    navigateMock.mockClear();
    renderPage();
    fireEvent.click(screen.getByTestId("hero-login"));
    expect(navigateMock).toHaveBeenCalledWith("/login");
  });

  it("底部引导按钮跳转登录页", () => {
    navigateMock.mockClear();
    renderPage();
    fireEvent.click(screen.getByTestId("footer-login"));
    expect(navigateMock).toHaveBeenCalledWith("/login");
  });

  it("未登录时次级按钮为「了解功能亮点」", () => {
    renderPage();
    expect(screen.getByTestId("hero-secondary")).toBeInTheDocument();
    expect(screen.getByText("了解功能亮点")).toBeInTheDocument();
  });
});
