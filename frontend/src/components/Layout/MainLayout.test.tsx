import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import MainLayout from "./MainLayout";

vi.mock("./Header", () => ({ default: () => <div>HeaderMock</div> }));
vi.mock("./Sidebar", () => ({ default: () => <div>SidebarMock</div> }));
vi.mock("react-router-dom", () => ({ Outlet: () => <div>OutletMock</div> }));

describe("MainLayout", () => {
  it("渲染侧边栏、头部和内容区", () => {
    render(<MainLayout />);
    expect(screen.getByText("HeaderMock")).toBeInTheDocument();
    expect(screen.getByText("SidebarMock")).toBeInTheDocument();
    expect(screen.getByText("OutletMock")).toBeInTheDocument();
  });
});
