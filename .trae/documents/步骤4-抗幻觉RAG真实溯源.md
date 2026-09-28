# 步骤4：抗幻觉 RAG 真实溯源

## Context（背景）

步骤4 的目标是把当前「降级规则模板」的溯源锚点 + 多文对比，接入**真实来源元数据**与 **LLM 结论**。

现状（已确认）：
- 后端 [source_anchor_service.py](file:///d:/work/VSCodeWork/LX/backend/app/services/source_anchor_service.py) 的 `extract_anchors` 接受调用方手动传入的 `{document_id, page_number, snippet, score}` 分块；`multi_document_compare` 结论为**规则模板**（无 LLM）。
- 后端 [source_anchor.py](file:///d:/work/VSCodeWork/LX/backend/app/api/v1/source_anchor.py) 暴露 `/source-anchor/anchors` 与 `/source-anchor/compare`，均依赖**调用方自行构造 chunks**，未从 8001 拉取真实来源。
- 后端 [graphrag_integration.py](file:///d:/work/VSCodeWork/LX/backend/app/services/graphrag_integration.py) 已有 `rag_query()`（httpx → 8001 `/query`），返回 `context`（图谱节点/关系），**尚无 sources（document_id/page/snippet）**。
- GraphRAGTest [graphrag_service.py](file:///d:/work/VSCodeWork/LX/GraphRAGTest/graphrag_service.py) 的 `query()` 仅返回图谱 context；[hybrid_retrieval.py](file:///d:/work/VSCodeWork/LX/GraphRAGTest/hybrid_retrieval.py) 的 chunk 带 `metadata {doc_id, chunk_index}`（**无 page_number**）。
- 前端 [GraphRAGPage.tsx](file:///d:/work/VSCodeWork/LX/frontend/src/pages/KnowledgeGraph/GraphRAGPage.tsx) 走 `graphApi.ragQuery` 展示图谱 context；`sourceAnchorApi` 在 [modules.ts:285](file:///d:/work/VSCodeWork/LX/frontend/src/api/modules.ts) 定义但**无页面使用**。

**核心缺口**：GraphRAG 8001 `/query` 不返回「带 document_id/page_number/snippet 的来源分块」，后端无可接的真实出处；`/compare` 结论非 LLM 生成。

## 目标

1. 让 GraphRAGTest `/query` 返回真实 `sources`（来自已索引 chunk 的 document_id + snippet + score）。
2. 后端新增「从 GraphRAG 拉取真实来源 → 生成溯源锚点」路径（`/source-anchor/rag-anchors`），`backend=rag`。
3. `/compare` 多文对比结论接入真实 LLM（`backend=llm`），未配置/失败降级规则模板。
4. 前端 GraphRAGPage 在回答下方展示来源锚点。

## 实现方案

### 1. GraphRAGTest `/query` 返回 sources（4.1）

文件：`GraphRAGTest/graphrag_service.py`
- 在 `retrieve_context`/`query` 中，当 `include_sources=True` 时额外调用 `hybrid_retriever.search(question, top_k=...)`，过滤 `type=="chunk"` 的结果，组装 `sources = [{document_id: metadata.doc_id, chunk_index, snippet: text, score}]`。
- `query(question, use_llm, return_context, include_sources=True)`：`include_sources` 与 `return_context` 解耦——只要 `include_sources` 就返回 `sources` 字段（始终随 `/query` 返回，供前端溯源展示）。
- `routes.py` `QueryRequest` 增加字段与透传。
- page_number 暂不硬编造：chunk 元数据无页号，source 用 `document_id + chunk_index` 定位（`page_number` 设 `None`），并在文档中标注「页级定位待后端 DocumentPage 回填」。

### 2. 后端 `source_anchor_service` 拉取真实来源（4.2）

文件：`backend/app/services/source_anchor_service.py`
- 新增 `anchors_from_rag(question: str) -> dict`：调用 `graphrag_integration.rag_query(question, return_context=True)`；
  - 若返回含 `sources`，转成 `extract_anchors([...])` 入参，`backend="rag"`；
  - 若报错/无 sources，降级：`backend="builtin"`，`anchors=[]`，`note` 说明 8001 未连接或无数来源。
- 复用现有 `llm_chat_completion` 风格（参照 citation_graph 步骤6 的 `_llm_chat_completion`，从 `writing_assistant_service` 抽取或复制最小实现）用于 4.3 的结论生成。

### 3. `/compare` LLM 结论（4.3）

文件：`backend/app/services/source_anchor_service.py`
- `multi_document_compare` 增加 `use_llm: bool = True` 参数：
  - 当 `LLM_ENABLED and LLM_ENDPOINT` 时，把按文档聚合的 `perspectives`（标题+代表性 snippet）拼 prompt，调用 OpenAI 兼容端点生成对比结论，`backend="llm"`；
  - 否则保留规则模板 `backend="builtin"`。
- 保持返回结构字段不变（`question/candidate_count/perspectives/top_chunks/conclusion`）。

### 4. 后端 API 端点

文件：`backend/app/api/v1/source_anchor.py`
- 新增 `POST /source-anchor/rag-anchors`，入参 `{question: str}`，返回 `source_anchor_service.anchors_from_rag(question)`。
- `/compare` 请求模型增加可选 `use_llm: bool = True` 透传。

### 5. 前端 GraphRAGPage 展示来源锚点

文件：`frontend/src/pages/KnowledgeGraph/GraphRAGPage.tsx`
- 复用 `graphApi.ragQuery` 返回值中的 `sources`，在回答下方渲染「来源」列表（document_id + snippet 前 80 字 + score），失败/为空显示占位。
- 新增 `sourceAnchorApi` 封装方法 `ragAnchors(question)`（[modules.ts](file:///d:/work/VSCodeWork/LX/frontend/src/api/modules.ts)）供后续溯源面板使用（当前 Question 先复用 ragQuery 的 sources，不需要额外调用，减少链路）。

### 6. 配置项（可插拔/可降级）

- 复用现有 `LLM_ENABLED/LLM_ENDPOINT/LLM_MODEL/LLM_TIMEOUT`（backend `.env` 已配 LM Studio）。
- GraphRAGTest 复用 `source_anchor_service` 无需新配置；后端无需新增硬编码地址（沿用 `graphrag_integration.GRAPHRAG_BASE_URL`）。

### 7. 测试

文件：`test/test_source_anchor_service.py` + `test/test_graphrag_sources_integration.py`（可选）
- `anchors_from_rag` 成功路径（mock rag_query 返回 sources → backend=rag、anchors 非空）。
- `anchors_from_rag` 降级路径（mock 抛错/空 sources → backend=builtin、anchors=[]、有 note）。
- `multi_document_compare` LLM 路径（monkeypatch LLM_* → backend=llm、conclusion 非空）与降级路径（未配置 → backend=builtin）。
- 既有 5 用例保持通过。

## 涉及文件

- `GraphRAGTest/graphrag_service.py`、`GraphRAGTest/api/routes.py`
- `backend/app/services/source_anchor_service.py`
- `backend/app/api/v1/source_anchor.py`
- `frontend/src/api/modules.ts`、`frontend/src/pages/KnowledgeGraph/GraphRAGPage.tsx`
- `test/test_source_anchor_service.py`
- 文档：`others/XiangMu.md`、`others/00-差别分析.md`、project_memory

## 验证方案

1. **单元/降级**：后端 `pytest test/test_source_anchor_service.py`（新老用例全绿）；`ruff` / `black --check` 通过；前端 `tsc --noEmit` / `eslint` / `prettier --check` 通过。
2. **真实 8001 链路**：
   - 启动 GraphRAGTest（8001）→ `POST /index/document` 索引一篇带 chunks 的文档（test 目录脚本或 seed）→ `POST /query {question, include_sources:true}` 验证返回 `sources` 非空。
   - 后端 `POST /api/v1/source-anchor/rag-anchors {question}` 返回 `backend=rag` + 真实锚点。
3. **真实 LLM /compare**：后端 `.env` 已配 LM Studio；`POST /api/v1/source-anchor/compare` 返回 `backend=llm` 的真实对比结论（同步骤6 实测标准）。
4. 重启后端 uvicorn（本机无 --reload）后实测所有后端 API；前端 build/类型检查通过。