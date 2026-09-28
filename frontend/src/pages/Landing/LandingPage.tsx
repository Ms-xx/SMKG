import { Fragment, useEffect, useState } from "react";
import { Button, Space, Tag, Typography } from "antd";
import { useNavigate } from "react-router-dom";
import { useAuthStore } from "@store/authStore";
import {
  FileSearchOutlined,
  SafetyCertificateOutlined,
  ApiOutlined,
  DeploymentUnitOutlined,
  BulbOutlined,
  ReadOutlined,
  TranslationOutlined,
  RadarChartOutlined,
  PartitionOutlined,
  EditOutlined,
  ArrowRightOutlined,
  LoginOutlined,
  ExperimentOutlined,
  DatabaseOutlined,
  ThunderboltOutlined,
  TeamOutlined,
  CheckCircleFilled,
  RightOutlined,
  ClusterOutlined,
} from "@ant-design/icons";
import "../../styles/landing.css";
import BrandLogo from "@components/BrandLogo";

const { Title, Paragraph } = Typography;

/** 五大能力维度（与 others/08-需求与能力对照.md 一致）。 */
const CAPABILITIES = [
  {
    icon: <FileSearchOutlined />,
    title: "多模态与细粒度文档感知",
    desc: "扫描件 OCR、双栏排版、复杂公式、图表、层级标题树与参考文献的结构化抽取；并基于正文语义指纹识别同一论文的不同版本（如 arXiv v1↔v7）。",
  },
  {
    icon: <SafetyCertificateOutlined />,
    title: "抗幻觉 RAG 与多文推理",
    desc: "回答细粒度问题（作者与机构、超参设置、GPU 型号、评测分数）时强制附原文出处与位置锚点；并支持跨多篇论文的演进对比与长上下文关联推理。",
  },
  {
    icon: <ApiOutlined />,
    title: "自主工具调用与闭环探索",
    desc: "集成 arXiv / PubMed 等外部接口与本地代码执行环境，实现「给定题名或参考文献 → 自动下钻下载入库 → 定期追踪 → 个性化推荐」闭环。",
  },
  {
    icon: <DeploymentUnitOutlined />,
    title: "图谱拓扑挖掘与学术洞察",
    desc: "基于批量文献构建局域引用网络，用 PageRank 与介数中心性挖掘基石论文与边缘衍生论文，自动生成领域综述并探索真正有价值的 Future Work。",
  },
  {
    icon: <BulbOutlined />,
    title: "学术 Copilot 与数据可视化",
    desc: "从 idea 生成带真实可溯源参考文献的论文框架，自动产出 TikZ / Graphviz / Mermaid / Matplotlib 架构图脚本，并将 CSV 转为符合学术规范的图表与图注。",
  },
];

/** 六大功能模块概览。 */
const MODULES = [
  {
    icon: <ReadOutlined />,
    name: "模块一 · PDF 管理与细粒度解析",
    points: ["单篇/批量上传", "语义级版本去重", "标题树 / 表格 / 公式 / 图表"],
  },
  {
    icon: <SafetyCertificateOutlined />,
    name: "模块二 · 抗幻觉知识问答",
    points: ["单篇细粒度问答", "原文出处与页级锚点", "跨文献对比推理"],
  },
  {
    icon: <TranslationOutlined />,
    name: "模块三 · 版式感知阅读与翻译",
    points: ["单双栏原生渲染", "[n] ↔ 参考文献双向跳转", "中英对照同步滚动"],
  },
  {
    icon: <RadarChartOutlined />,
    name: "模块四 · 检索、追踪与推荐",
    points: ["题名/参考文献下钻下载", "arXiv 定期追踪", "复现性加权推荐"],
  },
  {
    icon: <PartitionOutlined />,
    name: "模块五 · 引用图谱与综述生成",
    points: ["局域引用网络", "基石节点挖掘", "自动综述与前沿探索"],
  },
  {
    icon: <EditOutlined />,
    name: "模块六 · 写作辅助与可视化",
    points: ["真实参考文献框架", "架构拓扑图脚本", "CSV 图表与图注"],
  },
];

/** 典型适用场景。 */
const SCENARIOS = [
  {
    icon: <TeamOutlined />,
    title: "课题组文献调研",
    desc: "批量导入方向文献，自动解析并搭建引用网络，快速定位该领域的基石工作与研究脉络。",
  },
  {
    icon: <ExperimentOutlined />,
    title: "实验细节核对与复现",
    desc: "针对超参数、硬件环境、评测指标等细节提问，答案附原文锚点，便于逐条核对与复现。",
  },
  {
    icon: <ThunderboltOutlined />,
    title: "追踪领域最新进展",
    desc: "定期刷新 arXiv 最新论文并结合本地文献库计算相关性，优先推送易复现的开源工作。",
  },
  {
    icon: <DatabaseOutlined />,
    title: "综述撰写与图表产出",
    desc: "自动生成领域综述与论文框架，输出拓扑图脚本和规范化图表，缩短写作与制图周期。",
  },
];

