import { message } from "antd";

const _lastNotify: Map<string, number> = new Map();

export function shouldSuppress(key: string, now: number, windowMs = 3000): boolean {
  const last = _lastNotify.get(key);
  if (last === undefined) {
    _lastNotify.set(key, now);
    return false;
  }
  if (now - last < windowMs) {
    return true;
  }
  _lastNotify.set(key, now);
  return false;
}

export function notifyGraphError(msg: string, key: string): void {
  if (!shouldSuppress(key, Date.now())) {
    message.warning(msg);
  }
}

export function _resetNotifyRegistry(): void {
  _lastNotify.clear();
}
