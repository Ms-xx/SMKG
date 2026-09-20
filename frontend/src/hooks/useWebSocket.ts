import { useEffect, useRef, useState, useCallback } from "react";

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

  const connect = useCallback(() => {
    const ws = new WebSocket(url);
    wsRef.current = ws;
    ws.onopen = () => {
      setIsConnected(true);
      if (reconnectTimerRef.current) clearTimeout(reconnectTimerRef.current);
    };
    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      onMessage?.(data);
    };
    ws.onclose = () => {
      setIsConnected(false);
      if (autoReconnect) reconnectTimerRef.current = setTimeout(connect, reconnectInterval);
    };
    ws.onerror = () => ws.close();
  }, [url, onMessage, reconnectInterval, autoReconnect]);

  const sendMessage = useCallback((data: any) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(data));
    }
  }, []);

  const disconnect = useCallback(() => {
    if (reconnectTimerRef.current) clearTimeout(reconnectTimerRef.current);
    wsRef.current?.close();
    setIsConnected(false);
  }, []);

  useEffect(() => {
    connect();
    return () => disconnect();
  }, [connect, disconnect]);

  return { isConnected, sendMessage, disconnect };
}
