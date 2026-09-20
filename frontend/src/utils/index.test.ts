import { describe, it, expect, beforeEach } from "vitest";
import { getAccessToken, getRefreshToken, clearAuth, formatFileSize, formatDate } from "./index";

describe("utils", () => {
  beforeEach(() => {
    localStorage.clear();
  });

  describe("localStorage token helpers", () => {
    it("getAccessToken 读取 access_token", () => {
      localStorage.setItem("access_token", "abc");
      expect(getAccessToken()).toBe("abc");
    });

    it("getRefreshToken 读取 refresh_token", () => {
      localStorage.setItem("refresh_token", "def");
      expect(getRefreshToken()).toBe("def");
    });

    it("clearAuth 清除两个 token", () => {
      localStorage.setItem("access_token", "a");
      localStorage.setItem("refresh_token", "b");
      clearAuth();
      expect(localStorage.getItem("access_token")).toBeNull();
      expect(localStorage.getItem("refresh_token")).toBeNull();
    });
  });

  describe("formatFileSize", () => {
    it("0 字节返回 0 B", () => {
      expect(formatFileSize(0)).toBe("0 B");
    });

    it("字节级", () => {
      expect(formatFileSize(512)).toBe("512 B");
    });

    it("KB 级", () => {
      expect(formatFileSize(1024)).toBe("1 KB");
      expect(formatFileSize(1536)).toBe("1.5 KB");
    });

    it("MB 级", () => {
      expect(formatFileSize(1024 * 1024)).toBe("1 MB");
    });

    it("GB 级", () => {
      expect(formatFileSize(1024 * 1024 * 1024)).toBe("1 GB");
    });
  });

  describe("formatDate", () => {
    it("返回中文本地化字符串", () => {
      const result = formatDate("2026-01-01T00:00:00Z");
      expect(typeof result).toBe("string");
      expect(result.length).toBeGreaterThan(0);
    });
  });
});
