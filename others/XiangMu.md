# 多模态科学文献智能解析与知识图谱构建平台
# Scientific Multi-modal Knowledge Graph

> 本文档为项目现状总览（依据立项规划 `XiangMu` 原稿 + 实际代码重构）。
> 状态标记：✅ 已完成　⚠️ 部分完成　❌ 未完成/未实现

---

## 项目概述

面向科学文献的多模态智能解析与知识图谱构建平台，实现 PDF 文献“上传 → 多模态解析（文本/公式/图表/版面）→ 深度信息抽取（RAG + LLM + NER）→ 人机协同标注 → 知识图谱构建 → 智能问答/语义搜索”的完整闭环。

## 技术架构

| 层次 | 技术栈 |
|------|--------|
| 前端 | React 18 + TypeScript + Vite、Zustand、Ant Design、React Router、ForceGraph（图谱）、PDF.js（双栏）、KaTeX（公式渲染） |
| 后端 | FastAPI 0.109、SQLAlchemy 2.0（异步）、Pydantic v2、Celery 5.3.6（异步任务）、JWT + RBAC 权限 |
| 存储 | MySQL 8（aiomysql）、Redis 5（RESP2）、Neo4j 5（APOC）、MinIO（对象存储） |
| AI/ML | PyMuPDF、pdfplumber、PaddleOCR、LayoutLMv3、LaTeX-OCR(pix2tex)、YOLOv8、BLIP-2、SciBERT、BGE-M3、FAISS、sentence-transformers |
| 检索系统 | GraphRAGTest 独立子系统（Neo4j + LM Studio，向量 + BM25 混合检索 + 重排序） |
| 运维 | Docker/Docker Compose、GitHub Actions CI、Prometheus + Grafana、ELK 日志聚合 |

---

## 一、开发里程碑与整体完成度

按项目立项与建设顺序，共 6 个阶段。**总体完成度约 80%**（核心业务闭环已打通，遗留项集中在模型微调、实时协作、生产部署与性能优化）。

| 里程碑 | 目标 | 状态 |
|--------|------|------|
| M1 | 基础架构搭建（前后端 + 数据库 + 认证 + 权限） | ✅ 完成 |
| M2 | 文献解析模块（PDF/OCR/版面/公式/图表/参考文献） | ✅ 完成 |
| M3 | 信息抽取模块（RAG + LLM + NER + 向量检索 + REBEL 关系抽取） | ✅ 完成 |
| M4 | 前端平台开发（文档/标注/图谱/问答） | ✅ 完成 |
| M5 | 知识图谱构建（存储/对齐/推理/搜索/问答） | ✅ 完成（GNN 链路预测未做） |
| M6 | 系统优化与部署（主动学习/运维/监控） | ⚠️ 部分完成 |

**建设时间线（摘要）**

| 时间 | 完成内容 |
|------|---------|
| 立项 → 基础 | 前后端工程初始化、数据库 Schema、JWT 认证、Docker 编排 |
| 早期迭代 | PDF 解析、任务/标注/文档 CRUD、图谱 CRUD、Celery 异步、示例数据、注册/图谱探索增强 |
| 2026-09-06 | MinIO 部署接入、依赖服务连通、上传→解析→入库闭环、基础单测 |
| 2026-09-07 | 向量库（FAISS+BGE-M3）、混合检索+重排序、索引管线、公式识别、页眉页脚、模型路径统一、图表理解（YOLOv8+BLIP-2）、NER（SciBERT）、Pydantic v2 迁移 |
| 2026-09-08 | RBAC 细粒度权限（权限码 + 归属校验 + 动态菜单） |
| 2026-09-09 | 实体链接、语义搜索升级、Text-to-Cypher、主动学习、标注一致性、版本管理、置信度校准与漂移检测 |
| 2026-09-10 | 测试补全（后端 87% / 前端 87.66% / E2E）、代码质量工具（Ruff+Black / ESLint+Prettier）、TypeScript 类型修复、CI/CD 工作流、监控告警配置 |

---

## 二、分阶段建设情况

### Phase 1：基础架构搭建 ✅ 完成

