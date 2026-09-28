# 前端格式规范清单（Style Guide）

> 适用范围：`frontend/`（React 18 + Vite + TypeScript + Ant Design 5 + Tailwind CSS）
> 目标：统一布局结构、命名、主题变量、字体间距、色彩、按钮表单、响应式断点与文件组织，消除重复样式与不一致命名。
> 维护方式：**设计令牌为唯一事实来源**，新增页面/组件先查本清单与 `src/styles/global.css`，禁止再写硬编码色值。

---

## 1. 技术栈与目录组织

### 1.1 技术栈
- 框架：React 18 + TypeScript（函数组件 + Hooks）
- 构建：Vite
- UI 库：Ant Design 5（全局主题在 `src/main.tsx` 的 `ConfigProvider` 统一配置）
- 样式：Tailwind CSS（落地页等自定义视觉）+ 全局 CSS 变量（业务后台）
- 状态：Zustand（`@store`）；数据请求：TanStack Query + 自封装 `@api`
- 路由：React Router v6

### 1.2 目录结构（按职责分层）
```
src/
├── components/          # 通用复用组件
│   ├── Layout/         # MainLayout / Header / Sidebar（后台外壳）
│   └── BrandLogo.tsx    # 品牌 Logo
├── pages/               # 页面级组件，按业务域分目录
│   ├── Dashboard/
│   ├── Documents/
│   ├── KnowledgeGraph/
│   ├── ...
├── store/               # Zustand 状态
├── api/                 # 接口封装
├── types/               # 全局 TS 类型
├── hooks/               # 自定义 Hooks
├── utils/               # 纯函数工具
├── styles/
│   ├── global.css       # 设计令牌 + 全局基础样式（★唯一变量来源）
│   └── landing.css      # 落地页专属样式
└── main.tsx            # 入口 + antd 全局主题
```

### 1.3 文件命名规范
| 类型 | 规则 | 示例 |
|---|---|---|
| 页面/组件 | PascalCase，与文件名一致 | `DashboardPage.tsx`、`MainLayout.tsx` |
| 目录 | 业务域大驼峰 | `KnowledgeGraph/` |
| 样式 | kebab-case | `global.css`、`landing.css` |
| Hooks | `use` 开头小驼峰 | `useDocumentStore.ts` |
| 测试 | 被测文件同名 + `.test.tsx` | `Header.test.tsx` |
| 别名 | 已配置 `@`、`@components`、`@pages`、`@store`、`@api`、`@types`、`@utils` | 导入一律用别名，禁止深层相对路径 `../../` |

### 1.4 代码缩进与格式
- 缩进：2 空格；字符串优先单引号；JSX 属性使用双引号。
- 分号收尾；行宽建议 ≤ 100 字符。
- 组件：函数声明式 `export default function Xxx()`；辅助常量/类型置于组件上方。
- 一个文件只导出一个默认组件；测试、样式就近放置。

---

## 2. 设计令牌（Design Tokens）

> 定义位置：`src/styles/global.css :root`；antd 对应 token 在 `src/main.tsx` 的 `theme.token` / `theme.components`。**二者必须保持一致。**

### 2.1 色彩体系
| 用途 | 变量值 | CSS 变量 | antd token |
|---|---|---|---|
| 品牌主色 | `#4f46e5` 靛蓝 | `--color-primary` | `colorPrimary` |
| 主色 hover | `#4338ca` | `--color-primary-hover` | — |
| 主色浅底 | `#eef2ff` | `--color-primary-light` | Menu selected bg |
| 点缀色 | `#06b6d4` 青 | `--color-accent` | — |
| 成功 | `#10b981` | `--color-success` | `colorSuccess` |
| 警告 | `#f59e0b` | `--color-warning` | `colorWarning` |
| 错误 | `#ef4444` | `--color-error` | `colorError` |
| 页面外层背景 | `#f4f6fb` | `--color-bg-layout` | `colorBgLayout` |
| 卡片/内容背景 | `#ffffff` | `--color-bg-container` | — |
| 主文字 | `#0f172a` | `--color-text-primary` | — |
| 次文字 | `#475569` | `--color-text-secondary` | — |
| 弱文字 | `#94a3b8` | `--color-text-muted` | — |
| 边框 | `#e6e8f0` | `--color-border` | — |

**禁止**：在业务页面内再出现 `#1890ff`、`#52c41a`、`#722ed1`、`#faad14`、`#f0f2f5` 等 antd v4 旧硬编码色。状态色一律用 `Tag` 的 `success/processing/error/default` 语义或上面的变量。

### 2.2 圆角
| 变量 | 值 | 适用 |
|---|---|---|
| `--radius-sm` | 8px | 小按钮、标签、输入框 |
| `--radius-md` | 10px | antd 默认 `borderRadius` |
| `--radius-lg` | 12px | 卡片、内容区 |
| `--radius-xl` | 16px | 登录卡片、大弹窗、Hero 元素 |

### 2.3 阴影
- `--shadow-sm`：常规卡片
- `--shadow-md`：悬浮卡片、下拉
- `--shadow-lg`：品牌主视觉（登录卡片、落地 Hero）

