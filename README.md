# SMKG — 多模态科学文献智能解析与知识图谱构建平台

面向科学文献的多模态智能解析与知识图谱构建平台，实现 PDF 文献“上传 → 多模态解析（文本/公式/图表/版面）→ 深度信息抽取（RAG + LLM + NER）→ 人机协同标注 → 知识图谱构建 → 智能问答/语义搜索”的完整闭环。

## 核心能力

| 模块 | 说明 |
| --- | --- |
| 多模态解析 | PDF 文本提取、版面分析（LayoutLMv3）、公式识别（LaTeX-OCR/pix2tex）、图表检测（YOLOv8）、图表描述（BLIP-2）、OCR（PaddleOCR） |
| 信息抽取 | NER 实体识别（SciBERT）、关系抽取（REBEL）、实体链接（Wikidata/DBpedia） |
| 深度增强 | GraphRAG 检索增强 + LLM 问答、混合检索（向量 + BM25）、Text-to-Cypher |
| 人机协同标注 | 标注/审核工作流、版本管理、Fleiss' Kappa 一致性评估、主动学习采样 |
| 知识图谱 | Neo4j 图谱构建与查询、关系推理与链路预测（TransE）、语义搜索 |
| 运维治理 | 权限与审计、监控告警（Prometheus/Grafana/Alertmanager + ELK）、置信度校准与漂移检测、模型/数据版本管理 |

## 技术栈

- **后端**：FastAPI · SQLAlchemy 2.0（async）· Pydantic v2 · Celery · WebSocket
- **存储**：MySQL 8.0 · Redis · Neo4j 5 · MinIO
- **前端**：React 18 · TypeScript · Vite · Ant Design · Zustand · Vitest（pnpm 管理）
- **检索与检索增强**：GraphRAG · BGE-M3 · bge-reranker · LM Studio（本地 LLM）

## 目录结构

```
LX/
├── backend/            # FastAPI 后端服务
├── frontend/           # React 前端
├── GraphRAGTest/       # GraphRAG 检索增强与问答服务
├── monitoring/         # Prometheus / Alertmanager / Grafana / ELK 配置
├── test/               # 后端测试用例
├── moulds/             # 本地模型目录（不入库，每个模型一个子目录）
├── docker-compose.yml          # 主服务编排
├── docker-compose.monitoring.yml # 监控栈编排
└── .github/workflows/  # CI（lint / format / test / docker build）
```

## 快速开始

### 1. 环境要求

- Python 3.11+
- Node.js 22+（前端，使用 pnpm）
- MySQL 8.0、Redis、Neo4j 5、MinIO（本地运行）

### 2. 配置环境变量

以 `backend/.env.example` 为模板创建 `backend/.env`，并将数据库/缓存/图数据库/对象存储的账号密码替换为真实值（示例中的 `CHANGE_ME` 仅为占位符，勿在生产环境使用）。

### 3. 初始化数据库

```bash
cd backend
pip install -r requirements.txt
python scripts/init_db.py
```

### 4. 启动后端

```bash
cd backend
uvicorn app.main:app --reload --port 8000
# 另开终端启动 Celery Worker
celery -A app.core.celery_app worker -l info -Q parsing,extraction,graph
```

### 5. 启动前端

```bash
cd frontend
pnpm install
pnpm dev
```

## 运行测试

```bash
# 后端（需在 SciMKG 虚拟环境中执行）
cd backend
python -m pytest ../test -v

# 前端
cd frontend
pnpm test
```

## 代码质量

后端使用 Ruff 与 Black，前端使用 ESLint 与 Prettier；CI 会自动执行 lint、format 检查、测试与镜像构建。

## 许可证

（按需补充）