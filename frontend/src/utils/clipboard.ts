/**
 * 剪贴板复制工具。
 *
 * 优先使用 `navigator.clipboard`（需要安全上下文），不可用（http 域名、旧浏览器、
 * jsdom 测试环境）时回退到隐藏 textarea + `document.execCommand("copy")`，
 * 保证「可复制」在非 HTTPS 环境下同样成立。
 */
export async function copyToClipboard(text: string): Promise<boolean> {
  if (!text) return false;

  try {
    if (typeof navigator !== "undefined" && navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(text);
      return true;
    }
  } catch {
    // 继续走回退方案
  }

  try {
    if (typeof document === "undefined") return false;
    const textarea = document.createElement("textarea");
    textarea.value = text;
    textarea.setAttribute("readonly", "");
    textarea.style.position = "fixed";
    textarea.style.top = "-1000px";
    textarea.style.opacity = "0";
    document.body.appendChild(textarea);
    textarea.select();
    const ok = document.execCommand ? document.execCommand("copy") : false;
    document.body.removeChild(textarea);
    return Boolean(ok);
  } catch {
    return false;
  }
}
