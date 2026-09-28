import axios, { AxiosError, AxiosInstance, AxiosRequestConfig } from "axios";
import { message } from "antd";
import { mapErrorToChineseMessage } from "./errorMessage";
import { shouldSuppress } from "./errorNotify";

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || "/api/v1",
  timeout: 30000,
  headers: { "Content-Type": "application/json" },
});

api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem("access_token");
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  },
);

api.interceptors.response.use(
  (response) => response.data,
  async (error: AxiosError) => {
    const originalRequest = error.config as AxiosRequestConfig & {
      _retry?: boolean;
      meta?: { silent?: boolean };
    };
    if (error.response?.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true;
      try {
        const refreshToken = localStorage.getItem("refresh_token");
        const response = await axios.post("/api/v1/auth/refresh", { refresh_token: refreshToken });
        const { access_token, refresh_token } = response.data.data || response.data;
        localStorage.setItem("access_token", access_token);
        localStorage.setItem("refresh_token", refresh_token);
        originalRequest.headers!.Authorization = `Bearer ${access_token}`;
        return api(originalRequest);
      } catch {
        localStorage.removeItem("access_token");
        localStorage.removeItem("refresh_token");
        window.location.href = "/login";
        return Promise.reject(error);
      }
    }
    const detail = (error.response?.data as any)?.detail;
    // FastAPI 422 校验错误 detail 是对象数组，不能直接作为 message 子节点渲染（会导致 React 崩溃），统一转字符串
    // 文案策略：detail 为字符串时优先保留（既有行为，含中文 detail）；否则用中文文案映射（超时/网络/5xx 等）
    const notifyText =
      typeof detail === "string"
        ? detail
        : mapErrorToChineseMessage({
            code: (error as any)?.code,
            message: error.message,
            status: error.response?.status,
            detail,
          }) ||
          error.message ||
          "请求失败";
    const notifyKey = `${error.response?.status ?? "net"}:${originalRequest?.url ?? ""}`;
    const isSilent = originalRequest?.meta?.silent === true;
    if (!isSilent && !shouldSuppress(notifyKey, Date.now())) {
      message.error(notifyText);
    }
    return Promise.reject(error);
  },
);

type ApiClient = Omit<AxiosInstance, "get" | "post" | "put" | "patch" | "delete"> & {
  get<T = any>(url: string, config?: AxiosRequestConfig): Promise<T>;
  post<T = any>(url: string, data?: any, config?: AxiosRequestConfig): Promise<T>;
  put<T = any>(url: string, data?: any, config?: AxiosRequestConfig): Promise<T>;
  patch<T = any>(url: string, data?: any, config?: AxiosRequestConfig): Promise<T>;
  delete<T = any>(url: string, config?: AxiosRequestConfig): Promise<T>;
};

export default api as unknown as ApiClient;
