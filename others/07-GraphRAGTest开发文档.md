# 07-GraphRAGTest 开发文档

## 概述

GraphRAGTest 是本项目中独立的 **GraphRAG（知识图谱增强检索）子系统**，部署在 `http://localhost:8001`。它基于 **Neo4j 图数据库** + **Qwen LLM（LM Studio 本地部署）** 实现智能问答。

**与主项目（端口 8000）的关系：**

```
前端 (3000)
    │
    ├─► 后端 FastAPI (8000)           ← 主项目：PDF解析/标注/任务管理
    │       └─► Neo4j (7687)          ← 主项目的图谱服务（Neo4j）
    │
    └─► GraphRAG FastAPI (8001)       ← GraphRAG 子系统
            └─► Neo4j (7687)          ← 共享同一个 Neo4j 数据库
            └─► LM Studio (1234)      ← Qwen 本地推理
```

> **注意**：主项目和 GraphRAGTest 共用同一个 Neo4j 数据库。文档解析 + 信息抽取完成后，通过 `POST /api/v1/knowledge-graph/rag/index/document` 将实体和关系索引到图谱，之后 GraphRAG 即可基于图谱进行问答。

---

## 架构

### 技术栈

| 组件 | 技术 | 版本 |
|------|------|------|
| LLM 推理 | LM Studio + Qwen | qwen/qwen3-4b-2507 |
| 图数据库 | Neo4j | 5.x |
| API 框架 | FastAPI | 0.115+ |
| Python | Python | 3.10+ |
| HTTP 客户端 | httpx | 0.27+ |

### GraphRAG 工作原理

```
用户问题
    │
    ▼
┌─────────────────────────────────────┐
│  1. 关键词提取 (LLM)                   │
│     prompt 工程引导 Qwen 提取 3-5 个关键词  │
└──────────────────┬──────────────────┘
                   │
                   ▼
┌─────────────────────────────────────┐
│  2. 图谱检索 (Neo4j Cypher)            │
│     用关键词在图中搜索相关实体和关系          │
└──────────────────┬──────────────────┘
                   │
                   ▼
┌─────────────────────────────────────┐
│  3. 上下文组装                          │
│     将图谱三元组格式化为文本上下文          │
└──────────────────┬──────────────────┘
                   │
                   ▼
┌─────────────────────────────────────┐
│  4. LLM 生成 (LM Studio)            │
│     Qwen 基于上下文生成答案              │
└─────────────────────────────────────┘
```

---

## 快速启动

### 前置条件

1. **LM Studio** 已启动，模型 `qwen/qwen3-4b-2507` 已加载
   - 启动 LM Studio → Server 标签页 → Start Server
   - 默认地址: `http://localhost:1234`

2. **Neo4j** 已启动
   - 地址: `bolt://localhost:7687`
   - 默认账号: `neo4j/neo4j`

### 启动步骤

```bash
# 1. 进入目录
cd D:\work\VSCodeWork\aiTest1\GraphRAGTest

# 2. 安装依赖
pip install -r requirements.txt

# 3. 启动服务
python app.py
# 或双击 start.bat

# 4. 验证启动
# Swagger UI: http://localhost:8001/docs
# 健康检查: http://localhost:8001/api/v1/health
```

---

## 目录结构

```
GraphRAGTest/
├── app.py                    # FastAPI 应用入口
├── config.py                 # 全局配置 (LM Studio / Neo4j 地址)
├── .env                      # 环境变量
├── requirements.txt          # Python 依赖
├── neo4j_client.py           # Neo4j 客户端 (节点/关系 CRUD + 检索)
├── lmstudio_client.py        # LM Studio 客户端 (模型管理 + Chat Completion)
├── graphrag_service.py       # GraphRAG 核心 (关键词提取 → 检索 → 生成)
├── indexer.py               # 图谱索引器 (批量导入实体/关系/文档)
├── api/
│   └── routes.py            # API 路由定义
└── start.bat                # Windows 启动脚本
```

---

## API 接口