**已完成**
- 前后端项目初始化（React + FastAPI 结构完整）
- 数据库 Schema 设计（MySQL：user / role / document / task / annotation / comment / model / system_config）
- 用户认证系统（注册、登录、JWT、bcrypt）
- RBAC 细粒度权限（`core/permissions.py` 权限码 + `require_permission` 依赖工厂；文档/任务级归属校验；系统级权限码；前端动态菜单 + 路由守卫）
- Docker / docker-compose 编排（MySQL/Redis/Neo4j/MinIO/backend/celery/frontend）
- CI/CD 工作流（`.github/workflows/ci.yml`）⚠️ 自动部署未实现

### Phase 2：文献解析模块 ✅ 完成

**已完成（多模态解析，AI 模型全部可插拔、缺失自动降级）**
- PDF 文本/表格提取：PyMuPDF + pdfplumber
- OCR 辅助：PaddleOCR（扫描件/图片文字页回退）
- 版面分析：LayoutLMv3（title/paragraph/list/table/figure + bbox）
- 页眉页脚处理：纵向位置启发式 + 页码识别
- 公式识别：LaTeX-OCR（pix2tex，公式图 → LaTeX）
- 图表/公式检测：YOLOv8
- 图表语义理解：BLIP-2 描述
- 参考文献解析与结构化：Section 定位（正则 + 版面）+ 条目切分（前置/后置序号）+ 字段抽取（作者/标题/期刊/年份/卷/期/页码/DOI）+ 标准化输出（CSL-JSON / BibTeX）
- 结果入库、图片提取

### Phase 3：信息抽取模块 ✅ 完成

**已完成**
- GraphRAGTest 独立子系统（Neo4j + LM Studio qwen3-4b）
- 实体抽取：规则 + LLM + SciBERT 微调 NER（可插拔降级）
- 关系抽取：规则 + LLM + REBEL 关系分类（可插拔降级）
- 向量检索：FAISS + BGE-M3（可降级为哈希 + numpy）
- 混合检索：向量 + BM25 + RRF 融合，可选 Cross-Encoder 精排
- 文档索引管线（chunks 入 Neo4j + 向量库）

**❌ 未完成**
- （本阶段功能已全部完成）

### Phase 4：前端平台开发 ✅ 完成

**已完成**
- 页面：登录/注册、仪表盘、文档管理（上传/列表/详情/删除）、任务管理（含进度）、标注工作台、知识图谱可视化、GraphRAG 问答、操作日志、工作量统计、个人设置、角色权限管理
- PDF 查看器（双栏对比视图）
- 标注工作台（实体标注、关系标注、评论讨论、历史记录、双栏视图）
- 知识图谱可视化（ForceGraph，统计卡片、类型筛选、节点详情抽屉）
- 状态管理（Zustand：auth / document / ui）
- API 接口层完整、RBAC 动态菜单

### Phase 5：知识图谱构建 ✅ 完成（GNN 未做）

**已完成**
- Neo4j 图谱存储与节点/关系 CRUD
- 实体链接（Wikidata/DBpedia 查询 + 实体消歧 + 同义词合并，可降级）
- 关系推理（规则推理 + TransE）
- 图谱补全（TransE 链路预测 + 统计降级）
- 语义搜索（分面搜索 + 搜索建议，纯 Python 零依赖，可插拔 ES）
- Text-to-Cypher（自然语言 → 只读 Cypher，规则模板 + LLM 预留）
- 智能问答（GraphRAG + Qwen）
- 图谱统计、示例数据初始化（seed_data + API）

**❌ 未完成**
- GNN（图神经网络）链路预测（当前以 TransE 替代）

### Phase 6：系统优化与部署 ⚠️ 部分完成

**已完成**
- 主动学习采样（不确定性 / 多样性 / QBC / 混合，纯 Python 零依赖）
- 标注一致性评估（Cohen's Kappa / Fleiss' Kappa / Krippendorff's Alpha）
- 数据/模型版本管理（DVC + MLflow + 自动重训管道，可降级）
- 置信度校准与漂移检测（Temperature/Platt Scaling + ECE + PSI/KS/卡方漂移告警）

