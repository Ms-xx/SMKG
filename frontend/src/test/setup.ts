import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";

// 每个用例结束后显式卸载并清理 DOM。
// 不依赖 RTL 的 auto-cleanup（其生效条件受 globals/版本影响）：缺失清理会导致
// 前一个用例的渲染结果残留在 document 上，后续用例出现 "Found multiple elements ..." 误报。
afterEach(() => {
  cleanup();
});

// jsdom 不提供 matchMedia，antd 组件依赖，测试环境下需要 polyfill
if (typeof window !== "undefined") {
  Object.defineProperty(window, "matchMedia", {
    writable: true,
    value: (query: string) => ({
      matches: false,
      media: query,
      onchange: null,
      addListener: () => {},
      removeListener: () => {},
      addEventListener: () => {},
      removeEventListener: () => {},
      dispatchEvent: () => false,
    }),
  });

  // antd 的 message/notification 依赖 ResizeObserver
  class ResizeObserverMock {
    observe() {}
    unobserve() {}
    disconnect() {}
  }
  Object.defineProperty(window, "ResizeObserver", {
    writable: true,
    value: ResizeObserverMock,
  });

  // jsdom 不实现 scrollTo
  Object.defineProperty(window, "scrollTo", {
    writable: true,
    value: () => {},
  });
}