> Base URL: `http://localhost:8001/api/v1`
> 认证: 无（本地内部服务）

### 健康检查

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/health` | 服务健康状态 |

### LLM 管理

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/llm/models` | 列出 LM Studio 可用模型 |
| GET | `/llm/status` | 当前模型加载状态 |
| POST | `/llm/load` | 预加载模型到内存 |
| POST | `/llm/unload` | 卸载模型 |
| POST | `/llm/generate` | 直接调用 LLM 生成文本 |

**加载模型示例:**
```bash
curl -X POST "http://localhost:8001/api/v1/llm/load" \
  -H "Content-Type: application/json" \
  -d '{"model": "qwen/qwen3-4b-2507"}'
```

### GraphRAG 问答

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/query` | GraphRAG 智能问答 |
| GET | `/query/history` | 查询历史 |

**问答示例:**
```bash
curl -X POST "http://localhost:8001/api/v1/query" \
  -H "Content-Type: application/json" \
  -d '{"question": "钙钛矿有哪些性能特点？", "return_context": true}'
```

**响应示例:**
```json
{
  "question": "钙钛矿有哪些性能特点？",
  "answer": "钙钛矿材料具有以下性能特点：\n1. 高光电转换效率...\n2. 制备成本低...",
  "keywords": ["钙钛矿", "光电转换效率", "带隙可调"],
  "context": {
    "nodes": [...],
    "relations": [...]
  }
}
```

### 图谱管理

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/graph/nodes` | 添加实体节点 |
| POST | `/graph/relations` | 添加关系 |
| POST | `/graph/batch` | 批量导入 |
| DELETE | `/graph/clear` | 清空图谱 |
| GET | `/graph/stats` | 图谱统计 |
| GET | `/graph/nodes/{label}` | 按标签查节点 |
| GET | `/graph/nodes/keyword/{keyword}` | 关键词搜索节点 |

### 文档索引

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/index/document` | 将文档实体+关系批量索引到图谱 |

**索引示例:**
```bash
curl -X POST "http://localhost:8001/api/v1/index/document" \
  -H "Content-Type: application/json" \
  -d '{
    "doc_id": "doc-uuid-001",
    "doc_title": "钙钛矿太阳能电池研究",
    "entities": [
      {"text": "钙钛矿", "entity_type": "Material"},
      {"text": "高效率", "entity_type": "Property"}
    ],
    "relations": [
      {
        "source": "钙钛矿", "source_type": "Material",
        "target": "高效率", "target_type": "Property",
        "relation_type": "HAS_PROPERTY",
        "context": "钙钛矿具有高光电转换效率"
      }
    ]
  }'
