"""
GraphRAG 集成服务
代理后端请求到 GraphRAGTest 服务 (port 8001)
统一调用流程: 后端 -> GraphRAGTest -> Neo4j + LM Studio
"""

from typing import Any

import httpx
from loguru import logger

GRAPHRAG_BASE_URL = "http://localhost:8001/api/v1"


class GraphRAGIntegration:
    """GraphRAGTest 服务集成代理"""

    def __init__(self, base_url: str = GRAPHRAG_BASE_URL):
        self.base_url = base_url.rstrip("/")

    def _client(self) -> httpx.Client:
        return httpx.Client(timeout=60.0)

    # ─── 健康检查 ───────────────────────────────────────

    def health_check(self) -> dict[str, Any]:
        """检查 GraphRAGTest 服务状态"""
        try:
            with self._client() as client:
                resp = client.get(f"{self.base_url}/health")
                resp.raise_for_status()
                return {"status": "connected", "service": resp.json()}
        except Exception as e:
            logger.warning(f"GraphRAGTest 健康检查失败: {e}")
            return {"status": "disconnected", "error": str(e)}

    # ─── LLM 模型管理 ───────────────────────────────────────

    def llm_status(self) -> dict[str, Any]:
        """获取 LLM (LM Studio) 当前状态"""
        try:
            with self._client() as client:
                resp = client.get(f"{self.base_url}/llm/status")
                resp.raise_for_status()
                return resp.json()
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def list_models(self) -> dict[str, Any]:
        """列出 LM Studio 中可用模型"""
        try:
            with self._client() as client:
                resp = client.get(f"{self.base_url}/llm/models")
                resp.raise_for_status()
                return resp.json()
        except Exception as e:
            return {"error": str(e)}

    def load_model(self, model: str | None = None) -> dict[str, Any]:
        """让 LM Studio 预加载模型"""
        try:
            with self._client() as client:
                payload = {"model": model} if model else {}
                resp = client.post(f"{self.base_url}/llm/load", json=payload)
                resp.raise_for_status()
                return resp.json()
        except Exception as e:
            return {"error": str(e)}

    # ─── GraphRAG 问答 ───────────────────────────────────────

    def rag_query(
        self,
        question: str,
        return_context: bool = False,
        include_sources: bool = True,
    ) -> dict[str, Any]:
        """
        GraphRAG 问答

        Args:
            question: 用户问题
            return_context: 是否返回检索到的图谱上下文
            include_sources: 是否返回带 document_id / snippet 的溯源来源

        Returns:
            {
                "question": str,
                "answer": str,
                "keywords": list[str],
                "context": {...} (optional),
                "sources": [{document_id, chunk_index, snippet, score}...] (optional)
            }
        """
        try:
            with self._client() as client:
                resp = client.post(
                    f"{self.base_url}/query",
                    json={
                        "question": question,
                        "return_context": return_context,
                        "include_sources": include_sources,
                    },
                    timeout=120.0,
                )
                resp.raise_for_status()
                return resp.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"GraphRAG 问答请求失败: {e.response.status_code} - {e.response.text}")
            return {"error": f"请求失败: {e.response.status_code}", "details": e.response.text}
        except Exception as e:
            logger.error(f"GraphRAG 问答异常: {e}")
            return {"error": str(e)}

    # ─── 图谱管理 ───────────────────────────────────────

    def graph_stats(self) -> dict[str, Any]:
        """图谱统计 (节点数/关系数/标签统计)"""
        try:
            with self._client() as client:
                resp = client.get(f"{self.base_url}/graph/stats")
                resp.raise_for_status()
                return resp.json()
        except Exception as e:
            return {"error": str(e)}

    def search_nodes(self, keyword: str, limit: int = 20) -> dict[str, Any]:
        """按关键词模糊搜索图谱节点"""
        try:
            with self._client() as client:
                resp = client.get(
                    f"{self.base_url}/graph/nodes/keyword/{keyword}", params={"limit": limit}
                )
                resp.raise_for_status()
                return resp.json()
        except Exception as e:
            return {"error": str(e)}

    def get_relations_by_type(self, rel_type: str, limit: int = 20) -> dict[str, Any]:
        """按类型查询关系"""
        try:
            with self._client() as client:
                resp = client.get(
                    f"{self.base_url}/graph/relations/type/{rel_type}", params={"limit": limit}
                )
                resp.raise_for_status()
                return resp.json()
        except Exception as e:
            return {"error": str(e)}

    def get_nodes_by_label(self, label: str, limit: int = 50) -> dict[str, Any]:
        """按标签获取所有节点"""
        try:
            with self._client() as client:
                resp = client.get(f"{self.base_url}/graph/nodes/{label}", params={"limit": limit})
                resp.raise_for_status()
                return resp.json()
        except Exception as e:
            return {"error": str(e)}

    # ─── 文档索引 ───────────────────────────────────────

    def index_document(
        self,
        doc_id: str,
        doc_title: str,
        entities: list[dict[str, Any]],
        relations: list[dict[str, Any]],
        metadata: dict[str, Any] | None = None,
        chunks: list[str] | None = None,
    ) -> dict[str, Any]:
        """
        将文档的实体和关系索引到图谱

        entities 格式:
        [{"text": "钙钛矿", "entity_type": "Material", ...}]

        relations 格式:
        [{"source": "钙钛矿", "source_type": "Material",
          "target": "高效率", "target_type": "Property",
          "relation_type": "HAS_PROPERTY", "context": "..."}]

        chunks: 文档文本分块，用于向量化入向量库。
        """
        try:
            with self._client() as client:
                resp = client.post(
                    f"{self.base_url}/index/document",
                    json={
                        "doc_id": doc_id,
                        "doc_title": doc_title,
                        "entities": entities,
                        "relations": relations,
                        "metadata": metadata or {},
                        "chunks": chunks or [],
                    },
                    timeout=120.0,
                )
                resp.raise_for_status()
                return resp.json()
        except Exception as e:
            return {"error": str(e)}

    def add_node(
        self,
        label: str,
        node_id: str,
        properties: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """添加单个图谱节点"""
        try:
            with self._client() as client:
                resp = client.post(
                    f"{self.base_url}/graph/nodes",
                    json={"label": label, "id": node_id, "properties": properties or {}},
                )
                resp.raise_for_status()
                return resp.json()
        except Exception as e:
            return {"error": str(e)}

    def add_relation(
        self,
        source_label: str,
        source_id: str,
        target_label: str,
        target_id: str,
        rel_type: str,
        properties: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """添加图谱关系"""
        try:
            with self._client() as client:
                resp = client.post(
                    f"{self.base_url}/graph/relations",
                    json={
                        "source_label": source_label,
                        "source_id": source_id,
                        "target_label": target_label,
                        "target_id": target_id,
                        "rel_type": rel_type,
                        "properties": properties or {},
                    },
                )
                resp.raise_for_status()
                return resp.json()
        except Exception as e:
            return {"error": str(e)}

    def clear_graph(self) -> dict[str, Any]:
        """清空整个图谱"""
        try:
            with self._client() as client:
                resp = client.delete(f"{self.base_url}/graph/clear")
                resp.raise_for_status()
                return resp.json()
        except Exception as e:
            return {"error": str(e)}

    def seed_demo_data(self) -> dict[str, Any]:
        """初始化示例数据"""
        try:
            with self._client() as client:
                resp = client.post(f"{self.base_url}/seed/demo")
                resp.raise_for_status()
                return resp.json()
        except Exception as e:
            return {"error": str(e)}


# 全局单例
graphrag_integration = GraphRAGIntegration()