### 2.4 间距刻度（4 的倍数）
`--space-1`=4 · `--space-2`=8 · `--space-3`=12 · `--space-4`=16 · `--space-5`=24 · `--space-6`=32。
页面内边距统一 24px（移动端 12px）；卡片内边距由 antd `Card.paddingLG=20` 提供。

---

## 3. 布局结构规范

### 3.1 后台外壳（MainLayout）
- 顶栏高 60px（`headerHeight: 60`），白底，底部 1px 边框 `--color-border`。
- 侧边栏宽 256px（折叠 80px），白底，选中项为靛蓝浅底 + 8px 圆角。
- 内容区：外边距 16px，内边距 24px，白底圆角 12px，置于 `#f4f6fb` 页面底色上。
- **所有受保护页面都走 MainLayout，不在页面内再写整页背景/外边距。**

### 3.2 页面内部结构
- 页面根容器统一使用 `.app-page`（或交给 MainLayout 内容区），区块间距用 `--space-*`。
- 卡片统一 `Card`（圆角 12、阴影 sm），不要手写 `boxShadow`。
- 栅格用 antd `Row/Col`，区间 gutter 16。

---

## 4. 字体与排版
- 字体栈（已在 token 与 body 统一）：
  `-apple-system, "PingFang SC", "Microsoft YaHei", ...`
- 层级：页面标题 20px/600；区块标题 16px/600；正文 14px/400；辅助说明 12px。
- 数字/英文可用等宽感，但不要引入新字体文件。

---

## 5. 按钮与表单
- **主操作**：`Button type="primary"`（自动渲染品牌靛蓝，勿再写 `style={{background:'#1890ff'}}`）。
- **次操作**：默认按钮 / `type="text"` / `type="link"`。
- 按钮高度统一 36px（`controlHeight: 36`），字重 500；危险操作用 `danger`。
- 表单：统一 antd `Form/Input/Select/DatePicker`，圆角、聚焦色由全局 token 提供；表单标签右对齐或顶部对齐保持一致。
- 表格：表头背景 `#f8fafc`、字重 600；操作列固定右侧。

---

## 6. 响应式断点
| 断点 | 宽度 | 行为 |
|---|---|---|
| 桌面 | ≥1024px | 侧边栏展开，栅格多列 |
| 平板 | 768–1023px | 侧边栏可折叠，内容区单/双列 |
| 移动 | <768px | `.app-page` 内边距降为 12px；栅格强制单列；顶部操作区换行 |

- 落地页自定义网格在 `<768px` 自动收起（`hidden md:block` 等）。
- 不允许出现横向滚动；复杂工作台（标注/图谱）内部自行滚动。

---

## 7. 动效与微交互
- 过渡统一 `transition: all .2s ease`（antd 组件自带）。
- 落地页滚动显现用 `reveal` 类；后台页面不做重动效，仅保留 hover / focus 反馈。

---

## 8. 不兼容部分的调整建议（存量代码）

以下为现状与本规范的差异，按优先级处理：

1. **【高优先级】硬编码旧色值**
   - 位置：`DashboardPage.tsx` 的 `quickActions`（`#1890ff/#52c41a/#722ed1/#faad14`）等。
   - 建议：主操作图标色改为 `var(--color-primary)`；统计卡如需区分色，用语义色变量（success/warning/error）并收敛到最多 4 色。

2. **【高优先级】散落内联 `style={{}}`**
   - 现状：Header、各页面大量内联样式。
   - 建议：通用外观抽到 `global.css` 类（如 `.app-card`、`.app-page`）；与业务强相关的内联样式保留即可，颜色/圆角必须引用 CSS 变量，不写死十六进制。

3. **【中优先级】页面标题不统一**
   - 现状：各页 h1 字号/边距各异。
   - 建议：统一页面头部组件（标题 20px/600 + 副标题 14px secondary），后续抽取 `<PageHeader />`。

4. **【中优先级】登录页 / 落地页与后台主题割裂**
   - 已处理：登录页改为品牌渐变 + Logo；后台通过 ConfigProvider 统一为靛蓝。
   - 后续：将落地页 `landing.css` 中的颜色值也替换为 `:root` 变量，避免双份维护。

5. **【低优先级】未使用的样式与重复类**
   - 建议清理全局未被引用的 CSS；Tailwind 仅用于落地页，业务后台不混用 Tailwind 工具类，以免两套样式体系冲突。

6. **【低优先级】`#f0f25` 类旧背景**
   - 已统一为 `--color-bg-layout: #f4f6fb`，检索全局确认无残留 `#f0f2f5` / `#f5f5f5` 页面级背景。

---

## 9. 落地检查清单（新增页面时自查）
- [ ] 是否复用 MainLayout，未自写整页背景/外边距？
- [ ] 颜色是否取自 `global.css` 变量 / antd token，无硬编码十六进制？
- [ ] 按钮是否只用 antd 类型（primary/default/text/link/danger），未手写背景？
- [ ] 间距是否落在 4 的倍数刻度上？
- [ ] 移动端是否单列、无横向滚动？
- [ ] 组件/文件命名是否 PascalCase、导入是否用别名？
- [ ] 是否补充了对应 `.test.tsx`？
