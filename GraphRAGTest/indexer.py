"""
图谱索引构建器
将科学文献中的实体和关系提取后, 批量导入 Neo4j 图数据库
"""
from typing import Any
from loguru import logger
from neo4j_client import neo4j_client


class GraphIndexer:
    """将结构化数据批量索引到 Neo4j"""

    def __init__(self):
        self.graph = neo4j_client

    # ─── 实体索引 ───────────────────────────────────────

    async def index_entity(
        self,
        label: str,
        entity_id: str,
        properties: dict[str, Any],
    ) -> dict[str, Any]:
        """索引单个实体"""
        all_props = {"id": entity_id, **properties}
        return await self.graph.create_or_update_node(
            label=label,
            match_key="id",
            match_value=entity_id,
            properties=all_props,
        )

    async def index_entities(
        self,
        entities: list[dict[str, Any]],
        label_field: str = "entity_type",
        id_field: str = "text",
    ) -> dict[str, Any]:
        """
        批量索引实体列表

        entities 格式:
        [
          {"text": "钙钛矿", "entity_type": "Material", "start": 0, "end": 3},
          {"text": "高效率", "entity_type": "Property", ...}
        ]
        """
        imported = 0
        errors: list[str] = []
        for e in entities:
            try:
                label = e.get(label_field, "Entity")
                entity_id = e.get(id_field, e.get("text", ""))
                props = {k: v for k, v in e.items() if k not in (label_field, id_field)}
                await self.index_entity(label, entity_id, props)
                imported += 1
            except Exception as ex:
                errors.append(f"{entity_id}: {str(ex)}")
        return {"imported": imported, "errors": errors[:20]}

    # ─── 关系索引 ───────────────────────────────────────

    async def index_relation(
        self,
        source_id: str,
        source_label: str,
        target_id: str,
        target_label: str,
        rel_type: str,
        properties: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """索引单个关系"""
        return await self.graph.create_relation(
            source_label=source_label,
            source_key="id",
            source_value=source_id,
            target_label=target_label,
            target_key="id",
            target_value=target_id,
            rel_type=rel_type,
            properties=properties,
        )

    async def index_relations(
        self,
        relations: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """
        批量索引关系列表

        relations 格式:
        [
          {
            "source": "钙钛矿", "source_type": "Material",
            "target": "高效率", "target_type": "Property",
            "relation_type": "HAS_PROPERTY",
            "context": "钙钛矿具有高光电转换效率"
          }
        ]
        """
        imported = 0
        errors: list[str] = []
        for r in relations:
            try:
                await self.index_relation(
                    source_id=r["source"],
                    source_label=r.get("source_type", "Entity"),
                    target_id=r["target"],
                    target_label=r.get("target_type", "Entity"),
                    rel_type=r["relation_type"],
                    properties={k: v for k, v in r.items()
                                if k not in ("source", "source_type", "target", "target_type", "relation_type")},
                )
                imported += 1
            except Exception as ex:
                errors.append(f"{r.get('source')}->{r.get('target')}: {str(ex)}")
        return {"imported": imported, "errors": errors[:20]}

    # ─── 完整文档索引流程 ───────────────────────────────────────

    async def index_document(
        self,
        doc_id: str,
        doc_title: str,
        entities: list[dict[str, Any]],
        relations: list[dict[str, Any]],
        metadata: dict[str, Any] | None = None,
        chunks: list[str] | None = None,
    ) -> dict[str, Any]:
        """
        完整索引一篇科学文献到图谱 + 向量库

        流程:
        1. 创建文档节点
        2. 批量索引所有实体
        3. 批量索引所有关系
        4. 关联文档节点和实体节点
        5. 索引 chunk（Neo4j `Chunk` 节点 + 向量库）
        6. 将实体 / 关系 / chunk 向量化入向量库（混合检索器，兼顾 BM25）
        """
        # 1. 创建文档节点
        doc_props = {
            "id": doc_id,
            "title": doc_title,
            **(metadata or {}),
        }
        await self.graph.create_or_update_node(
            label="Document",
            match_key="id",
            match_value=doc_id,
            properties=doc_props,
        )

        # 2. 索引实体
        ent_result = await self.index_entities(entities)

        # 3. 索引关系
        rel_result = await self.index_relations(relations)

        # 4. 建立文档-实体关联 (HAS_ENTITY 关系)
        doc_entity_rels = []
        for e in entities:
            entity_id = e.get("text", e.get("id", ""))
            doc_entity_rels.append({
                "source_label": "Document",
                "source_id": doc_id,
                "target_label": e.get("entity_type", "Entity"),
                "target_id": entity_id,
                "rel_type": "HAS_ENTITY",
                "properties": {},
            })

        doc_rel_imported = 0
        for rel in doc_entity_rels:
            try:
                await self.graph.create_relation(
                    rel["source_label"], "id", rel["source_id"],
                    rel["target_label"], "id", rel["target_id"],
                    rel["rel_type"],
                    rel["properties"],
                )
                doc_rel_imported += 1
            except Exception:
                pass

        # 5. 索引 chunk 到 Neo4j（Chunk 节点挂载到 Document）
        chunks_imported = 0
        for i, content in enumerate(chunks or []):
            chunk_id = f"{doc_id}:chunk:{i}"
            try:
                await self.graph.create_or_update_node(
                    label="Chunk",
                    match_key="id",
                    match_value=chunk_id,
                    properties={
                        "id": chunk_id,
                        "doc_id": doc_id,
                        "content": content,
                        "chunk_index": i,
                    },
                )
                await self.graph.create_relation(
                    "Document", "id", doc_id,
                    "Chunk", "id", chunk_id,
                    "CONTAINS", {},
                )
                chunks_imported += 1
            except Exception:
                pass

        # 6. 实体 / 关系 / chunk 向量化入向量库（延迟导入，避免服务启动即加载模型）
        from hybrid_retrieval import index_document_vectors

        vec_result = index_document_vectors(doc_id, entities, relations, chunks)

        logger.info(
            f"Indexed doc {doc_id}: {ent_result['imported']} entities, "
            f"{rel_result['imported']} relations, {chunks_imported} chunks; "
            f"vectorized {vec_result['entities_indexed']} entities / "
            f"{vec_result['relations_indexed']} relations / "
            f"{vec_result['chunks_indexed']} chunks"
        )

        return {
            "doc_id": doc_id,
            "entities_imported": ent_result["imported"],
            "relations_imported": rel_result["imported"],
            "doc_entity_links": doc_rel_imported,
            "chunks_imported": chunks_imported,
            "entities_vectorized": vec_result["entities_indexed"],
            "relations_vectorized": vec_result["relations_indexed"],
            "chunks_vectorized": vec_result["chunks_indexed"],
            "errors": (ent_result.get("errors", []) + rel_result.get("errors", []))[:10],
        }


# 全局单例
graph_indexer = GraphIndexer()
