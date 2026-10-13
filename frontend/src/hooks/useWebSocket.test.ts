import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useWebSocket } from "./useWebSocket";

// jsdom 不提供完整 WebSocket，用可控的 mock 替换
class MockWebSocket {
  static CONNECTING = 0;
  static OPEN = 1;
  static CLOSED = 3;
  static instances: MockWebSocket[] = [];

  url: string;
  readyState: number = 0;
  sent: string[] = [];
  onopen: (() => void) | null = null;
  onmessage: ((event: any) => void) | null = null;
  onclose: (() => void) | null = null;
  onerror: (() => void) | null = null;
  closeCalls = 0;

  constructor(url: string) {
    this.url = url;
    MockWebSocket.instances.push(this);
  }

  send(data: string) {
    this.sent.push(data);
  }

  close() {
    this.closeCalls += 1;
    this.readyState = 3;
    this.onclose?.();
  }

  /** 模拟握手完成 */
  simulateOpen() {
    this.readyState = 1;
    this.onopen?.();
  }
}

describe("useWebSocket", () => {
  beforeEach(() => {
    MockWebSocket.instances = [];
    vi.stubGlobal("WebSocket", MockWebSocket);
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });

  it("连接建立后 isConnected 为 true", () => {
    const { result } = renderHook(() => useWebSocket({ url: "ws://test" }));

    expect(MockWebSocket.instances).toHaveLength(1);
    const ws = MockWebSocket.instances[0];
    expect(ws.url).toBe("ws://test");

    act(() => {
      ws.readyState = 1;
      ws.onopen?.();
    });
    expect(result.current.isConnected).toBe(true);
  });

  it("收到消息时解析 JSON 并回调 onMessage", () => {
    const onMessage = vi.fn();
    renderHook(() => useWebSocket({ url: "ws://test", onMessage }));

    const ws = MockWebSocket.instances[0];
    act(() => {
      ws.onmessage?.({ data: JSON.stringify({ type: "progress", value: 42 }) });
    });
    expect(onMessage).toHaveBeenCalledWith({ type: "progress", value: 42 });
  });

  it("sendMessage 在 OPEN 状态发送消息", () => {
    const { result } = renderHook(() => useWebSocket({ url: "ws://test" }));
    const ws = MockWebSocket.instances[0];
    act(() => {
      ws.readyState = 1;
    });

    act(() => {
      result.current.sendMessage({ hello: "world" });
    });
    expect(ws.sent).toEqual([JSON.stringify({ hello: "world" })]);
  });

  it("非 OPEN 状态不发送消息", () => {
    const { result } = renderHook(() => useWebSocket({ url: "ws://test" }));

    act(() => {
      result.current.sendMessage({ hello: "world" });
    });
    expect(MockWebSocket.instances[0].sent).toEqual([]);
  });

  it("disconnect 关闭连接并标记未连接", () => {
    const { result } = renderHook(() => useWebSocket({ url: "ws://test" }));

    act(() => {
      result.current.disconnect();
    });
    expect(result.current.isConnected).toBe(false);
  });

  it("onMessage 变化不会重建连接", () => {
    const first = vi.fn();
    const { rerender } = renderHook(
      ({ cb }: { cb: (d: any) => void }) => useWebSocket({ url: "ws://test", onMessage: cb }),
      { initialProps: { cb: first } },
    );
    expect(MockWebSocket.instances).toHaveLength(1);

    // 传入新的回调（模拟父组件因数据加载导致 handleWsMessage 身份变化）
    const second = vi.fn();
    rerender({ cb: second });

    // 连接不应被拆掉重建
    expect(MockWebSocket.instances).toHaveLength(1);

    // 且调用的是最新回调
    act(() => {
      MockWebSocket.instances[0].onmessage?.({ data: JSON.stringify({ n: 1 }) });
    });
    expect(second).toHaveBeenCalledWith({ n: 1 });
    expect(first).not.toHaveBeenCalled();
  });

  it("主动 disconnect 后不再自动重连", () => {
    const { result } = renderHook(() => useWebSocket({ url: "ws://test" }));
    const ws = MockWebSocket.instances[0];
    act(() => {
      ws.simulateOpen();
    });

    act(() => {
      result.current.disconnect();
    });

    // 关闭触发的 onclose 不应再排重连定时器
    act(() => {
      vi.advanceTimersByTime(20000);
    });
    expect(MockWebSocket.instances).toHaveLength(1);
  });

  it("卸载后不再重连（修复前会在卸载后无限重连）", () => {
    const { unmount } = renderHook(() => useWebSocket({ url: "ws://test" }));
    const ws = MockWebSocket.instances[0];
    act(() => {
      ws.simulateOpen();
    });

    unmount();
    act(() => {
      vi.advanceTimersByTime(30000);
    });
    expect(MockWebSocket.instances).toHaveLength(1);
  });

  it("握手未完成时不立即 close（避免 closed before established 告警）", () => {
    const { unmount } = renderHook(() => useWebSocket({ url: "ws://test" }));
    const ws = MockWebSocket.instances[0];
    expect(ws.readyState).toBe(MockWebSocket.CONNECTING);

    unmount();
    // 仍处于 CONNECTING，不应调用 close()，而是等 open 后再关
    expect(ws.closeCalls).toBe(0);
    act(() => {
      ws.simulateOpen();
    });
    expect(ws.closeCalls).toBe(1);
  });

  it("异常关闭时会自动重连", () => {
    renderHook(() => useWebSocket({ url: "ws://test", reconnectInterval: 1000 }));
    const ws = MockWebSocket.instances[0];
    act(() => {
      ws.simulateOpen();
    });

    // 模拟服务端断开（非主动关闭）
    act(() => {
      ws.close();
    });
    act(() => {
      vi.advanceTimersByTime(1000);
    });
    expect(MockWebSocket.instances).toHaveLength(2);
  });
});