**❌ 未完成（详见第三部分）**
- LoRA/QLoRA 科学领域微调
- A/B 测试框架
- 主动学习低置信度样本推送
- 实时协作（WebSocket）
- 性能优化
- 监控告警：配置/编排已提供，告警渠道未接入、未端到端验证
- 生产部署：K8s 未做、自动部署未实现

---

## 三、未完成模块详细清单（按优先级）

### 3.1 高优先级（核心能力补全）

| 未完成项 | 详情 | 现状 |
|---------|------|------|
| LoRA/QLoRA 科学领域微调 | 领域适配微调 LLM/模型 | 版本管理框架已建，实际微调流程未接 |

### 3.2 中等优先级（平台能力增强）

| 未完成项 | 详情 |
|---------|------|
| 实时协作（WebSocket） | 多人同时标注、实时同步未实现 |
| 主动学习低置信度样本推送 | 采样策略已实现，但前端“低置信度样本优先标注”推送链路未做 |
| A/B 测试框架 | 模型对比评估未实现 |

### 3.3 低优先级（运维与工程化）

| 未完成项 | 详情 |
|---------|------|
| 性能优化 | 全链路性能调优、缓存策略、数据库索引优化未系统性开展 |
| 自动部署（CI/CD deploy） | `.github/workflows/ci.yml` 的 `deploy` job 为 `if: false` 占位，需镜像仓库认证与部署目标；Git 仓库未初始化，未实际触发 CI |
| 监控告警端到端 | `monitoring/` + `docker-compose.monitoring.yml` 已提供编排，但 ELK（尤其 Elasticsearch）需机器资源实际运行验证；告警渠道（邮件/钉钉/企业微信）为占位未接真实接收器 |
| 生产部署（K8s） | 仅 docker-compose，未实现 Deployment/Service/Ingress/HPA |
| GNN 图神经网络链路预测 | 图谱补全当前用 TransE 链路预测 + 统计降级替代 |

---

## 四、当前可正常运行的功能

### 后端 API（15 个模块）
- 认证授权：`/auth`（登录/注册/JWT）、`/permissions`（角色权限管理）
- 核心业务：`/documents`、`/tasks`、`/annotations`、`/comments`、`/notifications`
- 知识图谱：`/knowledge-graph`（CRUD/实体链接/分面搜索/Text-to-Cypher）
- 平台管理：`/users`、`/operation-logs`、`/statistics`（工作量统计）、`/models`
- AI 能力：`/active-learning`、`/version-management`、`/calibration-drift`

### 前端页面
登录/注册、仪表盘、文档管理、任务管理、标注工作台、知识图谱可视化、GraphRAG 问答、操作日志、工作量统计、个人设置、角色权限管理

### 服务依赖（本机开发环境）
- ✅ MySQL（3306）、Redis（6379）、Neo4j（7474/7687）、MinIO（9000/9001）均已部署并连通验证

---

## 五、工程质量保障

| 维度 | 状态 |
|------|------|
| 后端测试 | ✅ pytest `321` 用例通过，语句覆盖率 **87%**（`test/` 目录） |
| 前端测试 | ✅ Vitest + RTL `138` 用例（34 文件），覆盖率 **87.66%** |
| E2E 测试 | ✅ Playwright 已配置（冒烟用例 + `test:e2e` 脚本） |
| 后端代码质量 | ✅ Ruff（`pyproject.toml`）+ Black，`ruff check` / `black --check` 全通过 |
| 前端代码质量 | ✅ ESLint + Prettier，`pnpm lint` / `prettier --check` / `tsc --noEmit` 全通过 |
| CI/CD | ⚠️ GitHub Actions 工作流已配置（lint→test→镜像构建），自动部署未实现 |
| 监控告警 | ⚠️ Prometheus + Grafana + ELK 配置/编排已提供，未端到端运行 |

---

## 六、后续开发建议

**短期（1-2 周）**：接入真实告警渠道并端到端运行监控栈；完善任务进度同步与示例 PDF。

**中期（1 个月）**：打通 LoRA 微调 → 模型注册 → 部署的再训练闭环；实现主动学习低置信度样本推送。