const STACK = [
  "FastAPI",
  "Celery",
  "MySQL",
  "Redis",
  "Neo4j",
  "MinIO",
  "React 18",
  "TypeScript",
  "Ant Design",
  "GraphRAGTest(:8001)",
];

const HERO_POINTS = [
  "语义级去重：识别同一论文 v1 与 v7 并建议保留最新版",
  "原文溯源：答案附带 document / 页码 / 片段锚点",
  "双向跳转：正文 [n] ↔ 参考文献条目无损跳转",
  "引用网络：PageRank + 介数中心性挖掘基石论文",
  "自动综述：LLM 生成，未配置时降级规则模板",
  "可视化 Copilot：TikZ / Mermaid / Matplotlib + CSV 图注",
];

const PAINS = [
  {
    t: "信息过载与文献时效",
    d: "论文数量爆发式增长，人工检索、过滤、去重与建图成本极高。",
    s: "自动检索 · 语义去重 · 图谱搭建",
  },
  {
    t: "读写效率与学术严谨",
    d: "跨语言阅读、细粒度数据提取与消除模型幻觉，都需要确定性工具。",
    s: "对照翻译 · 锚点溯源 · 结构化抽取",
  },
  {
    t: "创意落地与实践复现",
    d: "从制图到创新点验证，需要深度整合代码环境与外部接口。",
    s: "可视化 Copilot · 外部 API · 复现性推荐",
  },
];

