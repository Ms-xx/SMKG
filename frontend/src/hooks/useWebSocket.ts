import { useEffect, useRef, useState, useCallback } from "react";

const CONNECTING = 0;
const OPEN = 1;

export function useWebSocket({
  url,
  onMessage,
  reconnectInterval = 5000,
  autoReconnect = true,
}: {
  url: string;
  onMessage?: (data: any) => void;
  reconnectInterval?: number;
  autoReconnect?: boolean;
}) {
  const wsRef = useRef<WebSocket | null>(null);
  const [isConnected, setIsConnected] = useState(false);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout>>();

  // 回调放进 ref：否则 onMessage 每次变化都会改变 connect 的身份，
  // 触发下面的 effect 重跑，把刚建好的连接拆掉重建
  // （表现为连接反复创建、服务端不断收到 presence.joined/left 抖动）。
  const onMessageRef = useRef(onMessage);
  useEffect(() => {
    onMessageRef.current = onMessage;
  }, [onMessage]);

  // 主动断开或组件卸载后不应再自动重连
  const shouldReconnectRef = useRef(true);

  const clearReconnectTimer = useCallback(() => {
    if (reconnectTimerRef.current) {
      clearTimeout(reconnectTimerRef.current);
      reconnectTimerRef.current = undefined;
    }
  }, []);

  const connect = useCallback(() => {
    if (!url) return;
    clearReconnectTimer();
    const ws = new WebSocket(url);
    wsRef.current = ws;

    ws.onopen = () => {
      setIsConnected(true);
      clearReconnectTimer();
    };
    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      onMessageRef.current?.(data);
    };
    ws.onclose = () => {
      setIsConnected(false);
      // 仅在"非主动关闭"时才重连，否则卸载/主动断开后会被无限重连
      if (autoReconnect && shouldReconnectRef.current) {
        reconnectTimerRef.current = setTimeout(connect, reconnectInterval);
      }
    };
    ws.onerror = () => ws.close();
  }, [url, reconnectInterval, autoReconnect, clearReconnectTimer]);

  /**
   * 关闭连接。
   * 处于 CONNECTING 时直接 close() 会触发浏览器告警
   * "WebSocket is closed before the connection is established"
   * （StrictMode 下 effect 双挂载必然走到这里），因此等握手完成后再关闭。
   */
  const teardown = useCallback((ws: WebSocket | null) => {
    if (!ws) return;
    ws.onmessage = null;
    ws.onclose = null;
    ws.onerror = null;
    if (ws.readyState === CONNECTING) {
      ws.onopen = () => ws.close();
    } else {
      ws.onopen = null;
      if (ws.readyState === OPEN) ws.close();
    }
  }, []);

  const sendMessage = useCallback((data: any) => {
    if (wsRef.current?.readyState === OPEN) {
      wsRef.current.send(JSON.stringify(data));
    }
  }, []);

  const disconnect = useCallback(() => {
    shouldReconnectRef.current = false;
    clearReconnectTimer();
    const ws = wsRef.current;
    wsRef.current = null;
    teardown(ws);
    setIsConnected(false);
  }, [clearReconnectTimer, teardown]);

  useEffect(() => {
    if (!url) return;
    shouldReconnectRef.current = true;
    connect();
    return () => {
      shouldReconnectRef.current = false;
      clearReconnectTimer();
      const ws = wsRef.current;
      wsRef.current = null;
      teardown(ws);
      setIsConnected(false);
    };
  }, [connect, disconnect, url, clearReconnectTimer, teardown]);

  return { isConnected, sendMessage, disconnect };
}