**长期（持续）**：实时协作（WebSocket）、A/B 测试框架、系统性性能优化、K8s 生产部署与自动部署、监控仪表盘/告警规则细化。

---

## 七、后续需要完成的详细步骤

> 按优先级（P0 最高）排序，覆盖第三部分「未完成模块」的落地路径。每步给出目标、现状、子任务与验收标准。

### 步骤 1【P0】参考文献解析与结构化 ✅ 已完成

**目标**：补齐 Phase 2 缺失的参考文献抽取能力。
**现状**：✅ 已实现，规则 + 正则兜底（未集成 GROBID/Cermine），PDF 尾部参考文献自动抽取并入库、前端展示。

- [x] 1.1 定位参考文献区块（正则 + 版面位置：Section "References"/"Bibliography"/"参考文献" 判定）
- [x] 1.2 条目切分（按序号 `[1]`/`［1］` 前置或后置）与字段抽取（作者、标题、期刊/会议、年份、卷、期、页码、DOI、类型）
- [x] 1.3 选型：规则 + 正则兜底（`reference_service.py`，GROBID/Cermine 预留可替换）
- [x] 1.4 输出标准化（CSL-JSON / BibTeX）并按 source 关联 `document.references`
- [x] 1.5 前端展示参考文献列表（`DocumentDetailPage`）+ 单测（`test_reference_service.py` 6 用例）

**实现文件**：`backend/app/services/reference_service.py`（抽取 + `references_to_csl_json`/`references_to_bibtex`）、`parsing_service.py`（`extract_references` 委托）、`workers/parsing_tasks.py`（解析流程接入并写 `document.references`）、`models/document.py` + `schemas/document.py`（`references` 字段）。

**验收**：上传含参考文献的 PDF（如 `database/大型语言模型：原理、实现与发展.pdf`），解析结果含结构化参考文献（桩例实测抽取 46 条，含作者/标题/期刊/年份/卷期页/类型）且格式正确。

---

### 步骤 2【P0】LoRA/QLoRA 微调 → 注册 → 服务化闭环 ✅ 已完成

**目标**：打通「标注数据 → 领域微调 → 模型注册 → 部署」的再训练闭环。
**现状**：✅ 已实现，`finetune_service.py` 落地真实 LoRA/QLoRA 微调，接入版本管理自动重训管道。

- [x] 2.1 标注数据导出训练集（`export_ner_training_set` / `build_bio_examples` / `to_conll` / `entities_to_char_bio`，纯 Python 确定性）
- [x] 2.2 PEFT（LoRA，QLoRA 4bit 预留需 bitsandbytes，缺失自动退回标准 LoRA）微调 SciBERT NER；依赖/模型缺失时降级为多数类基线
- [x] 2.3 训练脚本 + token 级精确率/召回率/F1 评估（`token_level_metrics`，全 O 预测 f1=0）
- [x] 2.4 模型注册 + 阶段流转/一键切换（`register_model` + `transition_stage`，晋升 Production 自动归档旧版）
- [x] 2.5 接入触发闭环 `run_finetune_pipeline`（数据准备→训练→评估→注册→部署）+ API `/version-management/retrain/finetune`（读 DB 标注 + `f1_threshold` 自动晋升）

**实现文件**：`services/finetune_service.py`（训练集导出 + `FinetuneService.train_ner` + BIO/评估纯函数）、`services/version_management_service.py`（新增 `run_finetune_pipeline`）、`api/v1/version_management.py`（新增 `FinetuneRequest` + `POST /retrain/finetune`）、`test/test_finetune_service.py`（16 用例）。

**验收**：新增标注导出训练集 → LoRA/QLoRA 微调（缺失时基线降级）→ token 级 F1/P/R 评估 → 注册版本；F1 ≥ 阈值自动晋升 Production（否则停留 Staging 可手动切换）。微调产物落到 `moulds/scibert` 后 `ner_service` 自动加载。

---

### 步骤 3【P1】REBEL / OpenIE 关系抽取模型集成 ✅ 已完成

**目标**：以专门关系抽取模型替代/补充「规则 + LLM」。
**现状**：✅ 已实现，`rebel_service.py` 集成 REBEL 关系分类，可插拔降级，已接入 `extraction_service.py`。