export default function LandingPage() {
  const navigate = useNavigate();
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);
  const [scrolled, setScrolled] = useState(false);

  // 顶部导航滚动后由透明切换为毛玻璃实底
  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 24);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  // 滚动显现：进入视口后为 .reveal 元素加上 .is-visible
  useEffect(() => {
    const els = document.querySelectorAll<HTMLElement>(".landing-page .reveal");
    if (typeof IntersectionObserver === "undefined") {
      els.forEach((el) => el.classList.add("is-visible"));
      return;
    }
    const io = new IntersectionObserver(
      (entries) => {
        entries.forEach((e) => {
          if (e.isIntersecting) {
            e.target.classList.add("is-visible");
            io.unobserve(e.target);
          }
        });
      },
      { threshold: 0.12, rootMargin: "0px 0px -48px 0px" },
    );
    els.forEach((el) => io.observe(el));
    return () => io.disconnect();
  }, []);

  return (
    <div className="landing-page min-h-screen bg-slate-50 text-slate-800">
      {/* 顶部导航：Hero 上透明，滚动后毛玻璃实底 */}
      <header
        className={`fixed inset-x-0 top-0 z-50 transition-all duration-300 ${
          scrolled
            ? "border-b border-slate-200/70 bg-white/85 shadow-[0_8px_30px_-18px_rgba(15,23,42,0.25)] backdrop-blur-xl"
            : "border-b border-transparent bg-transparent"
        }`}
      >
        <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-4">
          <div className="flex items-center gap-2.5">
            <BrandLogo size={36} />
            <span
              className={`text-base font-semibold tracking-tight transition-colors ${
                scrolled ? "text-slate-900" : "text-white"
              }`}
            >
              科学文献智能解析平台
            </span>
          </div>
          <Space>
            <Button
              type="text"
              onClick={() => navigate("/login")}
              data-testid="nav-login"
              style={scrolled ? undefined : { color: "rgba(255,255,255,0.85)" }}
            >
              登录
            </Button>
            <Button
              type="primary"
              icon={<LoginOutlined />}
              onClick={() => navigate("/login")}
              data-testid="nav-cta"
              style={
                scrolled
                  ? {
                      background: "linear-gradient(135deg,#4f46e5,#0891b2)",
                      border: "none",
                      fontWeight: 500,
                    }
                  : {
                      background: "#fff",
                      color: "#4f46e5",
                      borderColor: "#fff",
                      fontWeight: 600,
                      boxShadow: "0 8px 24px -10px rgba(255,255,255,0.6)",
                    }
              }
            >
              开始使用
            </Button>
          </Space>
        </div>
      </header>

      {/* ============ 主视觉 Hero ============ */}
      <section className="landing-hero">
        <div className="orb orb-1" />
        <div className="orb orb-2" />
        <div className="orb orb-3" />
        <div className="grid-overlay" />

        <div className="relative mx-auto max-w-6xl px-6 pb-28 pt-32 md:pt-40">
          <div className="grid items-center gap-12 md:grid-cols-[1.15fr_1fr]">
            {/* 左侧文案 */}
            <div className="reveal is-visible">
              <span className="eyebrow-pill">
                <span className="dot" />
                面向科研全流程 · 实际开发项目
              </span>
              <Title
                level={1}
                style={{
                  color: "#fff",
                  fontWeight: 800,
                  letterSpacing: "-0.02em",
                  lineHeight: 1.15,
                  marginTop: 20,
                  marginBottom: 20,
                  fontSize: "clamp(32px, 5vw, 52px)",
                }}
              >
                多模态科学文献智能解析
                <br />
                <span className="gradient-text">与知识图谱构建平台</span>
              </Title>
              <Paragraph
                className="text-base leading-8"
                style={{ color: "rgba(226,232,240,0.78)", maxWidth: 560 }}
              >
                把 PDF、公式、图表与参考文献变成可检索、可溯源、可推理的结构化知识：
                细粒度解析文献内容，以原文锚点消除问答幻觉，构建局域引用网络挖掘基石论文，
                并生成带真实参考文献的综述与图表，覆盖从检索、阅读到写作的完整科研环节。
              </Paragraph>

              <Space size="middle" className="mt-8">
                <Button
                  type="primary"
                  size="large"
                  onClick={() => navigate("/login")}
                  data-testid="hero-login"
                  style={{
                    background: "linear-gradient(135deg,#6366f1,#06b6d4)",
                    border: "none",
                    fontWeight: 600,
                    height: 48,
                    padding: "0 26px",
                    boxShadow: "0 14px 34px -12px rgba(99,102,241,0.7)",
                  }}
                >
                  立即登录 <ArrowRightOutlined />
                </Button>
                <Button
                  size="large"
                  onClick={() => navigate(isAuthenticated ? "/home" : "/login")}
                  data-testid="hero-secondary"
                  style={{
                    background: "rgba(255,255,255,0.06)",
                    color: "#fff",
                    borderColor: "rgba(255,255,255,0.25)",
                    height: 48,
                    padding: "0 26px",
                  }}
                >
                  {isAuthenticated ? "进入控制台" : "了解功能亮点"}
                </Button>
              </Space>

              <div className="mt-12 grid max-w-md grid-cols-3 gap-6 border-t border-white/10 pt-7">
                {[
                  { k: "6", v: "功能模块" },
                  { k: "5", v: "核心能力" },
                  { k: "4", v: "类适用场景" },
                ].map((s) => (
                  <div key={s.v}>
                    <div
                      className="text-3xl font-bold"
                      style={{ color: "#fff", fontVariantNumeric: "tabular-nums" }}
                    >
                      {s.k}
                    </div>
                    <div className="mt-1 text-xs" style={{ color: "rgba(203,213,225,0.7)" }}>
                      {s.v}
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* 右侧：产品截图 + 能力速览 */}
            <div className="reveal is-visible hidden md:block" style={{ transitionDelay: "0.15s" }}>
              {/* 产品实拍：知识图谱探索 */}
              <div className="relative">
                <div
                  className="animate-float overflow-hidden rounded-2xl border border-white/15 bg-slate-900"
                  style={{
                    boxShadow:
                      "0 40px 80px -30px rgba(2,6,23,0.9), 0 0 0 1px rgba(99,102,241,0.15)",
                  }}
                >
                  <div
                    className="flex items-center gap-1.5 px-3 py-2"
                    style={{ background: "rgba(15,23,42,0.9)" }}
                  >
                    <span className="h-2.5 w-2.5 rounded-full bg-rose-400/80" />
                    <span className="h-2.5 w-2.5 rounded-full bg-amber-400/80" />
                    <span className="h-2.5 w-2.5 rounded-full bg-emerald-400/80" />
                    <span
                      className="ml-3 rounded px-2 py-0.5 text-[11px]"
                      style={{
                        color: "rgba(148,163,184,0.8)",
                        background: "rgba(255,255,255,0.05)",
                      }}
                    >
                      localhost:3000/knowledge-graph
                    </span>
                  </div>
                  <img
                    src="/images/knowledge-graph.png"
                    alt="知识图谱探索界面：302 个实体、192 条关系的实时力导向图"
                    className="block w-full"
                    loading="lazy"
                  />
                </div>
                {/* 浮动数据徽章 */}
                <div className="glass-card absolute -bottom-5 -left-4 flex items-center gap-2 px-4 py-2.5">
                  <ClusterOutlined style={{ color: "#22d3ee" }} />
                  <span className="text-xs font-medium" style={{ color: "#e2e8f0" }}>
                    302 实体 · 192 关系 · 实时力导向图
                  </span>
                </div>
              </div>

              {/* 能力速览玻璃卡 */}
              <div className="glass-card mt-8 p-6">
                <div className="flex items-center justify-between">
                  <span style={{ color: "#fff", fontWeight: 600 }}>平台已具备的核心能力</span>
                  <span className="flex gap-1.5">
                    <span className="h-2.5 w-2.5 rounded-full bg-rose-400/70" />
                    <span className="h-2.5 w-2.5 rounded-full bg-amber-400/70" />
                    <span className="h-2.5 w-2.5 rounded-full bg-emerald-400/70" />
                  </span>
                </div>
                <ul
                  className="mt-4 space-y-2.5 text-sm"
                  style={{ color: "rgba(226,232,240,0.85)" }}
                >
                  {HERO_POINTS.map((t) => (
                    <li key={t} className="flex gap-2.5">
                      <CheckCircleFilled className="mt-0.5 shrink-0" style={{ color: "#34d399" }} />
                      <span>{t}</span>
                    </li>
                  ))}
                </ul>
                <div
                  className="glass-note mt-5 rounded-xl p-3.5 text-xs"
                  style={{ color: "rgba(203,213,225,0.75)" }}
                >
                  当前实例：已入库 24 篇文献，图谱含 15 条引用关系，主文档年份覆盖 23/23。
                </div>
              </div>
            </div>
          </div>
        </div>
        <div className="hero-bottom-fade" />
      </section>

      {/* ============ 项目背景 ============ */}
      <section className="mx-auto max-w-6xl px-6 py-20">
        <div className="reveal">
          <span className="section-kicker">Why it matters</span>
          <Title level={2} style={{ marginTop: 12, fontWeight: 700 }}>
            为什么需要它
          </Title>
          <Paragraph className="text-slate-600">
            科研阅读与写作的效率瓶颈长期集中在三处，本平台按这三类需求组织能力。
          </Paragraph>
        </div>
        <div className="mt-10 grid gap-5 md:grid-cols-3">
          {PAINS.map((c, i) => (
            <div
              key={c.t}
              className="feature-card reveal"
              style={{ transitionDelay: `${i * 0.08}s` }}
            >
              <div className="text-base font-semibold text-slate-900">{c.t}</div>
              <p className="mt-2 text-sm leading-6 text-slate-600">{c.d}</p>
              <Tag className="mt-4" color="geekblue">
                {c.s}
              </Tag>
            </div>
          ))}
        </div>
      </section>

      {/* ============ 五大核心能力（深色段，与 Hero 呼应） ============ */}
      <section
        className="relative overflow-hidden py-20"
        style={{ background: "linear-gradient(180deg,#0b1230,#0e1738)" }}
      >
        <div className="mx-auto max-w-6xl px-6">
          <div className="reveal">
            <span className="section-kicker" style={{ color: "#a5b4fc" }}>
              Core Capabilities
            </span>
            <Title level={2} style={{ marginTop: 12, color: "#fff", fontWeight: 700 }}>
              五大核心能力
            </Title>
          </div>
          <div className="mm-wrap mt-12 reveal">
            {/* 中心枢纽 */}
            <div className="mm-hub">
              <ClusterOutlined className="hub-icon" />
              <div style={{ color: "#fff", fontWeight: 700, fontSize: 15 }}>AI 科研平台</div>
              <div
                style={{
                  color: "rgba(203,213,225,0.7)",
                  fontSize: 12,
                  marginTop: 6,
                  lineHeight: 1.6,
                }}
              >
                感知 · 推理
                <br />
                探索 · 洞察 · 产出
              </div>
            </div>
            {/* 五条能力分支（思维导图） */}
            <div className="mm-tree">
              {CAPABILITIES.map((c, i) => (
                <div
                  key={c.title}
                  className="mm-branch feature-card-dark reveal"
                  style={{ transitionDelay: `${i * 0.08}s` }}
                >
                  <div className="flex gap-4">
                    <span className="icon-tile shrink-0">{c.icon}</span>
                    <div>
                      <div style={{ color: "#fff", fontWeight: 600 }}>{c.title}</div>
                      <p
                        className="mt-1.5 text-sm leading-6"
                        style={{ color: "rgba(203,213,225,0.75)" }}
                      >
                        {c.desc}
                      </p>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>

      {/* ============ 六大模块 ============ */}
      <section className="mx-auto max-w-6xl px-6 py-20">
        <div className="reveal">
          <span className="section-kicker">Modules</span>
          <Title level={2} style={{ marginTop: 12, fontWeight: 700 }}>
            功能模块概览
          </Title>
          <Paragraph className="text-slate-600">
            平台按科研工作流划分为六个模块，覆盖从文献入库到写作产出的完整链路。
          </Paragraph>
        </div>
        <div className="module-flow mt-14 reveal">
          {MODULES.map((m, i) => (
            <Fragment key={m.name}>
              <div className="flow-node">
                <span className="step-num">0{i + 1}</span>
                <span className="flow-icon">{m.icon}</span>
                <div className="mt-3 text-sm font-semibold leading-snug text-slate-900">
                  {m.name}
                </div>
                <ul className="mt-2.5 space-y-1.5 text-xs text-slate-600">
                  {m.points.map((p) => (
                    <li key={p} className="flex gap-1.5">
                      <span style={{ color: "#6366f1" }}>•</span>
                      <span>{p}</span>
                    </li>
                  ))}
                </ul>
              </div>
              {i < MODULES.length - 1 && (
                <div className="flow-arrow">
                  <RightOutlined className="arrow-icon" />
                </div>
              )}
            </Fragment>
          ))}
        </div>
      </section>

      {/* ============ 适用场景 ============ */}
      <section className="bg-white py-20">
        <div className="mx-auto max-w-6xl px-6">
          <div className="reveal">
            <span className="section-kicker">Use Cases</span>
            <Title level={2} style={{ marginTop: 12, fontWeight: 700 }}>
              适用场景
            </Title>
          </div>
          <div className="mt-10 grid gap-5 md:grid-cols-2">
            {SCENARIOS.map((s, i) => (
              <div
                key={s.title}
                className="feature-card reveal"
                style={{ transitionDelay: `${i * 0.08}s` }}
              >
                <div className="flex items-center gap-2.5 font-semibold text-slate-900">
                  <span className="icon-tile" style={{ width: 36, height: 36, fontSize: 16 }}>
                    <span style={{ color: "#4f46e5" }}>{s.icon}</span>
                  </span>
                  {s.title}
                </div>
                <p className="mt-2.5 text-sm leading-6 text-slate-600">{s.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ============ 技术栈（深色紧凑条） ============ */}
      <section className="py-16" style={{ background: "#070b1a" }}>
        <div className="mx-auto max-w-6xl px-6">
          <div className="reveal">
            <span className="section-kicker" style={{ color: "#a5b4fc" }}>
              Tech Stack
            </span>
            <Title level={2} style={{ marginTop: 12, color: "#fff", fontWeight: 700 }}>
              技术栈
            </Title>
          </div>
          <div className="mt-6 flex flex-wrap gap-2.5">
            {STACK.map((s) => (
              <span key={s} className="tech-tag">
                {s}
              </span>
            ))}
          </div>
        </div>
      </section>

      {/* ============ 底部引导 CTA ============ */}
      <section
        className="relative overflow-hidden py-20"
        style={{ background: "linear-gradient(135deg,#4338ca 0%,#7c3aed 50%,#0e7490 100%)" }}
      >
        <div
          className="pointer-events-none absolute -left-20 -top-20 h-64 w-64 rounded-full"
          style={{ background: "radial-gradient(circle, rgba(255,255,255,0.18), transparent 70%)" }}
        />
        <div
          className="pointer-events-none absolute -bottom-24 -right-16 h-72 w-72 rounded-full"
          style={{ background: "radial-gradient(circle, rgba(255,255,255,0.14), transparent 70%)" }}
        />
        <div className="relative mx-auto max-w-3xl px-6 text-center">
          <Title level={2} style={{ color: "#fff", fontWeight: 700 }}>
            开始使用文献智能解析平台
          </Title>
          <Paragraph style={{ color: "rgba(255,255,255,0.85)" }}>
            登录后即可上传文献、构建引用图谱并发起可溯源的问答。
          </Paragraph>
          <Button
            size="large"
            onClick={() => navigate("/login")}
            data-testid="footer-login"
            style={{
              background: "#fff",
              color: "#4338ca",
              border: "none",
              fontWeight: 600,
              height: 48,
              padding: "0 30px",
              boxShadow: "0 16px 40px -12px rgba(0,0,0,0.45)",
            }}
          >
            前往登录页 <ArrowRightOutlined />
          </Button>
        </div>
      </section>

      <footer className="bg-slate-950 py-6 text-center text-xs text-slate-500">
        多模态科学文献智能解析与知识图谱构建平台 · 登录入口 {"/login"}
      </footer>
    </div>
  );
}
