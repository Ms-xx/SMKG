"""
知识图谱构建Celery任务
实现从抽取的实体和关系构建Neo4j知识图谱
"""

from datetime import datetime

from sqlalchemy import select

from app.core.celery_app import celery_app
from app.core.database import get_db_context
from app.models.document import Document, DocumentElement, DocumentPage
from app.models.task import Task
from app.utils.neo4j_client import Neo4jClient


@celery_app.task(name="build_knowledge_graph", bind=True, queue="graph")
def build_knowledge_graph_task(self, document_id: str):
    """
    知识图谱构建任务
    Args:
        document_id: 文档ID
    Returns:
        构建结果
    """
    neo4j_client = Neo4jClient()

    try:
        # 步骤1: 加载文档和抽取结果
        self.update_state(
            state="PROGRESS",
            meta={"progress": 20, "step": "loading_document"},
        )

        with get_db_context() as db:
            # 获取文档
            result = db.execute(select(Document).where(Document.id == document_id))
            document = result.scalar_one_or_none()

            if not document:
                raise ValueError(f"Document {document_id} not found")

            # 获取文档的所有元素及其抽取结果
            pages_result = db.execute(
                select(DocumentPage).where(DocumentPage.document_id == document_id)
            )
            pages = pages_result.scalars().all()

            all_entities = []
            all_relations = []

            for page in pages:
                elements_result = db.execute(
                    select(DocumentElement).where(DocumentElement.page_id == page.id)
                )
                elements = elements_result.scalars().all()

                for element in elements:
                    if element.metadata and element.metadata.get("entities"):
                        all_entities.extend(element.metadata["entities"])
                    if element.metadata and element.metadata.get("relations"):
                        all_relations.extend(element.metadata["relations"])

        # 步骤2: 创建实体节点
        self.update_state(
            state="PROGRESS",
            meta={"progress": 40, "step": "creating_nodes"},
        )

        unique_entities = {}
        for entity in all_entities:
            # 实体去重
            key = f"{entity['type']}_{entity['text']}"
            if key not in unique_entities:
                unique_entities[key] = entity

        nodes_created = 0
        for _, entity in unique_entities.items():
            # 创建节点
            cypher = f"""
            MERGE (n:{entity['type']} {{name: $name}})
            ON CREATE SET
                n.id = randomUUID(),
                n.created_at = datetime(),
                n.source_document_ids = [$document_id]
            ON MATCH SET
                n.source_document_ids = n.source_document_ids + $document_id
            RETURN n.id as node_id
            """

            params = {
                "name": entity["text"],
                "document_id": document_id,
            }

            # neo4j_client的方法是异步的,但在Celery任务中需要同步调用
            # 这里需要使用同步方法或转换
            import asyncio

            result = asyncio.run(neo4j_client.execute_write(cypher, params))
            nodes_created += 1

        # 步骤3: 创建关系
        self.update_state(
            state="PROGRESS",
            meta={"progress": 60, "step": "creating_relations"},
        )

        relations_created = 0
        for relation in all_relations:
            # 创建关系
            cypher = f"""
            MATCH (source {{name: $source_name}})
            MATCH (target {{name: $target_name}})
            MERGE (source)-[r:{relation['relation_type']}]->(target)
            ON CREATE SET
                r.confidence = $confidence,
                r.context = $context,
                r.source_document_id = $document_id,
                r.created_at = datetime()
            RETURN r
            """

            params = {
                "source_name": relation["source"],
                "target_name": relation["target"],
                "confidence": relation.get("confidence", 0.7),
                "context": relation.get("context", ""),
                "document_id": document_id,
            }

            try:
                import asyncio

                asyncio.run(neo4j_client.execute_write(cypher, params))
                relations_created += 1
            except Exception as e:
                print(f"Failed to create relation: {e}")

        # 步骤4: 创建文档节点并建立关联
        self.update_state(
            state="PROGRESS",
            meta={"progress": 80, "step": "creating_document_node"},
        )

        # 创建文档节点
        doc_cypher = """
        MERGE (d:Document {id: $document_id})
        ON CREATE SET
            d.title = $title,
            d.authors = $authors,
            d.year = $year,
            d.journal = $journal,
            d.created_at = datetime()
        RETURN d
        """

        doc_params = {
            "document_id": document_id,
            "title": document.title,
            "authors": document.authors if document.authors else [],
            "year": (document.publication_date.year if document.publication_date else None),
            "journal": document.journal,
        }

        import asyncio

        asyncio.run(neo4j_client.execute_write(doc_cypher, doc_params))

        # 步骤5: 完成
        self.update_state(
            state="PROGRESS",
            meta={"progress": 100, "step": "completed"},
        )

        return {
            "status": "success",
            "document_id": document_id,
            "nodes_created": nodes_created,
            "relations_created": relations_created,
            "unique_entities": len(unique_entities),
            "total_relations": len(all_relations),
        }

    except Exception as e:
        self.update_state(state="FAILURE", meta={"error": str(e)})

        # 更新任务状态
        with get_db_context() as db:
            task_result = db.execute(select(Task).where(Task.document_id == document_id))
            task = task_result.scalar_one_or_none()
            if task:
                task.status = "failed"
                task.error_message = str(e)
                db.commit()

        raise


