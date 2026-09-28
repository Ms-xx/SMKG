import { useCallback, useMemo, useState } from "react";
import katex from "katex";
import "katex/dist/katex.min.css";
import { Button, Tooltip, Typography, message } from "antd";
import { CheckOutlined, CopyOutlined, WarningOutlined } from "@ant-design/icons";
import { copyToClipboard } from "../../utils/clipboard";
import { toLatexBody, wrapLatex } from "../../utils/latex";
import "./LatexFormula.css";

export interface LatexFormulaProps {
  /** LaTeX 主体或带定界符的串（组件内部会统一剥离定界符）。 */
  latex?: string | null;
  /** `true` 行间公式（居中、可带编号），`false` 行内公式。 */
  display?: boolean;
  /** 公式编号（来自后端 `formula_number`）。 */
  number?: string | null;
  /** 后端标注的规范化状态；`false` 表示未成功转 LaTeX，按原文降级展示。 */
  normalized?: boolean | null;
  /** 是否展示复制按钮。 */
  copyable?: boolean;
  className?: string;
}

/**
 * 统一 LaTeX 公式渲染组件。
 *
 * - **渲染**：KaTeX，`trust: false`（禁止原始 HTML）、`throwOnError: true` 以便
 *   精确捕获失败并降级，而不是把红色报错文本塞进正文；
 * - **风格统一**：行内/行间两种版式由同一组件承载，行间居中 + 编号右对齐；
 * - **可复制**：复制内容为**带统一定界符的 LaTeX**（行间 `$$...$$` / 行内 `$...$`），
 *   可直接粘贴进论文或 Markdown；
 * - **异常处理**：渲染失败或后端标注 `normalized === false` 时，降级为等宽原文
 *   展示并给出提示，保证页面不白屏、不丢信息。
 */
export default function LatexFormula({
  latex,
  display = false,
  number = null,
  normalized,
  copyable = true,
  className = "",
}: LatexFormulaProps) {
  const body = useMemo(() => toLatexBody(latex), [latex]);
  const [copied, setCopied] = useState(false);

  const { html, failed } = useMemo(() => {
    if (!body) return { html: "", failed: true };
    try {
      return {
        html: katex.renderToString(body, {
          displayMode: display,
          throwOnError: true,
          strict: false,
          trust: false,
          output: "html",
        }),
        failed: false,
      };
    } catch {
      return { html: "", failed: true };
    }
  }, [body, display]);

  const copyText = useMemo(() => wrapLatex(body, display), [body, display]);

  const handleCopy = useCallback(async () => {
    const ok = await copyToClipboard(copyText);
    if (ok) {
      setCopied(true);
      message.success("已复制 LaTeX 公式");
      window.setTimeout(() => setCopied(false), 1500);
    } else {
      message.warning("复制失败，请手动选择公式文本");
    }
  }, [copyText]);

  // 空公式：与元素面板既有文案保持一致
  if (!body) {
    return <Typography.Text type="secondary">[无文本内容]</Typography.Text>;
  }

  const degraded = failed || normalized === false;
  const wrapperClass = [
    "latex-formula",
    display ? "is-display" : "is-inline",
    degraded ? "is-degraded" : "",
    className,
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <span className={wrapperClass} data-testid="latex-formula" data-display={display}>
      <span className="latex-formula-content">
        {degraded ? (
          <Tooltip title="未识别为标准 LaTeX，已按原文展示">
            <code className="latex-formula-fallback">
              <WarningOutlined className="latex-formula-warning" />
              {body}
            </code>
          </Tooltip>
        ) : (
          // KaTeX 输出：trust=false 已禁用原始 HTML，此处注入安全
          <span className="latex-formula-body" dangerouslySetInnerHTML={{ __html: html }} />
        )}
      </span>
      {number ? <span className="latex-formula-number">({number})</span> : null}
      {copyable ? (
        <Tooltip title={copied ? "已复制" : "复制 LaTeX"}>
          <Button
            type="text"
            size="small"
            className="latex-formula-copy"
            aria-label="复制 LaTeX 公式"
            icon={copied ? <CheckOutlined /> : <CopyOutlined />}
            onClick={handleCopy}
          />
        </Tooltip>
      ) : null}
    </span>
  );
}