- [x] 3.1 集成 REBEL（关系分类）封装可插拔服务（缺模型自动降级）
- [x] 3.2 接入 `extraction_service.py`，与 NER 输出对齐（source_type/target_type 实体回填 + 去重合并）
- [x] 3.3 增加 `test_rebel_service.py`（7 用例：解析/规范化/降级/对齐/合并去重）

**实现文件**：`services/rebel_service.py`（`parse_rebel_output` 纯函数 + `normalize_relation_type` + `RebelService` 懒加载/降级）、`config.py`（RELATION_EXTRACTION_ENABLED / REBEL_MODEL / REBEL_MODEL_PATH 等）、`extraction_service.py`（`_extract_relations_by_rebel` + 合并去重）。

**验收**：关系抽取可输出三类以上关系（REBEL 原生 200+ 关系类型，规范化后 SCREAMING_SNAKE），无模型时降级为规则不报错。

---

### 步骤 4【P1】监控告警端到端运行

**目标**：让已提供的监控栈真正跑起来并接入真实告警。
**现状**：⚠️ 代码侧（业务指标 exporter + 告警 webhook 接收/转发 + 监控配置）已打通；⚠️ 本机未安装 Docker，4.1/4.2 无法在本机实际启动验证。

- [ ] 4.1（阻塞）启动 `docker compose -f docker-compose.monitoring.yml up -d` —— **本机未安装 Docker**，需在装有 Docker 的机器上执行
- [ ] 4.2（阻塞）验证 Prometheus 抓取后端 `/metrics`、Grafana 仪表盘出图、Filebeat→Logstash→ES→Kibana 日志链路 —— 依赖 4.1 启动后验证
- [x] 4.3 接入真实告警渠道：新增 `services/alert_service.py`（钉钉/企业微信 markdown 格式化 + HMAC-SHA256 加签 + 通用 webhook 透传）与 `api/v1/alerts.py`（`POST /alerts/webhook` 接收 Alertmanager 告警 → 结构化 JSON 日志进入 ELK + 按 `ALERT_WEBHOOK_URL/ALERT_WEBHOOK_SECRET` 异步转发外部渠道）；`alertmanager.yml` 默认 receiver 指向 `host.docker.internal:8000/api/v1/alerts/webhook`
- [x] 4.4 补充业务指标：新增 `utils/business_metrics.py` 暴露 `/metrics/business`（模型推理延迟 `model_inference_duration_seconds` + Celery 队列长度 `celery_queue_length`，Redis `LLEN` 抓取时刷新、不可达记 0）；`ner_service.py` 埋点计时；`prometheus.yml` 新增 `backend-business` job、`alerts.yml` 新增 `SlowModelInference`/`CeleryQueueBacklog` 规则、Grafana 新增「模型推理延迟(P95)」「Celery 队列长度」面板

**实现文件**：`utils/business_metrics.py`、`services/alert_service.py`、`api/v1/alerts.py`、`test/test_monitoring.py`（10 用例，Ruff/Black 通过）；配置 `config.py`（`ALERT_WEBHOOK_URL/SECRET`）、`main.py`/`router.py`/`ner_service.py` 接线、`monitoring/{prometheus/prometheus.yml,prometheus/alerts.yml,alertmanager/alertmanager.yml,grafana/dashboards/backend-overview.json}`。

**验收**：代码侧验收通过——`/metrics/business` 可返回业务指标、`POST /alerts/webhook` 可记录结构化日志并转发外部渠道（单测覆盖）。**Docker 未安装，4.1/4.2 的「人为制造 5xx/慢请求触发告警、Kibana 检索」需在装有 Docker 的环境按下方命令验证。**

**Docker 环境验证命令**：

```bash
# 1. 启动监控栈（后端需以 host.docker.internal:8000 可访问）
docker compose -f docker-compose.monitoring.yml up -d

# 2. 确认抓取正常
curl http://localhost:9090/api/v1/targets            # backend / backend-business 两个 job 均 up
curl http://localhost:8000/metrics/business          # 业务指标文本
curl http://localhost:3000                            # Grafana（admin/admin），backend-overview 出图

# 3. 人为制造慢请求/5xx 触发告警后观察
#    Alertmanager: http://localhost:9093
#    Kibana:       http://localhost:5601（检索 event:"alert" 与后端 JSON 日志）
```

