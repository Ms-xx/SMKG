import { describe, it, expect } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import NotFoundPage from "./NotFoundPage";

const renderWithRoutes = () =>
  render(
    <MemoryRouter initialEntries={["/bad-path"]}>
      <Routes>
        <Route path="*" element={<NotFoundPage />} />
        <Route path="/" element={<div>HOME</div>} />
      </Routes>
    </MemoryRouter>,
  );

describe("NotFoundPage", () => {
  it("渲染 404 提示与返回首页按钮", () => {
    renderWithRoutes();
    expect(screen.getByText("404")).toBeInTheDocument();
    expect(screen.getByText("抱歉，您访问的页面不存在")).toBeInTheDocument();
    expect(screen.getByText("返回首页")).toBeInTheDocument();
  });

  it("点击返回首页跳转到首页", () => {
    renderWithRoutes();
    fireEvent.click(screen.getByText("返回首页"));
    expect(screen.getByText("HOME")).toBeInTheDocument();
  });
});
