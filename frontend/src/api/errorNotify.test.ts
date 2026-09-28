import { describe, it, expect, beforeEach } from "vitest";
import { shouldSuppress, _resetNotifyRegistry } from "./errorNotify";

describe("shouldSuppress", () => {
  beforeEach(() => {
    _resetNotifyRegistry();
  });

  it("U-05: 首次不抑制", () => {
    expect(shouldSuppress("k1", 1000)).toBe(false);
  });

  it("U-05: 窗口内同 key 抑制", () => {
    expect(shouldSuppress("k1", 1000)).toBe(false);
    expect(shouldSuppress("k1", 2000)).toBe(true);
    expect(shouldSuppress("k1", 3500)).toBe(true);
  });

  it("U-05: 窗口外放行", () => {
    expect(shouldSuppress("k1", 1000)).toBe(false);
    expect(shouldSuppress("k1", 4001)).toBe(false);
  });

  it("U-05: 不同 key 互不影响", () => {
    expect(shouldSuppress("k1", 1000)).toBe(false);
    expect(shouldSuppress("k2", 1500)).toBe(false);
    expect(shouldSuppress("k1", 2000)).toBe(true);
    expect(shouldSuppress("k2", 2500)).toBe(true);
  });

  it("U-05: 自定义 windowMs", () => {
    expect(shouldSuppress("k1", 1000, 5000)).toBe(false);
    expect(shouldSuppress("k1", 4000, 5000)).toBe(true);
    expect(shouldSuppress("k1", 6001, 5000)).toBe(false);
  });
});
