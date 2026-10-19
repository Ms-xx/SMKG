# SMKG — 多模态科学文献智能解析与知识图谱构建平台

面向科学文献的多模态智能解析与知识图谱构建平台，实现 PDF 文献“上传 → 多模态解析（文本/公式/图表/版面）→ 深度信息抽取（RAG + LLM + NER）→ 人机协同标注 → 知识图谱构建 → 智能问答/语义搜索”的完整闭环。

> 当前状态：后端 694 项单测通过、前端 228 项单测 + 3 项 E2E 通过；`main` 分支为稳定开发主线。
>
> **四个创新点（A/B/C/D）已全部完成并本机实测**：A 实体级图谱落地（英文 NER 兜底）、B 图谱增强检索 + grounding_score、C 主动学习闭环、D 多智能体图谱融合，详见下方[核心创新](#核心创新)与 `others/Document/XiangMu.md`。

## 部署模式

> **本项目当前唯一官方支持的部署模式为「本地部署」**（单机 / 本地服务器 / 本地计算环境）。
> 所有标准使用场景均在本地完成；**云端部署仅为代码层预留的扩展接口，不纳入官方支持范围**。
> 完整部署步骤、操作指引与验证流程见 [DEPLOYMENT.md](DEPLOYMENT.md)。

## 目录

- [项目简介](#项目简介)
- [功能特性](#功能特性)
- [核心能力](#核心能力)
- [核心创新](#核心创新)
- [文档与状态](#文档与状态)
- [技术栈](#技术栈)
- [目录结构](#目录结构)
- [安装步骤](#安装步骤)
- [配置说明](#配置说明)
- [启动服务](#启动服务)
- [使用方法](#使用方法)
- [API 文档](#api-文档)
- [运行测试](#运行测试)
- [代码质量](#代码质量)
- [部署模式](#部署模式)
- [部署](#部署)
- [常见问题](#常见问题)
- [贡献指南](#贡献指南)
- [许可证](#许可证)

## 项目简介

平台围绕科研工作流组织能力，覆盖从**原始 PDF** 到**可问答的知识图谱**的完整链路：

1. **解析**：PDF 文本抽取、版面分析、公式识别、图表检测与描述、扫描件 OCR；
2. **抽取**：实体/关系抽取、实体链接，结合 RAG 与本地 LLM 做深度理解；
3. **协同**：人机协同标注与审核、一致性评估、主动学习采样；
4. **图谱**：Neo4j 图谱构建、引用网络挖掘、关系推理与语义搜索；
5. **应用**：图谱问答、论文检索与追踪推荐、写作辅助与数据可视化。

设计上强调**可插拔与可降级**：OCR、版面分析、公式识别、LLM 等能力在模型或依赖缺失时自动降级为规则/纯 Python 实现，不阻断主流程。

## 功能特性

| 模块 | 具体特性 |
| --- | --- |
| 文献管理 | PDF 单篇/批量上传、列表与详情、解析状态跟踪、源文件下载、JATS 导出 |
| 多模态解析 | 文本抽取、标题树抽取、表格/图表检测与描述、公式识别并统一以 LaTeX 输出、扫描件 OCR |
| 语义去重 | SimHash 正文指纹比对、arXiv 版本号识别（如 v1/v7）、给出“保留最新版本”建议 |
| 信息抽取 | NER 实体识别、关系抽取、实体链接、作者与机构结构化 |
| 抗幻觉问答 | 答案附原文出处锚点与页码、跨文献对比推理、Text-to-Cypher |
| 知识图谱 | Neo4j 图谱构建与查询、引用网络建图、PageRank 基石节点挖掘、自动综述、趋势分析与异常检测 |
| 人机协同标注 | 标注/审核工作流、版本管理、Fleiss' Kappa 一致性评估、主动学习采样、实时协作（WebSocket） |
| 检索追踪推荐 | 论文下钻入库、arXiv 定期追踪、相关性推荐、A/B 测试分流 |
| 写作辅助 | 论文框架生成、TikZ/Graphviz/Mermaid/Matplotlib 拓扑图、CSV 图表与图注、学术翻译 |
| 运维治理 | 权限与审计、监控告警、置信度校准与漂移检测、模型/数据版本管理 |

## 核心能力

| 模块 | 说明 |
| --- | --- |
| 多模态解析 | PDF 文本提取、版面分析（LayoutLMv3）、公式识别（LaTeX-OCR/pix2tex）、图表检测（YOLOv8）、图表描述（BLIP-2）、OCR（PaddleOCR） |
| 信息抽取 | NER 实体识别（SciBERT）、关系抽取（REBEL）、实体链接（Wikidata/DBpedia） |
| 深度增强 | GraphRAG 检索增强 + LLM 问答、混合检索（向量 + BM25）、Text-to-Cypher |
| 人机协同标注 | 标注/审核工作流、版本管理、Fleiss' Kappa 一致性评估、主动学习采样 |
| 知识图谱 | Neo4j 图谱构建与查询、关系推理与链路预测（TransE）、语义搜索 |
| 运维治理 | 权限与审计、监控告警（Prometheus/Grafana/Alertmanager + ELK）、置信度校准与漂移检测、模型/数据版本管理 |

## 核心创新

> 四个创新点为平台在知识图谱/主动学习/检索增强方向的最新研究性成果，**均已本机真实校验完成**，全部遵循**可插拔 + 可降级**约定（模型/图/LLM 缺失时不阻断主流程）。源码位于 `backend/` 与 `GraphRAGTest/`，测试在 `test/`，实测产物在 `outputs/`。

| 创新点 | 能力 | 落点与校验 |
| --- | --- | --- |
| **A 实体级图谱落地** | 英文科学文献实体/关系非 0 并写入图谱（确定性英文 NER 兜底，ML 可用时优先） | `backend/app/services/ner_service.py` → `extract_english_gazetteer`（材料/方法/指标/任务/科学术语）；产物 `outputs/innovA_ner_e2e.json`（22 唯一实体入 Neo4j）、`outputs/innovA_abstract_e2e.json`（真实论文 10 个非 0 实体） |
| **B 图谱增强检索 + grounding_score** | 图谱邻居扩跳重排序 + 答案支撑度量化（0~1） | `GraphRAGTest/{neo4j_client,graphrag_service}.py` → `get_connection_strength` 连接强度加权重排、`compute_grounding_score`（grounded 1.0 / 无关 0.0）；产物 `outputs/innovB_{focus_internal,e2e_service}.json` |
| **C 主动学习闭环** | 从静态不确定性采样升级为「标注→训练→留出集评估→软概率驱动下一轮采样」的飞轮 | `backend/app/services/active_learning_loop.py` + `POST /active-learning/cycle`；飞轮验证：标注后目标样本熵 0.9963→0.9553；产物 `outputs/innovC_active_learning_loop.json` |
| **D 多智能体图谱融合** | 多 agent 抽取→冲突消解→实体/关系写回 Neo4j 完整闭环 | `backend/app/services/multi_agent_service.py` → `fuse_to_graph`（经 `GraphRAGIntegration.index_document` 写回，`graph_fusion` 字段透出）；实测 `/graph/stats` 核对 HAS_ENTITY 3 / CO_OCCURS 1；产物 `outputs/innovD_multi_agent_graph_fusion.json` |

> 说明：四创新点均已完成两轮代码复审（修复 A 化学式正则误报/span 错位、C 无特征降级误判、D 断言真实化，详见 `others/Document/XiangMu.md` 11.6 节）；grounding 与抽取为确定性（CPU 可跑），语义级扩展与真实 LoRA 精读路径已预留接口。

## 文档与状态

项目规划的**执行顺序、验收标准与逐步骤完成/阻塞状态**以 `others/` 下的文档为权威依据：

| 文档 | 说明 |
| --- | --- |
| [`XiangMu.md`](others/Document/XiangMu.md) | 纵向主文档：完整实施步骤、每步状态判定、变更记录（当前 v8.0，含「十二、后续未完成步骤详细清单」） |
| [`00-差别分析.md`](others/Document/00-差别分析.md) | 状态对照 + 更新记录表，与 XiangMu 的待办总览保持口径一致 |
| [`PROJECT_SUMMARY.md`](others/Document/PROJECT_SUMMARY.md) | 已完成能力全貌与创新点注记总览 |
| [`08-需求与能力对照.md`](others/Document/08-需求与能力对照.md) | 需求原文归档与逐条现状判定 |
| `others/PROJECT/`（01–07） | 数据库 / 后端 / 前端 / 开发流程 / API 接口 / 环境 / GraphRAGTest 设计文档 |

最大程度采用官方 `git ignore` 保护：`config/*.env`、`moulds/`、`outputs/`、`database/`、`timeout/` 均不入库；`others/` 为项目文档，按需同步。

## 技术栈

- **后端**：FastAPI · SQLAlchemy 2.0（async）· Pydantic v2 · Celery · WebSocket
- **存储**：MySQL 8.0 · Redis · Neo4j 5 · MinIO
- **前端**：React 18 · TypeScript · Vite · Ant Design · Zustand · Vitest（pnpm 管理）
- **检索与检索增强**：GraphRAG · BGE-M3 · bge-reranker · LM Studio（本地 LLM）
- **工程化**：Ruff · Black · ESLint · Prettier · pytest · Vitest · Playwright · GitHub Actions

## 目录结构

```
LX/
├── backend/            # FastAPI 后端服务
├── frontend/           # React 前端
├── GraphRAGTest/       # GraphRAG 检索增强与问答服务
├── config/             # 集中化配置（真实值不入库，仅提交 *.env.example 模板）
├── monitoring/         # Prometheus / Alertmanager / Grafana / ELK 配置
├── deploy/k8s/         # Kubernetes 部署清单
├── test/               # 后端测试用例与端到端驱动脚本（如 step18_parsing_e2e.py、innovA/B/C/D_*.py）
├── outputs/            # 实测产物（JSON 报告，不入库）
├── others/             # 项目文档（规划、状态对照、设计文档），见 [文档与状态](#文档与状态)
├── moulds/             # 本地模型目录（不入库，每个模型一个子目录）
├── database/           # 本地数据库文件（不入库）
├── timeout/            # 本地超时/临时文件（不入库）
├── DEPLOYMENT.md                 # 本地部署唯一官方支持指南（部署 / 操作 / 验证）
├── docker-compose.yml            # 主服务编排
├── docker-compose.monitoring.yml # 监控栈编排
├── start_all.ps1                 # 一键启动（Windows）
└── .github/workflows/  # CI（lint / format / test / docker build）
```

## 安装步骤

### 1. 环境要求

- Python 3.11+
- Node.js 22+（前端，使用 pnpm）
- MySQL 8.0、Redis、Neo4j 5、MinIO（本地运行）
- LM Studio（本地 LLM，默认 `http://127.0.0.1:1234`，用于 RAG 问答与翻译）

### 2. 后端依赖

```bash
cd backend
pip install -r requirements.txt
```

### 3. 前端依赖

```bash
cd frontend
pnpm install
```

### 4. 初始化数据库

```bash
cd backend
python scripts/init_db.py
```

脚本会建表并写入初始角色、管理员账号与系统配置（管理员账号与口令来自 `config/backend.env`）。

## 配置说明

所有敏感配置统一集中在 [`config/`](config/README.md) 目录，**代码中不硬编码任何密钥**。首次初始化：

```bash
cp config/common.env.example    config/common.env
cp config/backend.env.example   config/backend.env
cp config/graphrag.env.example  config/graphrag.env
```

| 文件 | 用途 | 是否入库 |
| --- | --- | --- |
| `config/common.env` | 跨服务共享凭据：Neo4j 连接 | 否 |
| `config/backend.env` | 后端配置：MySQL / Redis / MinIO / JWT / Celery / LLM / 管理员账号 | 否 |
| `config/graphrag.env` | GraphRAGTest 子服务配置 | 否 |
| `config/*.env.example` | 上述文件的占位模板 | 是 |

关键配置项（其余见模板文件）：

| 配置项 | 说明 |
| --- | --- |
| `DATABASE_URL` | MySQL 连接串，形如 `mysql+aiomysql://<用户>:<口令>@127.0.0.1:3306/<库名>` |
| `REDIS_URL` | Redis 连接串（Celery Broker/结果后端另配） |
| `NEO4J_URI` / `NEO4J_USER` / `NEO4J_PASSWORD` | 图数据库连接，后端与 GraphRAGTest 共用 |
| `MINIO_ENDPOINT` / `MINIO_ACCESS_KEY` / `MINIO_SECRET_KEY` | 对象存储凭据 |
| `JWT_SECRET_KEY` | JWT 签名密钥，生产环境务必替换为随机强密钥 |
| `ADMIN_USERNAME` / `ADMIN_PASSWORD` | 初始化管理员账号，仅本地开发默认值 |
| `LLM_ENDPOINT` / `LLM_MODEL` | 本地 LLM 服务地址与模型 |

> 真实文件由 `.gitignore` 的 `config/*.env` 规则排除，不会进入版本库。前端（Vite）的 `frontend/.env.*` 仅存放非敏感项（如 API 基址），由 Vite 构建期内联，故仍保留在 `frontend/` 目录内。

## 启动服务

### 方式一：一键启动（Windows）

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\start_all.ps1
```

或双击 `启动全部服务.cmd`。脚本会拉起依赖检查、后端、Celery Worker/Beat、GraphRAGTest 与前端，每个服务独立窗口运行。

### 方式二：分步启动

```bash
# 1) 后端
cd backend
uvicorn app.main:app --reload --port 8000

# 2) Celery Worker（另开终端）
cd backend
celery -A app.core.celery_app worker -l info -Q parsing,extraction,graph,training

# 3) Celery Beat（另开终端，定时任务）
cd backend
celery -A app.core.celery_app beat -l info

# 4) GraphRAGTest 子服务（另开终端）
cd GraphRAGTest
python app.py

# 5) 前端
cd frontend
pnpm dev
```

### 访问地址

| 服务 | 地址 | 说明 |
| --- | --- | --- |
| 前端 | http://localhost:3000 | 主界面 |
| 后端健康检查 | http://localhost:8000/health | 返回 `{"status":"healthy",...}` |
| 后端 API 文档 | http://localhost:8000/docs | Swagger UI |
| GraphRAGTest | http://localhost:8001/docs | 检索增强服务 |
| MinIO 控制台 | http://localhost:9001 | 对象存储管理 |

默认管理员账号见 `config/backend.env` 中的 `ADMIN_USERNAME` / `ADMIN_PASSWORD`。

## 使用方法

典型端到端流程：

1. **上传文献**：进入「文档管理 → 上传」，选择 PDF；上传后自动创建文档并触发解析任务。
2. **查看解析结果**：在文档详情查看正文、标题树、图表、**公式（统一以 LaTeX 渲染，可一键复制）**，以及抽取出的实体/关系。
3. **解析状态**：解析由 Celery 异步执行，状态流转 `uploaded → parsing → parsed`；失败会在任务列表记录原因。
4. **构建与查看图谱**：解析完成后实体与关系写入 Neo4j；在「知识图谱」中查看图谱、引用网络与基石节点。
5. **智能问答**：在「知识图谱 → 问答对话」提问，答案附出处锚点；也可使用「多智能体」模式进行对比推理。
6. **协同标注**：进入文档的标注工作台，进行标注、提交审核、查看版本与一致性评估；多人协作状态通过 WebSocket 实时同步。
7. **检索与推荐**：在「论文检索」按关键词或参考文献下钻入库，并配置 arXiv 追踪任务。
8. **写作辅助**：生成论文框架、拓扑图脚本（TikZ/Graphviz/Mermaid/Matplotlib）、CSV 图表与图注，或进行学术翻译。

命令行侧也提供了端到端驱动脚本，例如 `test/step18_parsing_e2e.py`（多模态解析验证）、`test/corpus_expand.py`（真实 arXiv 语料扩充入库）。

## API 文档

- 在线文档（启动后端后访问）：http://localhost:8000/docs
- OpenAPI 描述：http://localhost:8000/openapi.json
- 接口前缀统一为 `/api/v1`

主要接口分组（27 个路由模块）：

| 分组 | 典型路径 | 说明 |
| --- | --- | --- |
| 认证与用户 | `/auth`、`/users`、`/permissions` | 登录、刷新令牌、用户与权限 |
| 文档 | `/documents` | 上传、列表、详情、解析、源文件、JATS 导出 |
| 标注 | `/annotations`、`/comments`、`/tasks` | 标注工作流、评论、任务 |
| 知识图谱 | `/knowledge-graph`、`/graph-insights`、`/citation-graph` | 图谱查询、趋势与异常、引用网络与综述 |
| 检索增强 | `/source-anchor`、`/multi-agent`、`/paper-retrieval` | 溯源锚点、多智能体、论文检索 |
| 主动学习 | `/active-learning`、`/ab-test`、`/models` | 采样、A/B 测试、模型管理 |
| 运维治理 | `/statistics`、`/operation-logs`、`/alerts`、`/system`、`/version-management`、`/calibration-drift` | 统计、审计、告警、版本与漂移 |
| 工具与实时 | `/writing-assistant`、`/deduplication`、`/citation-link`、`/notifications`、`/ws` | 写作辅助、去重、引用跳转、通知、WebSocket |

认证方式：先登录获取令牌，再以 Bearer 方式调用。

```bash
# 登录
TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"<用户名>","password":"<口令>"}' | jq -r .access_token)

# 调用受保护接口
curl -s http://localhost:8000/api/v1/documents/?page_size=1 \
  -H "Authorization: Bearer $TOKEN"
```

更详细的接口字段说明见 `frontend/API_INTERFACE_CONFIG.md`。

## 运行测试

```bash
# 后端（pytest.ini 已配置 testpaths=test）
python -m pytest -q

# 前端单测
cd frontend
pnpm test

# 前端端到端（Playwright，会自动拉起 5173 端口的开发服务）
cd frontend
pnpm test:e2e
```

后端测试使用 SQLite 临时库，不污染真实 MySQL；依赖异步组件缺失时相关用例自动跳过。

## 代码质量

| 范围 | 工具 | 常用命令 |
| --- | --- | --- |
| 后端 | Ruff · Black | `ruff check .`、`black --check app scripts` |
| 前端 | ESLint · Prettier · TypeScript | `pnpm lint`、`pnpm format`、`pnpm type-check` |

CI（`.github/workflows/ci.yml`）包含 4 个 job：`backend`（ruff/black/pytest）、`frontend`（eslint/prettier/tsc/vitest）、`docker`（镜像构建）、`deploy`（默认 `if: false`；云上部署非官方支持）。

## 部署

> **本项目的唯一官方支持部署模式为本地部署**；云端部署不属于官方支持范围。

### 本地部署（唯一官方支持模式）

- **一键启动（推荐）**：Windows 下运行 `start_all.ps1`，自动完成依赖检查、MinIO、后端、Celery Worker/Beat、GraphRAGTest 与前端拉起与健康检查。
- **分步启动**：见上方[启动服务](#启动服务)。
- **容器化本地编排（可选）**：`docker-compose.yml` 编排主服务依赖；`docker-compose.monitoring.yml` 编排监控栈（需本地容器运行时）。
- **完整部署步骤、操作指引与验证流程**：见 [DEPLOYMENT.md](DEPLOYMENT.md)。

### 云上扩展点（非官方支持）

- `deploy/k8s/` 提供 namespace、configmap、secret 与各服务清单；
- `.github/workflows/ci.yml` 的 `deploy` job 默认 `if: false`（含镜像打标推送与占位部署步骤）。

以上仅为**代码层扩展预留**，允许使用者自行调整配置切换云端，但**不纳入官方支持范围**；
云端部署需自行把连接串、CORS、对象存储与 LLM 端点等改为外部地址。

生产环境的密钥不应写入仓库，请通过编排平台的 Secret 或 CI/CD 变量注入（对应 `config/*.env.example` 中的各项）。

## 常见问题

- **后端读不到配置**：配置已改为从 `config/` 按绝对路径加载，不再依赖启动目录；若报配置缺失，请确认 `config/*.env` 已由模板复制生成。
- **前端依赖预构建报错（`504 Outdated Optimize Dep`）**：通常是缓存失效所致，删除 `frontend/node_modules/.vite` 后重启开发服务；新增按需引入的重依赖请一并登记到 `vite.config.ts` 的 `optimizeDeps.include`。
- **LLM 相关接口超时**：本地 CPU 推理较慢（约 7 token/s），前端对 LLM 类接口已统一放宽超时；如仍超时，可调小 `LLM_MAX_TOKENS` 或改用 GPU。
- **WebSocket 连接告警**：开发模式下 React StrictMode 会双挂载，`ws://` 连接会出现一次“连接未建立即关闭”的提示，属预期现象；生产构建不会出现。
- **MinIO 源文件 404**：说明该文档的原始对象已丢失（`documents.file_path` 与存储不一致），需重新上传源文件。

## 贡献指南

1. **分支与提交**：从 `main` 切分支开发，提交信息使用约定式前缀，如 `feat:`、`fix:`、`chore:`、`docs:`、`refactor:`、`test:`。
2. **敏感配置**：任何口令、密钥、Token 只允许写入 `config/*.env`，并在同名 `*.env.example` 中以占位值登记；真实值严禁提交。
3. **提交前自检**：
   - 后端：`python -m pytest -q`、`ruff check .`、`black --check app scripts`
   - 前端：`pnpm type-check`、`pnpm lint`、`pnpm test`
4. **变更说明**：涉及行为变更、新增能力或缺陷修复时，同步更新相关文档（本项目内部规划与状态记录位于 `others/`，该目录不推送远端）。

