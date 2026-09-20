from app.utils.neo4j_client import Neo4jClient


class GraphService:
    def __init__(self):
        self.neo4j_client = Neo4jClient()

    async def search(self, query: str, entity_type: str = None, limit: int = 20):
        if entity_type:
            cypher = f"""
            MATCH (n:{entity_type})
            WHERE n.name CONTAINS $query OR n.formula CONTAINS $query
            RETURN n
            LIMIT $limit
            """
        else:
            cypher = """
            MATCH (n)
            WHERE n.name CONTAINS $query OR n.formula CONTAINS $query
            RETURN n
            LIMIT $limit
            """
        results = await self.neo4j_client.execute_query(cypher, {"query": query, "limit": limit})
        return results

    async def get_entity(self, entity_id: str):
        cypher = """
        MATCH (n)
        WHERE id(n) = $entity_id OR n.id = $entity_id
        RETURN n
        """
        results = await self.neo4j_client.execute_query(cypher, {"entity_id": entity_id})
        return results[0] if results else None

    async def get_entity_relations(self, entity_id: str, depth: int = 1):
        cypher = f"""
        MATCH path = (n {{id: $entity_id}})-[*1..{depth}]-(m)
        RETURN nodes(path) AS nodes, relationships(path) AS links
        """
        results = await self.neo4j_client.execute_query(cypher, {"entity_id": entity_id})
        return results

    async def execute_cypher(self, cypher: str, params: dict = None):
        return await self.neo4j_client.execute_query(cypher, params)

    async def get_statistics(self):
        cypher = """
        MATCH (n)
        RETURN labels(n) AS labels, count(*) AS count
        """
        node_stats = await self.neo4j_client.execute_query(cypher)

        cypher_rel = """
        MATCH ()-[r]->()
        RETURN type(r) AS type, count(*) AS count
        """
        rel_stats = await self.neo4j_client.execute_query(cypher_rel)

        return {"node_stats": node_stats, "relation_stats": rel_stats}
