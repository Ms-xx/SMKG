import { describe, it, expect } from "vitest";
import { mapErrorToChineseMessage } from "./errorMessage";

describe("mapErrorToChineseMessage", () => {
  it("U-04: 超时（ECONNABORTED）→ 中文超时文案", () => {
    const text = mapErrorToChineseMessage({
      code: "ECONNABORTED",
      message: "timeout of 30000ms exceeded",
    });
    expect(text).toBe("网络请求超时，请稍后重试");
    expect(text).not.toContain("timeout of");
  });

  it("U-04: 超时（message 含 timeout）→ 中文超时文案", () => {
    const text = mapErrorToChineseMessage({ message: "timeout of 60000ms exceeded" });
    expect(text).toBe("网络请求超时，请稍后重试");
    expect(text).not.toContain("timeout of");
  });

  it("U-04: Network Error → 中文网络文案", () => {
    expect(mapErrorToChineseMessage({ message: "Network Error" })).toBe(
      "网络连接失败，请检查网络连接",
    );
  });

  it("U-04: 5xx → 中文服务文案", () => {
    expect(mapErrorToChineseMessage({ status: 500, message: "x" })).toBe(
      "服务暂时不可用，请稍后重试",
    );
    expect(mapErrorToChineseMessage({ status: 502, message: "x" })).toBe(
      "服务暂时不可用，请稍后重试",
    );
  });

  it("U-04: 401 → 登录失效文案", () => {
    expect(mapErrorToChineseMessage({ status: 401, message: "x" })).toBe(
      "登录状态已失效，请重新登录",
    );
  });

  it("U-04: 4xx（非 401）→ detail 字符串化", () => {
    expect(mapErrorToChineseMessage({ status: 422, detail: "参数错误" })).toBe("参数错误");
    expect(mapErrorToChineseMessage({ status: 400, detail: [{ msg: "bad" }] })).toBe(
      '[{"msg":"bad"}]',
    );
    expect(mapErrorToChineseMessage({ status: 404, detail: null })).toBe("请求参数错误");
  });

  it("U-04: 未识别 → 通用中文文案", () => {
    expect(mapErrorToChineseMessage({})).toBe("请求失败，请稍后重试");
    expect(mapErrorToChineseMessage({ message: "unknown" })).toBe("请求失败，请稍后重试");
  });

  it("U-04: 所有输出不含英文原文 timeout of", () => {
    const cases = [
      { code: "ECONNABORTED", message: "timeout of 30000ms exceeded" },
      { message: "timeout of 60000ms exceeded" },
      { status: 500, message: "timeout of 30000ms exceeded" },
    ];
    for (const c of cases) {
      expect(mapErrorToChineseMessage(c)).not.toContain("timeout of");
    }
  });
});
