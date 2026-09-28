import { describe, it, expect } from "vitest";
import { GRAPH_SLOW_TIMEOUT_MS, isSlowGraphPath, SLOW_GRAPH_PATHS } from "./timeouts";

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
});
