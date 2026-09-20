import { describe, it, expect, vi, beforeEach } from "vitest";
import api from "./index";
import axios from "axios";
import { message } from "antd";

describe("api axios 实例", () => {
  beforeEach(() => {
    localStorage.clear();
    vi.restoreAllMocks();
  });

  it("创建实例并配置默认值", () => {
    expect(api.defaults.baseURL).toBe("/api/v1");
    expect(api.defaults.timeout).toBe(30000);
  });

  it("请求拦截器注入 Bearer token", () => {
    const req = (api.interceptors.request as any).handlers[0];
    localStorage.setItem("access_token", "tok123");
    const config = req.fulfilled({ headers: {} });
    expect(config.headers.Authorization).toBe("Bearer tok123");

    localStorage.removeItem("access_token");
    const config2 = req.fulfilled({ headers: {} });
    expect(config2.headers.Authorization).toBeUndefined();
  });

  it("请求拦截器错误透传", async () => {
    const req = (api.interceptors.request as any).handlers[0];
    await expect(req.rejected(new Error("boom"))).rejects.toThrow("boom");
  });

  it("响应拦截器返回 data", () => {
    const res = (api.interceptors.response as any).handlers[0];
    expect(res.fulfilled({ data: { ok: 1 } })).toEqual({ ok: 1 });
  });

  it("响应拦截器非 401 错误提示并拒绝", async () => {
    const spy = vi.spyOn(message, "error").mockImplementation(() => ({}) as any);
    const res = (api.interceptors.response as any).handlers[0];
    const err = {
      response: { status: 500, data: { detail: "服务器错误" } },
      config: { headers: {} },
      message: "x",
    };
    await expect(res.rejected(err)).rejects.toBe(err);
    expect(spy).toHaveBeenCalledWith("服务器错误");
  });

  it("响应拦截器 401 刷新 token 成功", async () => {
    localStorage.setItem("refresh_token", "rt");
    const postSpy = vi
      .spyOn(axios, "post")
      .mockResolvedValue({ data: { data: { access_token: "new", refresh_token: "nrt" } } });
    const res = (api.interceptors.response as any).handlers[0];
    const err = {
      response: { status: 401, data: {} },
      config: { headers: {}, _retry: false, url: "/x" },
      message: "401",
    };
    try {
      await res.rejected(err);
    } catch {
      // 忽略重发请求在 jsdom 中失败的情况
    }
    expect(postSpy).toHaveBeenCalled();
    expect(localStorage.getItem("access_token")).toBe("new");
    expect(localStorage.getItem("refresh_token")).toBe("nrt");
  });
});
