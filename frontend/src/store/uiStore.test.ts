import { describe, it, expect, beforeEach } from "vitest";
import { useUIStore } from "./uiStore";

describe("useUIStore", () => {
  beforeEach(() => {
    useUIStore.setState({ sidebarCollapsed: false, theme: "light" });
  });

  it("初始状态 sidebarCollapsed=false, theme=light", () => {
    const state = useUIStore.getState();
    expect(state.sidebarCollapsed).toBe(false);
    expect(state.theme).toBe("light");
  });

  it("toggleSidebar 切换折叠状态", () => {
    useUIStore.getState().toggleSidebar();
    expect(useUIStore.getState().sidebarCollapsed).toBe(true);

    useUIStore.getState().toggleSidebar();
    expect(useUIStore.getState().sidebarCollapsed).toBe(false);
  });

  it("setTheme 设置主题", () => {
    useUIStore.getState().setTheme("dark");
    expect(useUIStore.getState().theme).toBe("dark");
  });
});
