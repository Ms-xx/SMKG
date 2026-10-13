export const GRAPH_SLOW_TIMEOUT_MS = 60000;

export const SLOW_GRAPH_PATHS = [
  "/knowledge-graph/trends",
  "/knowledge-graph/anomalies",
  "/knowledge-graph/statistics",
  "/knowledge-graph/rag/graph/stats",
];

/**
 * LLM 生成类接口超时。
 *
 * 实测（qwen/qwen3-4b-2507 跑在 CPU 上，约 7.4 token/s）：196 tokens 的回答需约 27s。
 * 全局默认 30s 几乎没有余量，稍长一点就触发 `timeout of 30000ms exceeded`；
 * 而此刻后端仍在生成，用户拿到的是无意义的客户端中断，而不是真实结果或后端的错误信息。
 *
 * 取值刻意**显著高于后端 LLM_TIMEOUT（默认 60s）**：让后端自己的超时先发生并返回
 * 带 detail 的真实错误，前端只做兜底。
 */
export const LLM_TIMEOUT_MS = 120000;

/** 走 LLM 生成的接口路径（后缀匹配，与 SLOW_GRAPH_PATHS 同风格） */
export const LLM_PATHS = [
  "/knowledge-graph/rag/query",
  "/multi-agent/run",
  "/multi-agent/resolve",
  "/source-anchor/compare",
  "/citation-graph/survey",
  "/writing-assistant/outline",
  "/writing-assistant/translate",
  "/writing-assistant/llm-generate",
];

export function isSlowGraphPath(url: string): boolean {
  return SLOW_GRAPH_PATHS.some((p) => url.endsWith(p));
}

export function isLlmPath(url: string): boolean {
  return LLM_PATHS.some((p) => url.endsWith(p));
}
