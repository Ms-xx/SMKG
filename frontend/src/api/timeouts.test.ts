import { describe, it, expect } from "vitest";
import {
  GRAPH_SLOW_TIMEOUT_MS,
  isLlmPath,
  isSlowGraphPath,
  LLM_PATHS,
  LLM_TIMEOUT_MS,
  SLOW_GRAPH_PATHS,
} from "./timeouts";

describe("timeouts", () => {
  it("GRAPH_SLOW_TIMEOUT_MS 为 60000", () => {
    expect(GRAPH_SLOW_TIMEOUT_MS).toBe(60000);
  });

  it("U-06: 匹配慢路径", () => {
    expect(isSlowGraphPath("/api/v1/knowledge-graph/trends")).toBe(true);
    expect(isSlowGraphPath("/api/v1/knowledge-graph/anomalies")).toBe(true);
    expect(isSlowGraphPath("/api/v1/knowledge-graph/statistics")).toBe(true);
    expect(isSlowGraphPath("/api/v1/knowledge-graph/rag/graph/stats")).toBe(true);
    expect(isSlowGraphPath("/knowledge-graph/trends")).toBe(true);
  });

  it("U-06: 非慢路径返回 false", () => {
    expect(isSlowGraphPath("/api/v1/documents/")).toBe(false);
    expect(isSlowGraphPath("/api/v1/auth/login")).toBe(false);
    expect(isSlowGraphPath("")).toBe(false);
    expect(isSlowGraphPath("/knowledge-graph/trends/extra")).toBe(false);
  });

  it("SLOW_GRAPH_PATHS 包含 4 个路径", () => {
    expect(SLOW_GRAPH_PATHS).toHaveLength(4);
  });

  it("LLM_TIMEOUT_MS 显著高于后端 LLM_TIMEOUT(60s)", () => {
    // 需让后端的超时先触发，前端只做兜底，否则用户只会看到无意义的客户端中断
    expect(LLM_TIMEOUT_MS).toBe(120000);
    expect(LLM_TIMEOUT_MS).toBeGreaterThan(60000);
  });

  it("匹配 LLM 生成类路径", () => {
    expect(isLlmPath("/api/v1/knowledge-graph/rag/query")).toBe(true);
    expect(isLlmPath("/api/v1/multi-agent/run")).toBe(true);
    expect(isLlmPath("/api/v1/multi-agent/resolve")).toBe(true);
    expect(isLlmPath("/api/v1/source-anchor/compare")).toBe(true);
    expect(isLlmPath("/api/v1/citation-graph/survey")).toBe(true);
    expect(isLlmPath("/api/v1/writing-assistant/outline")).toBe(true);
    expect(isLlmPath("/api/v1/writing-assistant/translate")).toBe(true);
    expect(isLlmPath("/api/v1/writing-assistant/llm-generate")).toBe(true);
  });

  it("非 LLM 路径返回 false", () => {
    expect(isLlmPath("/api/v1/documents/")).toBe(false);
    expect(isLlmPath("/api/v1/auth/login")).toBe(false);
    expect(isLlmPath("")).toBe(false);
    expect(isLlmPath("/api/v1/knowledge-graph/rag/health")).toBe(false);
    expect(isLlmPath("/api/v1/knowledge-graph/rag/query/extra")).toBe(false);
  });

  it("LLM_PATHS 与 SLOW_GRAPH_PATHS 无重叠", () => {
    const overlap = LLM_PATHS.filter((p) => SLOW_GRAPH_PATHS.includes(p));
    expect(overlap).toEqual([]);
  });
});
