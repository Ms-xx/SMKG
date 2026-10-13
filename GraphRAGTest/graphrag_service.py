"""
GraphRAG 核心服务
实现: 关键词提取 / 图谱检索 / 上下文组装 / LLM 生成
"""

from typing import Any
from loguru import logger
from neo4j_client import neo4j_client
from lmstudio_client import llm_client
from config import settings


class GraphRAGService:
    def __init__(self):
        self.llm = llm_client
        self.graph = neo4j_client

    # ─── 关键词提取 ───────────────────────────────────────

    def extract_keywords(self, question: str) -> list[str]:
        """使用 LLM 从问题中提取关键词；LLM 不可用时降级为提取句内词元。"""
        try:
            prompt = settings.GRAPHRAG_KEYWORD_EXTRACT_PROMPT.format(question=question)
            response = self.llm.generate(
                prompt=prompt,
                temperature=0.1,
                max_tokens=64,
            )
            content = self.llm.extract_content(response)
            # 解析关键词列表
            keywords = [
                kw.strip() for kw in content.replace("\n", ",").split(",") if kw.strip()
            ]
            logger.debug(f"Extracted keywords: {keywords}")
            if keywords:
                return keywords[:5]
        except Exception as e:  # noqa: BLE001 - LLM 降级为规则
            logger.warning(f"LLM 关键词提取失败, 改用词元降级: {e}")
        # 降级：取问题里的非停用词元（去重保序）作为关键词
        fallback: list[str] = []
        for tok in self._tokenize(question):
            if tok not in fallback:
                fallback.append(tok)
            if len(fallback) >= 5:
                break
        return fallback or [question[:10]]

    # ─── 图谱检索 ───────────────────────────────────────

    async def retrieve_context(self, keywords: list[str]) -> dict[str, Any]:
        """
        根据关键词检索图谱, 返回上下文信息
        包含: 相关节点列表、关系列表、社区信息
        """
        all_nodes: list[dict[str, Any]] = []
        all_relations: list[dict[str, Any]] = []
        seen_nodes: set[str] = set()

        for kw in keywords:
            try:
                # 搜索节点
                nodes = await self.graph.find_nodes_by_keyword(kw, limit=10)
                for node in nodes:
                    node_key = f"{node['label']}:{node['properties'].get('id', node['properties'].get('name', ''))}"
                    if node_key not in seen_nodes:
                        seen_nodes.add(node_key)
                        all_nodes.append(node)

                # 搜索关系
                rels = await self.graph.find_relations_by_keyword(kw, limit=10)
                all_relations.extend(rels)

                # 搜索关系类型节点
                type_nodes = await self.graph.find_nodes_by_keyword(kw, limit=5)
                for node in type_nodes:
                    node_key = f"{node['label']}:{node['properties'].get('id', node['properties'].get('name', ''))}"
                    if node_key not in seen_nodes:
                        seen_nodes.add(node_key)
                        all_nodes.append(node)
            except Exception as e:
                logger.warning(f"Failed to retrieve for keyword '{kw}': {e}")

        # 关系扩展：把命中节点的一跳关系（CITES / CONTAINS 等）带入上下文，
        # 否则"某论文引用了哪些论文"这类问题只看得到节点、看不到边。
        try:
            matched_ids = [
                str(n["properties"].get("id"))
                for n in all_nodes[:8]
                if n.get("properties", {}).get("id")
            ]
            expanded = await self.graph.find_relations_of_nodes(matched_ids, limit=50)
            seen_rel: set[tuple[str, str, str]] = {
                (
                    str(r.get("source", {}).get("id")),
                    str(r.get("relation")),
                    str(r.get("target", {}).get("id")),
                )
                for r in all_relations
            }
            for rel in expanded:
                key = (
                    str(rel.get("source", {}).get("id")),
                    str(rel.get("relation")),
                    str(rel.get("target", {}).get("id")),
                )
                if key not in seen_rel:
                    seen_rel.add(key)
                    all_relations.append(rel)
        except Exception as e:  # noqa: BLE001
            logger.warning(f"关系扩展失败（不影响节点检索）: {e}")

        # 限制数量
        all_nodes = all_nodes[: settings.GRAPHRAG_MAX_NODES]
        all_relations = all_relations[: settings.GRAPHRAG_MAX_RELATIONS]

        # —— 创新点 B：图谱邻居扩跳重排序 ——
        # 用图谱 1/2 跳邻居的连接强度对候选节点加权重排，突出"中心实体"；
        # 连接更强的节点提前，但仍保留原始检索位置分加权，图不可用时稳定降级为原序。
        rerank_applied = False
        if settings.GRAPH_HOP_RERANK_ENABLED and all_nodes:
            node_keys = [
                str(
                    n.get("properties", {}).get("id")
                    or n.get("properties", {}).get("name")
                    or ""
                )
                for n in all_nodes
            ]
            node_keys = [k for k in node_keys if k]

            if node_keys:
                try:
                    strength = await self.graph.get_connection_strength(
                        node_keys,
                        depth=settings.GRAPH_HOP_DEPTH,
                    )
                    rerank_applied = bool(strength)
                except Exception:  # pragma: no cover - 扩跳失败降级
                    strength = {}

                if strength:
                    max_s = max(strength.values()) or 1.0
                    boost_w = settings.GRAPH_HOP_BOOST_WEIGHT
                    orig_rank = list(range(len(all_nodes)))  # 0 为最前，越大越靠后
                    # 原始检索名次分 = 越靠前越高；再叠加归一化邻居强度
                    all_nodes = [
                        n
                        for _, n in sorted(
                            zip(orig_rank, all_nodes),
                            key=lambda pr: (
                                (len(all_nodes) - pr[0]) * (1.0 - boost_w)
                                + (
                                    strength.get(
                                        str(
                                            pr[1].get("properties", {}).get("id")
                                            or pr[1].get("properties", {}).get("name")
                                            or ""
                                        ),
                                        0,
                                    )
                                    / max_s
                                )
                                * boost_w
                                * 100.0
                            ),
                            reverse=True,
                        )
                    ]
                    logger.debug("图谱邻居扩跳重排完成，连接数 max={}", max_s)

        return {
            "nodes": all_nodes,
            "relations": all_relations,
            "keyword_count": len(keywords),
            "rerank": {
                "enabled": settings.GRAPH_HOP_RERANK_ENABLED,
                "depth": settings.GRAPH_HOP_DEPTH,
                "applied": rerank_applied,
            },
        }

    def format_context(self, context: dict[str, Any]) -> str:
        """将检索结果格式化为文本上下文"""
        lines = []

        # 节点
        if context["nodes"]:
            lines.append("## 相关实体\n")
            for node in context["nodes"]:
                label = node.get("label", "")
                props = node.get("properties", {})
                name = (
                    props.get("name")
                    or props.get("id")
                    or props.get("title")
                    or str(props)
                )
                lines.append(f"- [{label}] {name}")
            lines.append("")

        # 关系
        if context["relations"]:
            lines.append("## 实体关系\n")
            for rel in context["relations"]:
                # Document 节点写入了 name（=title），但兜底兼容只有 title/id 的节点
                src_props = rel.get("source", {}) or {}
                tgt_props = rel.get("target", {}) or {}
                src = (
                    src_props.get("name")
                    or src_props.get("title")
                    or src_props.get("id")
                    or "?"
                )
                tgt = (
                    tgt_props.get("name")
                    or tgt_props.get("title")
                    or tgt_props.get("id")
                    or "?"
                )
                rtype = rel.get("relation", "?")
                ctx = rel.get("properties", {}).get("context", "")
                ctx_str = f" (上下文: {ctx})" if ctx else ""
                lines.append(f"- {src} --[{rtype}]--> {tgt}{ctx_str}")
            lines.append("")

        return "\n".join(lines) or "（知识图谱中未找到相关信息）"

    # ─── 创新点 B：grounding_score ───────────────────────────────────────

    @staticmethod
    def _tokenize(text: str) -> list[str]:
        """拆分为有效 token（拉丁词元 + CJK 连续串按最小长度过滤），用于支撑比对。"""
        import re

        lowered = (text or "").lower()
        # 拉丁/数字词元
        latin: list[str] = re.findall(r"[a-z0-9]+", lowered)
        # CJK 连续片段拆成二元组（与降级嵌入同一策略，避免整段变单 token）
        cjk_runs: list[str] = re.findall(r"[\u4e00-\u9fff]+", lowered)
        bigrams: list[str] = []
        for run in cjk_runs:
            if len(run) >= 2:
                bigrams.extend(run[i : i + 2] for i in range(len(run) - 1))
        tokens = latin + bigrams
        return [t for t in tokens if len(t) >= settings.GROUNDING_MIN_TOKEN_LEN]

    def compute_grounding_score(
        self,
        answer: str,
        context: dict[str, Any],
        sources: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """计算最终答案的证据支撑度 grounding_score（0~1）。

        以"检索到的证据"为支撑语料：图节点名/关系上下文（context）＋溯源页码片段
        （sources.snippet，即该页文本）。将答案拆成有效 token，统计其中能在证据词集中
        命中的比例作为量化支撑分。纯词法比对，CPU/离线可跑，语义扩展预留 GROUNDING_DEVICE。

        返回:
            {
                "enabled": bool,
                "score": float,          # 0~1，支撑 token 占比
                "supported_tokens": [{token, in_nodes, in_sources}]   # 命中详情
                "unsupported_tokens": [...],                          # 未命中 token
                "total_tokens": int,
                "method": "token-overlap",
                "device": settings.GROUNDING_DEVICE,
            }
        """
        if not settings.GROUNDING_ENABLED:
            return {"enabled": False, "score": 0.0, "method": "disabled"}

        answer = (answer or "").strip()
        if not answer:
            return {
                "enabled": True,
                "score": 0.0,
                "supported_tokens": [],
                "unsupported_tokens": [],
                "total_tokens": 0,
                "method": "token-overlap",
                "device": settings.GROUNDING_DEVICE,
            }

        # 1. 汇聚证据文本
        evidence_bits: list[str] = []
        nodes = context.get("nodes", []) or []
        rels = context.get("relations", []) or []
        for n in nodes:
            props = n.get("properties", {}) or {}
            evidence_bits.append(
                str(props.get("name") or props.get("id") or props.get("title") or "")
            )
        for r in rels:
            src = (r.get("source", {}) or {}).get("name") or (
                r.get("source", {}) or {}
            ).get("id")
            tgt = (r.get("target", {}) or {}).get("name") or (
                r.get("target", {}) or {}
            ).get("id")
            ctx = r.get("properties", {}).get("context", "")
            for bit in (src, tgt, ctx):
                if bit:
                    evidence_bits.append(str(bit))
        for s in sources:
            if s.get("snippet"):
                evidence_bits.append(str(s["snippet"]))

        evidence_text = " ".join(evidence_bits)
        if len(evidence_text) > settings.GROUNDING_MAX_EVIDENCE_CHARS:
            evidence_text = evidence_text[: settings.GROUNDING_MAX_EVIDENCE_CHARS]
        evidence_tokens = set(self._tokenize(evidence_text))

        # 拆分节点/来源证据词集，用于标注命中来源
        node_text = " ".join(evidence_bits[: len(nodes)])
        source_text = " ".join(s.get("snippet", "") for s in sources)
        node_tokens = set(self._tokenize(node_text))
        source_tokens = set(self._tokenize(source_text))

        # 2. 统计答案 token 命中率
        answer_tokens = self._tokenize(answer)
        supported: list[dict[str, Any]] = []
        unsupported: list[str] = []
        for tok in answer_tokens:
            if tok in evidence_tokens:
                supported.append(
                    {
                        "token": tok,
                        "in_nodes": tok in node_tokens,
                        "in_sources": tok in source_tokens,
                    }
                )
            else:
                unsupported.append(tok)

        total = len(answer_tokens)
        score = round(len(supported) / total, 4) if total else 0.0

        return {
            "enabled": True,
            "score": score,
            "supported_tokens": supported,
            "unsupported_tokens": unsupported,
            "total_tokens": total,
            "supported_count": len(supported),
            "evidence_sources": len(sources),
            "evidence_nodes": len(nodes),
            "method": "token-overlap",
            "device": settings.GROUNDING_DEVICE,
        }

    # ─── 溯源来源检索 ───────────────────────────────────────

    def retrieve_sources(self, question: str, top_k: int = 5) -> list[dict[str, Any]]:
        """从混合检索器的已索引 chunk 中返回带 document_id / snippet / score 的来源。

        依赖 `hybrid_retriever`（内存态，需先经 `/index/document` 写入 chunk）；
        检索为空或依赖不可用时返回空列表，由调用方降级。
        """
        try:
            from hybrid_retrieval import hybrid_retriever

            result = hybrid_retriever.search(query=question, top_k=top_k)
        except Exception as e:  # pragma: no cover - 依赖缺失降级
            logger.warning(f"溯源来源检索不可用: {e}")
            return []
        sources: list[dict[str, Any]] = []
        for hit in result.get("results", []):
            if hit.get("type") != "chunk":
                continue
            metadata = hit.get("metadata") or {}
            sources.append(
                {
                    "document_id": metadata.get("doc_id"),
                    "chunk_index": metadata.get("chunk_index"),
                    "page_number": None,  # chunk 无页级元数据，页级定位待后端 DocumentPage 回填
                    "snippet": hit.get("text", ""),
                    "score": round(float(hit.get("score") or 0.0), 4),
                }
            )
        return sources

    # ─── RAG 生成 ───────────────────────────────────────

    async def query(
        self,
        question: str,
        use_llm: bool = True,
        return_context: bool = False,
        include_sources: bool = True,
    ) -> dict[str, Any]:
        """
        完整的 GraphRAG 问答流程

        Args:
            question: 用户问题
            use_llm: 是否使用 LLM 生成答案(调试时可关闭)
            return_context: 是否在返回中包含检索到的上下文

        Returns:
            {
                "question": str,
                "answer": str,
                "keywords": list[str],
                "context": {...} (optional),
                "sources": [...] (optional),
            }
        """
        # 1. 提取关键词
        keywords = self.extract_keywords(question)
        if not keywords:
            keywords = [question[:10]]  # fallback

        # 2. 图谱检索（含创新点 B：图谱邻居扩跳重排序，结果带 rerank 标记）
        context_data = await self.retrieve_context(keywords)
        context_text = self.format_context(context_data)

        # 3. LLM 生成
        answer = ""
        if use_llm:
            prompt = settings.GRAPHRAG_CONTEXT_PROMPT.format(
                graph_context=context_text,
                question=question,
            )
            try:
                response = self.llm.generate(
                    prompt=prompt,
                    temperature=0.3,
                    max_tokens=1024,
                )
                answer = self.llm.extract_content(response)
            except Exception as e:
                logger.error(f"LLM generation failed: {e}")
                answer = "抱歉, LLM 服务暂时不可用, 请检查 LM Studio 是否正常运行。"
        else:
            answer = f"[调试模式] 检索到 {len(context_data['nodes'])} 个节点, {len(context_data['relations'])} 条关系"

        # 溯源来源
        sources: list[dict[str, Any]] = []
        if include_sources:
            sources = self.retrieve_sources(question)

        # 创新点 B：grounding_score（必须等答案与证据就绪后计算）
        grounding = self.compute_grounding_score(answer, context_data, sources)

        result = {
            "question": question,
            "answer": answer,
            "keywords": keywords,
            "grounding": grounding,
        }

        if return_context:
            result["context"] = context_data

        if include_sources:
            result["sources"] = sources

        return result

    # ─── 批量导入 (从 JSONL) ───────────────────────────────────────

    async def import_jsonl(
        self,
        lines: list[str],
    ) -> dict[str, Any]:
        """
        从 JSONL 行批量导入数据到图谱

        JSONL 格式(每行一个 JSON):
        实体: {"type": "node", "label": "Material", "id": "钙钛矿", "properties": {"name": "钙钛矿", "description": "..."}}
        关系: {"type": "relation", "source": "钙钛矿", "source_label": "Material", "target": "高效率", "target_label": "Property", "rel_type": "HAS_PROPERTY", "properties": {"context": "..."}}
        """
        nodes_imported = 0
        rels_imported = 0
        errors: list[str] = []

        for i, line in enumerate(lines):
            import json

            try:
                data = json.loads(line.strip())
                t = data.get("type", "")
                if t == "node":
                    await self.graph.create_or_update_node(
                        label=data["label"],
                        match_key="id",
                        match_value=data["id"],
                        properties=data.get("properties", {"id": data["id"]}),
                    )
                    nodes_imported += 1
                elif t == "relation":
                    await self.graph.create_relation(
                        source_label=data["source_label"],
                        source_key="id",
                        source_value=data["source"],
                        target_label=data["target_label"],
                        target_key="id",
                        target_value=data["target"],
                        rel_type=data["rel_type"],
                        properties=data.get("properties"),
                    )
                    rels_imported += 1
            except Exception as e:
                errors.append(f"Line {i+1}: {str(e)}")

        return {
            "nodes_imported": nodes_imported,
            "relations_imported": rels_imported,
            "errors": errors[:10],  # 最多返回10条错误
        }


# 全局单例
graphrag_service = GraphRAGService()
