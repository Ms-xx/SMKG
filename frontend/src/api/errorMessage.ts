export interface ErrorLike {
  code?: string;
  message?: string;
  status?: number;
  detail?: unknown;
}

function isString(value: unknown): value is string {
  return typeof value === "string";
}

function stringifyDetail(detail: unknown): string {
  if (isString(detail)) return detail;
  if (detail && typeof detail === "object") {
    try {
      return JSON.stringify(detail);
    } catch {
      return "请求参数错误";
    }
  }
  return "请求参数错误";
}

export function mapErrorToChineseMessage(error: ErrorLike): string {
  const code = error?.code;
  const msg = error?.message ?? "";
  const status = error?.status;

  if (code === "ECONNABORTED" || (isString(msg) && msg.toLowerCase().includes("timeout"))) {
    return "网络请求超时，请稍后重试";
  }
  if (msg === "Network Error") {
    return "网络连接失败，请检查网络连接";
  }
  if (typeof status === "number" && status >= 500) {
    return "服务暂时不可用，请稍后重试";
  }
  if (status === 401) {
    return "登录状态已失效，请重新登录";
  }
  if (typeof status === "number" && status >= 400) {
    return stringifyDetail(error?.detail);
  }
  return "请求失败，请稍后重试";
}
