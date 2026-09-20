"""
GraphRAG 核心服务
实现: 关键词提取 / 图谱检索 / 上下文组装 / LLM 生成
"""
from typing import Any, Optional
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
        """使用 LLM 从问题中提取关键词"""
        prompt = settings.GRAPHRAG_KEYWORD_EXTRACT_PROMPT.format(question=question)
        response = self.llm.generate(
            prompt=prompt,
            temperature=0.1,
            max_tokens=64,
        )
        content = self.llm.extract_content(response)
        # 解析关键词列表
        keywords = [kw.strip() for kw in content.replace("\n", ",").split(",") if kw.strip()]
        logger.debug(f"Extracted keywords: {keywords}")
        return keywords[:5]

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

        # 限制数量
        all_nodes = all_nodes[: settings.GRAPHRAG_MAX_NODES]
        all_relations = all_relations[: settings.GRAPHRAG_MAX_RELATIONS]

        return {
            "nodes": all_nodes,
            "relations": all_relations,
            "keyword_count": len(keywords),
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
                name = props.get("name") or props.get("id") or props.get("title") or str(props)
                lines.append(f"- [{label}] {name}")
            lines.append("")

        # 关系
        if context["relations"]:
            lines.append("## 实体关系\n")
            for rel in context["relations"]:
                src = rel.get("source", {}).get("name", "?")
                tgt = rel.get("target", {}).get("name", "?")
                rtype = rel.get("relation", "?")
                ctx = rel.get("properties", {}).get("context", "")
                ctx_str = f" (上下文: {ctx})" if ctx else ""
                lines.append(f"- {src} --[{rtype}]--> {tgt}{ctx_str}")
            lines.append("")

        return "\n".join(lines) or "（知识图谱中未找到相关信息）"

    # ─── RAG 生成 ───────────────────────────────────────

    async def query(
        self,
        question: str,
        use_llm: bool = True,
        return_context: bool = False,
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

        # 2. 图谱检索
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

        result = {
            "question": question,
            "answer": answer,
            "keywords": keywords,
        }

        if return_context:
            result["context"] = context_data

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