@celery_app.task(name="extract_and_build_graph", bind=True)
def extract_and_build_graph_task(self, document_id: str):
    """
    先执行信息抽取,再构建知识图谱的复合任务
    Args:
        document_id: 文档ID
    Returns:
        处理结果
    """
    try:
        # 步骤1: 信息抽取
        self.update_state(
            state="PROGRESS",
            meta={"progress": 30, "step": "extracting_entities"},
        )

        from app.workers.extraction_tasks import extract_entities_task

        extraction_result = extract_entities_task(document_id)

        # 步骤2: 构建图谱
        self.update_state(
            state="PROGRESS",
            meta={"progress": 60, "step": "building_graph"},
        )

        graph_result = build_knowledge_graph_task(document_id)

        # 步骤3: 完成
        self.update_state(
            state="PROGRESS",
            meta={"progress": 100, "step": "completed"},
        )

        return {
            "status": "success",
            "document_id": document_id,
            "extraction_result": extraction_result,
            "graph_result": graph_result,
        }

    except Exception as e:
        self.update_state(state="FAILURE", meta={"error": str(e)})
        raise


@celery_app.task(name="update_graph_statistics", queue="graph")
def update_graph_statistics_task():
    """
    更新图谱统计信息的定时任务
    Returns:
        统计结果
    """
    neo4j_client = Neo4jClient()

    try:
        import asyncio

        # 统计节点数量
        node_stats_query = """
        MATCH (n)
        RETURN labels(n) AS labels, count(*) AS count
        """

        node_stats = asyncio.run(neo4j_client.execute_query(node_stats_query))

        # 统计关系数量
        rel_stats_query = """
        MATCH ()-[r]->()
        RETURN type(r) AS type, count(*) AS count
        """

        rel_stats = asyncio.run(neo4j_client.execute_query(rel_stats_query))

        # 总节点数
        total_nodes_query = "MATCH (n) RETURN count(n) AS total"
        total_nodes = asyncio.run(neo4j_client.execute_query(total_nodes_query))

        # 总关系数
        total_relations_query = "MATCH ()-[r]->() RETURN count(r) AS total"
        total_relations = asyncio.run(neo4j_client.execute_query(total_relations_query))

        return {
            "total_nodes": total_nodes[0]["total"] if total_nodes else 0,
            "total_relations": (total_relations[0]["total"] if total_relations else 0),
            "node_types": node_stats,
            "relation_types": rel_stats,
            "updated_at": datetime.utcnow().isoformat(),
        }

    except Exception as e:
        return {"status": "failed", "error": str(e)}
