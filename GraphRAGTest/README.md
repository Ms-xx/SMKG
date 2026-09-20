# GraphRAG 本地知识库问答系统

基于 Neo4j 知识图谱 + Qwen LLM (LM Studio 本地部署) 的 GraphRAG 实现。

## 环境要求

- Python 3.10+
- Neo4j Desktop 或 Neo4j Aura (本地图数据库)
- LM Studio (已部署 qwen/qwen3-4b-2507)
- Windows 10/11

## 目录结构

```
GraphRAGTest/
├── config.py              # 配置文件
├── requirements.txt       # Python 依赖
├── neo4j_client.py        # Neo4j 图数据库客户端
├── lmstudio_client.py     # LM Studio LLM 客户端
├── graphrag_service.py    # GraphRAG 核心服务
├── indexer.py             # 图谱索引构建
├── app.py                 # FastAPI 应用入口
├── api/
│   └── routes.py          # API 路由
├── prompts/
│   └── templates.py       # Prompt 模板
├── .env                   # 环境变量（本地配置）
├── start.bat              # Windows 启动脚本
└── README.md              # 本文档
```

## 配置 LM Studio

1. 下载并安装 [LM Studio](https://lmstudio.ai/)
2. 下载模型 `qwen/qwen3-4b-2507` (或其他 Qwen 模型)
3. 启动 LM Studio Server:
   - 切换到 "Server" 标签页
   - 点击 "Start Server"
   - 默认地址: `http://localhost:1234`
4. 验证连接: `GET http://localhost:1234/api/v1/models`

## 配置 Neo4j

1. 下载并安装 [Neo4j Desktop](https://neo4j.com/download/)
2. 创建本地数据库 (推荐版本 5.x)
3. 启动数据库，默认地址: `bolt://localhost:7687`
4. 默认用户名/密码: `neo4j/neo4j` (首次登录需修改)

## 快速启动

### 1. 安装依赖

```bash
cd GraphRAGTest
pip install -r requirements.txt
```

### 2. 配置环境变量

编辑 `.env` 文件，填入实际地址和密码。

### 3. 启动服务

```bash
# Windows
start.bat

# 或手动启动
python app.py
```

### 4. 访问 API 文档

- Swagger UI: http://localhost:8001/docs
- ReDoc: http://localhost:8001/redoc

## API 接口

### 健康检查
- `GET /health` - 服务健康状态

### 图谱管理
- `POST /graph/nodes` - 添加实体节点
- `POST /graph/relations` - 添加关系
- `POST /graph/batch` - 批量导入 (JSONL)
- `DELETE /graph/clear` - 清空图谱
- `GET /graph/stats` - 图谱统计信息
- `GET /graph/nodes/{label}` - 按标签查询节点
- `GET /graph/relations/{type}` - 按类型查询关系

### 问答
- `POST /query` - GraphRAG 问答
- `GET /query/history` - 查询历史

### LLM & 模型
- `GET /llm/models` - 列出 LM Studio 可用模型
- `POST /llm/load` - 加载指定模型到 LM Studio
- `POST /llm/generate` - 直接 LLM 生成 (不使用图谱)

## 工作原理

```
用户问题
    ↓
┌─────────────────────────────────────┐
│  1. Keyword Extraction (LLM)          │
│     提取问题关键词                     │
└─────────────────┬───────────────────┘
                  ↓
┌─────────────────────────────────────┐
│  2. Graph Retrieval (Neo4j)           │
│     查询相关实体和关系                  │
└─────────────────┬───────────────────┘
                  ↓
┌─────────────────────────────────────┐
│  3. Context Assembly                 │
│     组装图谱上下文 + 系统提示           │
└─────────────────┬───────────────────┘
                  ↓
┌─────────────────────────────────────┐
│  4. LLM Generation (LM Studio)      │
│     Qwen 生成答案                     │
└─────────────────────────────────────┘
```

## GraphRAG vs 普通 RAG

| 特性 | 普通 RAG | GraphRAG |
|------|---------|---------|
| 检索单元 | 文本块 | 知识图谱实体/关系 |
| 上下文 | 相似文本片段 | 结构化图谱关系 |
| 多跳推理 | 弱 | 强 |
| 全局理解 | 差 | 好 (社区总结) |
| 可解释性 | 低 | 高 |

## 开发说明

```bash
# 运行测试
python -m pytest

# 代码检查
python -m ruff check .

# 格式化
python -m ruff format .
```

---

**版本**: 1.0.0
**日期**: 2026-05-12
