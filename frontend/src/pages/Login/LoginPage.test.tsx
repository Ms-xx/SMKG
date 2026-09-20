import { describe, it, expect } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import LoginPage from "./LoginPage";

const renderPage = () =>
  render(
    <MemoryRouter>
      <LoginPage />
    </MemoryRouter>,
  );

describe("LoginPage", () => {
  it("渲染登录表单", () => {
    renderPage();
    expect(screen.getByText("科学文献智能解析平台")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /登\s*录/ })).toBeInTheDocument();
    expect(screen.getByText("没有账号？立即注册")).toBeInTheDocument();
    expect(screen.getByPlaceholderText("用户名")).toBeInTheDocument();
    expect(screen.getByPlaceholderText("密码")).toBeInTheDocument();
  });

  it("点击注册链接打开注册弹窗", async () => {
    renderPage();
    fireEvent.click(screen.getByText("没有账号？立即注册"));
    await waitFor(() => expect(screen.getByText("用户注册")).toBeInTheDocument());
    expect(screen.getByPlaceholderText("请输入邮箱")).toBeInTheDocument();
  });
});
