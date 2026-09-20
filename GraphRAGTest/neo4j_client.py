"""
Neo4j 图数据库客户端
封装常用的 Cypher 操作: 增删改查节点和关系, 统计, 检索等
"""
from typing import Any, Optional
from neo4j import AsyncGraphDatabase, AsyncDriver
from config import settings
from loguru import logger


class Neo4jClient:
    _driver: Optional[AsyncDriver] = None

    @classmethod
    async def get_driver(cls) -> AsyncDriver:
        if cls._driver is None:
            cls._driver = AsyncGraphDatabase.driver(
                settings.NEO4J_URI,
                auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD),
            )
        return cls._driver

    @classmethod
    async def close(cls):
        if cls._driver:
            await cls._driver.close()
            cls._driver = None

    # ─── 节点操作 ───────────────────────────────────────

    async def create_node(
        self,
        label: str,
        properties: dict[str, Any],
        node_id: Optional[str] = None,
    ) -> dict[str, Any]:
        """创建单个节点"""
        driver = await self.get_driver()
        query = (
            f"CREATE (n:`{label}` $props) "
            "RETURN id(n) AS internal_id, n"
        )
        async with driver.session(database=settings.NEO4J_DATABASE) as session:
            result = await session.run(query, props=properties)
            record = await result.single()
            return {
                "internal_id": record["internal_id"],
                "id": properties.get("id", record["internal_id"]),
                "label": label,
                "properties": record["n"],
            }

    async def create_or_update_node(
        self,
        label: str,
        match_key: str,
        match_value: Any,
        properties: dict[str, Any],
    ) -> dict[str, Any]:
        """MERGE: 存在则更新, 不存在则创建"""
        driver = await self.get_driver()
        query = (
            f"MERGE (n:`{label}` {{{match_key}: $match_value}}) "
            "ON CREATE SET n = $props "
            "ON MATCH SET n += $props "
            "RETURN id(n) AS internal_id, n"
        )
        async with driver.session(database=settings.NEO4J_DATABASE) as session:
            result = await session.run(
                query,
                match_value=match_value,
                props={**properties, match_key: match_value},
            )
            record = await result.single()
            return {"internal_id": record["internal_id"], "label": label, "properties": record["n"]}

    async def delete_node(self, label: str, match_key: str, match_value: Any) -> bool:
        """删除指定节点(同时删除所有关系)"""
        driver = await self.get_driver()
        query = (
            f"MATCH (n:`{label}` {{{match_key}: $value}}) "
            "DETACH DELETE n RETURN count(n) AS deleted"
        )
        async with driver.session(database=settings.NEO4J_DATABASE) as session:
            result = await session.run(query, value=match_value)
            record = await result.single()
            return record["deleted"] > 0

    # ─── 关系操作 ───────────────────────────────────────

    async def create_relation(
        self,
        source_label: str,
        source_key: str,
        source_value: Any,
        target_label: str,
        target_key: str,
        target_value: Any,
        rel_type: str,
        properties: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """创建两个节点之间的关系"""
        driver = await self.get_driver()
        props_clause = ", ".join([f"{k}: ${k}" for k in (properties or {})])
        props_clause = f" {{{props_clause}}}" if props_clause else ""
        params = {
            "sv": source_value,
            "tv": target_value,
            **(properties or {}),
        }
        query = (
            f"MATCH (s:`{source_label}` {{{source_key}: $sv}}) "
            f"MATCH (t:`{target_label}` {{{target_key}: $tv}}) "
            f"CREATE (s)-[r:`{rel_type}`{props_clause}]->(t) "
            "RETURN r"
        )
        async with driver.session(database=settings.NEO4J_DATABASE) as session:
            result = await session.run(query, **params)
            record = await result.single()
            return {
                "source": source_value,
                "target": target_value,
                "type": rel_type,
                "properties": dict(record["r"]),
            }

    async def delete_relation(
        self,
        source_label: str,
        source_key: str,
        source_value: Any,
        rel_type: str,
        target_label: str,
        target_key: str,
        target_value: Any,
    ) -> bool:
        """删除指定关系"""
        driver = await self.get_driver()
        query = (
            f"MATCH (s:`{source_label}` {{{source_key}: $sv}})-[r:`{rel_type}`]->"
            f"(t:`{target_label}` {{{target_key}: $tv}}) "
            "DELETE r RETURN count(r) AS deleted"
        )
        async with driver.session(database=settings.NEO4J_DATABASE) as session:
            result = await session.run(query, sv=source_value, tv=target_value)
            record = await result.single()
            return record["deleted"] > 0

    # ─── 查询操作 ───────────────────────────────────────

    async def find_nodes_by_label(
        self,
        label: str,
        limit: int = 50,
        extra_where: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        """按标签查询所有节点"""
        driver = await self.get_driver()
        where_clause = f"WHERE {extra_where}" if extra_where else ""
        query = f"MATCH (n:`{label}`) {where_clause} RETURN n LIMIT $limit"
        async with driver.session(database=settings.NEO4J_DATABASE) as session:
            result = await session.run(query, limit=limit)
            return [{"label": label, "properties": dict(record["n"])} async for record in result]

    async def find_nodes_by_keyword(
        self,
        keyword: str,
        label: Optional[str] = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """在节点属性中模糊搜索关键词(ILIKE)"""
        driver = await self.get_driver()
        label_clause = f":`{label}`" if label else ""
        query = (
            f"MATCH (n{label_clause}) "
            "WHERE any(key IN keys(n) WHERE toLower(n[key]) CONTAINS toLower($keyword)) "
            "RETURN n LIMIT $limit"
        )
        async with driver.session(database=settings.NEO4J_DATABASE) as session:
            result = await session.run(query, keyword=keyword, limit=limit)
            return [
                {"label": list(record["n"].labels)[0], "properties": dict(record["n"])}
                async for record in result
            ]

    async def find_relations_by_keyword(
        self,
        keyword: str,
        rel_type: Optional[str] = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """搜索关系"""
        driver = await self.get_driver()
        type_clause = f":`{rel_type}`" if rel_type else ""
        query = (
            f"MATCH (s)-[r{type_clause}]->(t) "
            "WHERE any(key IN keys(r) WHERE toLower(r[key]) CONTAINS toLower($keyword)) "
            "RETURN s, r, t LIMIT $limit"
        )
        async with driver.session(database=settings.NEO4J_DATABASE) as session:
            result = await session.run(query, keyword=keyword, limit=limit)
            return [
                {
                    "source": dict(record["s"]),
                    "relation": record["r"].type,
                    "target": dict(record["t"]),
                    "properties": dict(record["r"]),
                }
                async for record in result
            ]

    async def get_neighbors(
        self,
        node_label: str,
        node_key: str,
        node_value: Any,
        depth: int = 2,
        limit: int = 50,
    ) -> dict[str, Any]:
        """获取节点的 N 度邻居"""
        driver = await self.get_driver()
        query = (
            f"MATCH path = (start:`{node_label}` {{{node_key}: $value}})"
            f"-[*1..{depth}]-(neighbor) "
            "RETURN path LIMIT $limit"
        )
        async with driver.session(database=settings.NEO4J_DATABASE) as session:
            result = await session.run(query, value=node_value, limit=limit)
            paths = []
            async for record in result:
                path = record["path"]
                nodes = [{"label": list(n.labels)[0], "properties": dict(n)} for n in path.nodes]
                rels = [{"type": r.type, "properties": dict(r)} for r in path.relationships]
                paths.append({"nodes": nodes, "relationships": rels})
            return {"node": node_value, "neighbors": paths}

    async def get_node_by_id(self, internal_id: int) -> Optional[dict[str, Any]]:
        """根据内部 ID 获取节点"""
        driver = await self.get_driver()
        query = "MATCH (n) WHERE id(n) = $id RETURN n, labels(n) AS lbs"
        async with driver.session(database=settings.NEO4J_DATABASE) as session:
            result = await session.run(query, id=internal_id)
            record = await result.single_or_none()
            if not record:
                return None
            return {"id": internal_id, "label": record["lbs"][0], "properties": dict(record["n"])}

    # ─── 统计操作 ───────────────────────────────────────

    async def get_stats(self) -> dict[str, Any]:
        """获取图谱统计信息"""
        driver = await self.get_driver()
        async with driver.session(database=settings.NEO4J_DATABASE) as session:
            # 节点数量
            node_count = await session.run("MATCH (n) RETURN count(n) AS cnt")
            n_count = (await node_count.single())["cnt"]

            # 关系数量
            rel_count = await session.run("MATCH ()-[r]->() RETURN count(r) AS cnt")
            r_count = (await rel_count.single())["cnt"]

            # 各标签节点数量
            label_result = await session.run(
                "MATCH (n) WITH labels(n)[0] AS lb, count(n) AS cnt "
                "ORDER BY cnt DESC RETURN lb, cnt"
            )
            labels = {record["lb"]: record["cnt"] async for record in label_result}

            # 关系类型数量
            type_result = await session.run(
                "MATCH ()-[r]->() WITH type(r) AS rt, count(r) AS cnt "
                "ORDER BY cnt DESC RETURN rt, cnt"
            )
            rel_types = {record["rt"]: record["cnt"] async for record in type_result}

            return {
                "total_nodes": n_count,
                "total_relations": r_count,
                "node_labels": labels,
                "relation_types": rel_types,
            }

    # ─── 批量操作 ───────────────────────────────────────

    async def batch_import_nodes(
        self,
        label: str,
        nodes: list[dict[str, Any]],
        id_key: str = "id",
    ) -> dict[str, Any]:
        """批量创建节点(CYPHER UNWIND)"""
        driver = await self.get_driver()
        query = (
            f"UNWIND $nodes AS node "
            f"MERGE (n:`{label}` {{{id_key}: node.{id_key}}}) "
            "ON CREATE SET n += node "
            "RETURN count(n) AS cnt"
        )
        async with driver.session(database=settings.NEO4J_DATABASE) as session:
            result = await session.run(query, nodes=nodes)
            record = await result.single()
            return {"label": label, "imported": record["cnt"]}

    async def batch_import_relations(
        self,
        relations: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """
        批量创建关系.

        relations 格式:
        [
          {
            "source_label": "Material",
            "source_id": "钙钛矿",
            "target_label": "Property",
            "target_id": "高效率",
            "rel_type": "HAS_PROPERTY",
            "properties": {"context": "..."}
          }
        ]
        """
        driver = await self.get_driver()
        query = (
            "UNWIND $relations AS rel "
            "MATCH (s {id: rel.source_id}) "
            "MATCH (t {id: rel.target_id}) "
            "CALL apoc.merge.relationship(s, rel.rel_type, {}, rel.properties || {}, t, {}) YIELD rel2 "
            "RETURN count(rel2) AS cnt"
        )
        # 如果没有 APOC, 退化为普通 MERGE:
        fallback_query = (
            "UNWIND $relations AS rel "
            "MATCH (s {id: rel.source_id}) "
            "MATCH (t {id: rel.target_id}) "
            "CALL apoc.merge.relationship(s, rel.rel_type, {}, rel.properties, t) YIELD rel as r "
            "RETURN count(r) AS cnt"
        )
        # 简化版: 用普通 CREATE
        simple_query = (
            "UNWIND $relations AS rel "
            "OPTIONAL MATCH (s:`" + "`+rel.get('source_label','')+`"+ "` {id: rel.source_id}) "
            "OPTIONAL MATCH (t {id: rel.target_id}) "
            "RETURN 0 AS cnt"
        )
        # 正确实现
        correct_query = (
            "UNWIND $relations AS rel "
            "MATCH (s) WHERE s.id = rel.source_id AND s:`" + "`+rel.source_label+`"
            "MATCH (t) WHERE t.id = rel.target_id AND t:`" + "`+rel.target_label+`"
            "CREATE (s)-[r:`" + "`+rel.rel_type+`]->(t) "
            "SET r += rel.properties "
            "RETURN count(r) AS cnt"
        )
        # 最终正确版 (避免动态标签拼接问题)
        final_query = (
            "UNWIND $relations AS rel "
            "CALL { WITH rel "
            "  MATCH (s:`" + "`+rel.source_label+`" + "` {id: rel.source_id}) "
            "  MATCH (t:`" + "`+rel.target_label+`" + "` {id: rel.target_id}) "
            "  CREATE (s)-[r]->(t) "
            "  SET r += rel.properties "
            "  RETURN count(r) AS c "
            "} "
            "RETURN sum(c) AS total"
        )
        try:
            async with driver.session(database=settings.NEO4J_DATABASE) as session:
                result = await session.run(final_query, relations=relations)
                record = await result.single()
                return {"imported": record["total"]}
        except Exception as e:
            logger.warning(f"Batch relation import failed: {e}, trying simple approach")
            # 简化版: 每条单独处理
            imported = 0
            for rel in relations:
                try:
                    await self.create_relation(
                        rel["source_label"],
                        "id",
                        rel["source_id"],
                        rel["target_label"],
                        "id",
                        rel["target_id"],
                        rel["rel_type"],
                        rel.get("properties"),
                    )
                    imported += 1
                except Exception:
                    pass
            return {"imported": imported}

    async def clear_graph(self) -> dict[str, Any]:
        """清空整个图谱(危险操作)"""
        driver = await self.get_driver()
        async with driver.session(database=settings.NEO4J_DATABASE) as session:
            result = await session.run("MATCH (n) DETACH DELETE n RETURN count(n) AS cnt")
            record = await result.single()
            return {"deleted_nodes": record["cnt"]}


# 全局单例
neo4j_client = Neo4jClient()
