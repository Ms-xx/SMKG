import "@testing-library/jest-dom/vitest";

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