```

---

## 与主项目（8000端口）集成

### 集成架构

```
aiTest1 主后端 (8000)
  └─ graphrag_integration.py    # 代理层，调用 GraphRAGTest (8001)
       └─ /knowledge-graph/rag/*  # 新增 API 端点
```

### 新增后端端点（8000端口）

| 方法 | 路径 | 功能 |
|------|------|------|
| GET | `/knowledge-graph/rag/health` | GraphRAGTest 健康状态 |
| GET | `/knowledge-graph/rag/llm/status` | LLM 状态 |
| GET | `/knowledge-graph/rag/llm/models` | 模型列表 |
| POST | `/knowledge-graph/rag/llm/load` | 加载模型 |
| POST | `/knowledge-graph/rag/query` | GraphRAG 问答 |
| GET | `/knowledge-graph/rag/graph/stats` | 图谱统计 |
| POST | `/knowledge-graph/rag/index/document` | 文档索引 |
| POST | `/knowledge-graph/rag/graph/nodes` | 添加节点 |
| POST | `/knowledge-graph/rag/graph/relations` | 添加关系 |
| DELETE | `/knowledge-graph/rag/graph/clear` | 清空图谱 |

### 前端路由

| 路由 | 页面 | 说明 |
|------|------|------|
| `/knowledge-graph` | 图谱探索 | 力导向图可视化 |
| `/knowledge-graph/rag` | GraphRAG 问答 | 智能问答对话界面 |

### 集成流程

```
1. 文档上传
   前端 → POST /documents/upload → 后端保存 PDF

2. 文档解析
   前端 → POST /documents/:id/parse → Celery Worker 解析 PDF
   ↓
   extraction_service.py 提取实体和关系
   ↓
   调用 POST /knowledge-graph/rag/index/document
   → 实体和关系写入 Neo4j 图谱

3. GraphRAG 问答
   前端 /knowledge-graph/rag → POST /knowledge-graph/rag/query
   → GraphRAGTest 处理: 关键词提取 → 图谱检索 → Qwen 生成
   → 返回答案给前端
```

---

## 配置说明

### .env 配置

```env
# LM Studio
LMSTUDIO_BASE_URL=http://localhost:1234
LMSTUDIO_MODEL=qwen/qwen3-4b-2507

# Neo4j
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=neo4j
NEO4J_DATABASE=neo4j

# API 服务
API_HOST=0.0.0.0
API_PORT=8001
```

### Neo4j 图谱节点标签体系

| 标签 | 说明 | 示例 |
|------|------|------|
| Document | 文档节点 | 论文本身 |
| Material | 材料类实体 | 钙钛矿, 硅, 石墨烯 |
| Property | 性能类实体 | 高效率, 稳定性好 |
| Method | 方法类实体 | 旋涂法, CVD |
| Parameter | 参数类实体 | 温度, 浓度 |
| Result | 结果类实体 | 光电转换效率 |
| Entity | 通用实体 | 未分类实体 |

### Neo4j 关系类型

| 关系类型 | 说明 | 示例 |
|------|------|------|
| HAS_PROPERTY | 具有性能 | 钙钛矿 --HAS_PROPERTY--> 高效率 |
| PRODUCED_BY | 由...制备 | 电池 --PRODUCED_BY--> 旋涂法 |
| IMPROVES | 改善 | 掺杂 --IMPROVES--> 稳定性 |
| CORRELATES_WITH | 相关于 | 带隙 --CORRELATES_WITH--> 效率 |
| HAS_ENTITY | 文档包含实体 | 论文 --HAS_ENTITY--> 钙钛矿 |

---

## 常见问题

### 1. GraphRAGTest 启动失败

```bash
# 检查端口占用
netstat -ano | findstr :8001

# 检查 Python 依赖
pip install -r requirements.txt

# 检查 Neo4j 连接
# 浏览器访问 http://localhost:7474 确认可登录
```

### 2. LLM 返回为空或超时

- 确认 LM Studio 已启动且模型已加载
- 确认 `http://localhost:1234` 可访问
- 检查 LM Studio Server 标签页是否显示 "Server is running"

### 3. 图谱检索不到结果

- 确认 Neo4j 中已有数据（通过 Cypher 查询确认）
- 检查节点 `id` 属性是否正确设置
- 确认实体和关系已正确关联

### 4. 问答答案不准确

- GraphRAG 依赖图谱中的实体和关系质量
- 可通过 `return_context: true` 查看检索到的上下文
- 关键词提取效果取决于 LLM 质量

---

## 开发指南

### 添加新的节点标签

修改 `neo4j_client.py` 中的查询方法，或直接在 Cypher 中使用：

```cypher
MATCH (n:`新标签`) RETURN n LIMIT 10
```

### 添加新的关系类型

在 `lmstudio_client.py` 或 `indexer.py` 中定义新类型常量：

```python
RELATION_TYPES = {
    "NEW_TYPE": "新关系说明",
}
```

### 扩展 LLM Prompt

修改 `config.py` 中的 prompt 模板：

```python
GRAPHRAG_KEYWORD_EXTRACT_PROMPT = "你是一个关键词提取助手..."
GRAPHRAG_CONTEXT_PROMPT = "你是一个基于知识图谱的问答助手..."
```

---

## 版本信息

- **版本**: 1.0.0
- **日期**: 2026-05-12
- **状态**: ✅ 已集成到主项目