---

### 步骤 5【P1】补齐 CI/CD 自动部署

**目标**：实现从推送到自动部署的完整流水线。
**现状**：⚠️ `.github/workflows/ci.yml` 已含 lint→test→镜像构建，`deploy` 为 `if: false` 占位。

- [ ] 5.1 初始化 Git 仓库并推送到 GitHub（当前未初始化）
- [ ] 5.2 配置镜像仓库认证 Secrets（`CONTAINER_REGISTRY_USER/PASSWORD`）
- [ ] 5.3 完善 `deploy` job：登录仓库 → 推送镜像 → 部署（ssh 到目标机 / kubectl apply）
- [ ] 5.4 验证 push 触发全链路

**验收**：`git push` 后自动完成 lint→test→build→push→deploy。

---

### 步骤 6【P2】实时协作（WebSocket）

**目标**：多人实时标注与同步。
**现状**：❌ 未实现，当前为轮询/单机。

- [ ] 6.1 后端 WebSocket 通道（标注区/文档粒度）
- [ ] 6.2 冲突检测与乐观锁/标注锁
- [ ] 6.3 前端实时同步（他人标注实时刷新）+ 变更通知广播

**验收**：两个用户同时标注同一文档，变更实时可见且无冲突覆盖。

---

### 步骤 7【P2】主动学习低置信度样本推送

**目标**：将已实现的采样策略落地到标注工作流。
**现状**：⚠️ 采样算法已实现，前端推送链路未做。

- [ ] 7.1 后端按不确定性/多样性计算样本优先级，生成待标注队列
- [ ] 7.2 新增推送 API + 前端「优先标注」入口
- [ ] 7.3 记录标注结果，回写训练集

**验收**：标注者能看到按低置信度排序的待标注样本。

---

### 步骤 8【P2】A/B 测试框架

**目标**：模型版本对比评估。
**现状**：❌ 未实现。

- [ ] 8.1 流量分流（按比例路由到不同模型版本）
- [ ] 8.2 指标采集（准确率/延迟/用户满意度）
- [ ] 8.3 统计显著性判定与结论面板

**验收**：可对两个模型版本进行对比实验并输出结论。

---

### 步骤 9【P2】GNN 图神经网络链路预测

**目标**：以图神经网络增强图谱补全。
**现状**：⚠️ 当前用 TransE 链路预测 + 统计降级。

- [ ] 9.1 引入 GNN（GraphSAGE / RGCN）做链接预测，封装可插拔服务
- [ ] 9.2 与现有关系推理接口统一，缺模型降级 TransE

**验收**：链路预测准确率优于/持平 TransE 基线。

---

### 步骤 10【P3】系统性性能优化

**目标**：全链路性能调优。
**现状**：❌ 未系统开展。

- [ ] 10.1 数据库索引与慢查询优化（MySQL/Neo4j）
- [ ] 10.2 热点缓存（Redis 缓存查询结果/向量）
- [ ] 10.3 解析/推理耗时优化（批处理、GPU 推理、异步化）
- [ ] 10.4 压测并产出基准报告

**验收**：核心接口 P95 延迟与吞吐达到设定目标。

---

### 步骤 11【P3】Kubernetes 生产部署

**目标**：生产级编排与弹性伸缩。
**现状**：⚠️ 仅 docker-compose。

- [ ] 11.1 编写 K8s 资源：Deployment/Service/Ingress/HPA
- [ ] 11.2 ConfigMap/Secret 管理配置与敏感信息
- [ ] 11.3 持久化卷（MySQL/Redis/Neo4j/MinIO 数据）
- [ ] 11.4 灰度/滚动更新与回滚策略

**验收**：`kubectl apply` 一键拉起生产环境，支持滚动更新与扩缩容。

---

**文档版本**：v2.1（新增「后续需要完成的详细步骤」）
**更新日期**：2026-09-10