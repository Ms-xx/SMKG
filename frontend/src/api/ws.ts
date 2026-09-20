/** 构造标注实时协作 WebSocket 地址（未登录时返回空串，避免无效连接）。 */
export function buildAnnotationWsUrl(documentId: string): string {
  const token = localStorage.getItem("access_token");
  if (!token) return "";
  const query = `token=${encodeURIComponent(token)}`;
  const wsPath = `/api/v1/ws/annotations/${documentId}`;
  const explicitBase = import.meta.env.VITE_WS_BASE_URL as string | undefined;
  if (explicitBase) {
    return `${explicitBase}${wsPath}?${query}`;
  }
  const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
  return `${proto}//${window.location.host}${wsPath}?${query}`;
}
