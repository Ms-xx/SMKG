export const GRAPH_SLOW_TIMEOUT_MS = 60000;

export const SLOW_GRAPH_PATHS = [
  "/knowledge-graph/trends",
  "/knowledge-graph/anomalies",
  "/knowledge-graph/statistics",
  "/knowledge-graph/rag/graph/stats",
];

export function isSlowGraphPath(url: string): boolean {
  return SLOW_GRAPH_PATHS.some((p) => url.endsWith(p));
}
