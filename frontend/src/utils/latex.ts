/**
 * LaTeX 公式前端工具（与后端 `app/services/latex_format.py` 口径保持一致）。
 *
 * 后端已保证「存储与接口的 latex 字段 = 无定界符的规范主体」，但历史数据可能
 * 仍带有定界符或数学环境，因此渲染前统一做一次防御性剥离，避免把 `$$` 直接
 * 交给 KaTeX 导致渲染异常。
 */

/** 数学环境 → 是否行间（display）。 */
const MATH_ENVIRONMENTS: Record<string, boolean> = {
  equation: true,
  "equation*": true,
  align: true,
  "align*": true,
  aligned: true,
  gather: true,
  "gather*": true,
  multline: true,
  "multline*": true,
  eqnarray: true,
  "eqnarray*": true,
  displaymath: true,
  math: false,
};

const ENV_RE = /\\begin\{([a-zA-Z*]+)\}([\s\S]*?)\\end\{\1\}/;
const PIX2TEX_TOKENS = ["[[START_SOLUTION]]", "[[END_SOLUTION]]"];

/** 剥离公式定界符与数学环境，返回 LaTeX 主体（不含定界符）。 */
export function toLatexBody(raw?: string | null): string {
  let text = (raw ?? "").trim();
  if (!text) return "";
  for (const token of PIX2TEX_TOKENS) {
    text = text.split(token).join("");
  }
  text = text.trim();
  if (!text) return "";

  // 最多剥离 4 轮，兼容 `\[E=mc^{2}\]$$` 这类多重残留
  for (let i = 0; i < 4; i += 1) {
    const before = text;
    const env = ENV_RE.exec(text);
    if (env && env[0] === text && MATH_ENVIRONMENTS[env[1].toLowerCase()] !== undefined) {
      text = env[2].trim();
      continue;
    }
    const paired: [string, string][] = [
      ["$$", "$$"],
      ["\\[", "\\]"],
      ["\\(", "\\)"],
      ["$", "$"],
    ];
    let unwrapped = false;
    for (const [left, right] of paired) {
      if (
        text.startsWith(left) &&
        text.endsWith(right) &&
        text.length > left.length + right.length
      ) {
        const inner = text.slice(left.length, text.length - right.length).trim();
        if (inner) {
          text = inner;
          unwrapped = true;
          break;
        }
      }
    }
    if (unwrapped) continue;
    // 单侧残留
    const singles = ["$$", "\\[", "\\]", "\\(", "\\)"];
    for (const token of singles) {
      if (text.startsWith(token)) {
        text = text.slice(token.length).trim();
        unwrapped = true;
        break;
      }
      if (text.endsWith(token)) {
        text = text.slice(0, text.length - token.length).trim();
        unwrapped = true;
        break;
      }
    }
    if (!unwrapped || text === before) break;
  }
  return text.trim();
}

/** 给 LaTeX 主体加统一定界符（行内 `$...$` / 行间 `$$...$$`），用于复制。 */
export function wrapLatex(body?: string | null, display = false): string {
  const text = (body ?? "").trim();
  if (!text) return "";
  const delimiter = display ? "$$" : "$";
  return `${delimiter}${text}${delimiter}`;
}

/** 公式在页面中的展示方向文案（统一术语，便于测试与无障碍标签）。 */
export function formulaDirectionLabel(display: boolean): string {
  return display ? "行间公式" : "行内公式";
}
