import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useWebSocket } from "./useWebSocket";

// jsdom 不提供完整 WebSocket，用可控的 mock 替换
class MockWebSocket {
  static OPEN = 1;
  static instances: MockWebSocket[] = [];

  url: string;
  readyState: number = 0;
  sent: string[] = [];
  onopen: (() => void) | null = null;
  onmessage: ((event: any) => void) | null = null;
  onclose: (() => void) | null = null;
  onerror: (() => void) | null = null;

  constructor(url: string) {
    this.url = url;
    MockWebSocket.instances.push(this);
  }

  send(data: string) {
    this.sent.push(data);
  }

  close() {
    this.readyState = 3;
    this.onclose?.();
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
});
