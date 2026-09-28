interface BrandLogoProps {
  /** 渲染尺寸（px），默认 36 */
  size?: number;
}

/**
 * 平台 Logo：融合「科学文献文档」与「知识图谱节点连接」两个核心意象。
 * - 白色折角文档 = 多模态文献解析（OCR / 版面 / 公式 / 图表 / 参考文献）
 * - 两条连线 + 卫星节点 = 局域引用网络与实体关系图谱
 * - 靛蓝 → 青渐变 = 与全站品牌色一致
 */
export default function BrandLogo({ size = 36 }: BrandLogoProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 64 64"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      role="img"
      aria-label="科学文献智能解析平台 Logo"
      style={{ display: "block", flexShrink: 0 }}
    >
      <defs>
        <linearGradient id="brand-bg" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#6366f1" />
          <stop offset="1" stopColor="#06b6d4" />
        </linearGradient>
      </defs>
      <rect width="64" height="64" rx="16" fill="url(#brand-bg)" />
      {/* 图谱连线 */}
      <path
        d="M39 22 L45 16 M23 44 L17 49"
        stroke="rgba(255,255,255,0.55)"
        strokeWidth="2"
        strokeLinecap="round"
      />
      {/* 文献文档 */}
      <path
        d="M23 15 h11 l8 8 v22 a2 2 0 0 1 -2 2 H23 a2 2 0 0 1 -2 -2 V17 a2 2 0 0 1 2 -2 z"
        fill="#ffffff"
      />
      {/* 折角 */}
      <path d="M34 15 l8 8 h-8 z" fill="rgba(99,102,241,0.28)" />
      {/* 正文行 */}
      <line
        x1="25"
        y1="31"
        x2="37"
        y2="31"
        stroke="#6366f1"
        strokeWidth="2"
        strokeLinecap="round"
      />
      <line
        x1="25"
        y1="37"
        x2="33"
        y2="37"
        stroke="#6366f1"
        strokeWidth="2"
        strokeLinecap="round"
      />
      {/* 卫星节点 */}
      <circle cx="48" cy="14" r="5" fill="#ffffff" />
      <circle cx="48" cy="14" r="2" fill="#06b6d4" />
      <circle cx="15" cy="50" r="5" fill="#ffffff" />
      <circle cx="15" cy="50" r="2" fill="#06b6d4" />
    </svg>
  );
}
